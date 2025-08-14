import os
import yt_dlp
import time
from datetime import datetime
from workers.celery_app import celery
from app import db
from app.models.downloads import Download, DownloadStatus
from app.services.logging_service import LoggingService
from app.services.tmdb_service import TMDBService

logger = LoggingService()
tmdb_service = TMDBService()

class DownloadProgressHook:
    def __init__(self, download_id, logger):
        self.download_id = download_id
        self.logger = logger
        self.start_time = time.time()
    
    def __call__(self, d):
        if d['status'] == 'downloading':
            # Calculate progress
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            if total_bytes > 0:
                progress = (downloaded_bytes / total_bytes) * 100
            else:
                progress = 0
            
            # Calculate speed and ETA
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"
            eta_str = f"{eta//60}m {eta%60}s" if eta else "N/A"
            
            # Update download record
            try:
                download = Download.query.get(self.download_id)
                if download:
                    download.update_progress(
                        percentage=progress,
                        downloaded_size=downloaded_bytes,
                        speed=speed_str,
                        eta=eta_str
                    )
                    db.session.commit()
                    
                    # Log progress
                    self.logger.log_download(
                        self.download_id,
                        'info',
                        f'Download progress: {progress:.1f}%',
                        progress_percentage=progress,
                        download_speed=speed_str,
                        estimated_time=eta_str
                    )
            except Exception as e:
                print(f"Error updating download progress: {str(e)}")
        
        elif d['status'] == 'finished':
            self.logger.log_download(
                self.download_id,
                'info',
                'Download completed successfully'
            )

@celery.task(bind=True, name='workers.download_worker.download_task')
def download_task(self, download_id):
    """Download a single file using yt-dlp"""
    try:
        # Get download record
        download = Download.query.get(download_id)
        if not download:
            raise Exception(f"Download {download_id} not found")
        
        # Update status to downloading
        download.start_download()
        db.session.commit()
        
        logger.log_download(
            download_id,
            'info',
            f'Starting download: {download.title}',
            details={'url': download.url, 'quality': download.quality}
        )
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'best[height<=1080]',  # Prefer 1080p or lower
            'outtmpl': os.path.join(
                os.getenv('TEMP_DOWNLOAD_DIR', '/tmp'),
                '%(title)s.%(ext)s'
            ),
            'progress_hooks': [DownloadProgressHook(download_id, logger)],
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writeinfojson': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['pt', 'en'],
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        # Download the file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(download.url, download=False)
            
            # Get the actual filename
            filename = ydl.prepare_filename(info)
            if filename.endswith('.webm'):
                filename = filename[:-5] + '.mp4'
            
            # Update download record
            download.filename = os.path.basename(filename)
            download.download_path = filename
            download.file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            download.complete_download()
            db.session.commit()
            
            logger.log_download(
                download_id,
                'info',
                f'Download completed: {download.filename}',
                details={'file_size': download.file_size}
            )
            
            # Trigger transfer task
            from workers.transfer_worker import transfer_task
            transfer_task.delay(download_id)
            
            return {
                'status': 'success',
                'download_id': download_id,
                'filename': download.filename,
                'file_size': download.file_size
            }
    
    except Exception as e:
        # Update download status to failed
        try:
            download = Download.query.get(download_id)
            if download:
                download.fail(str(e))
                db.session.commit()
        except:
            pass
        
        logger.log_download(
            download_id,
            'error',
            f'Download failed: {str(e)}',
            details={'error': str(e)}
        )
        
        raise

@celery.task(bind=True, name='workers.download_worker.process_download_queue')
def process_download_queue(self):
    """Process the download queue"""
    try:
        from app import current_app
        max_concurrent = current_app.config['MAX_CONCURRENT_DOWNLOADS']
        
        # Get pending downloads ordered by priority
        pending_downloads = Download.query.filter_by(
            status=DownloadStatus.PENDING
        ).order_by(
            Download.priority.desc(),
            Download.created_at.asc()
        ).limit(max_concurrent).all()
        
        active_downloads = Download.query.filter_by(
            status=DownloadStatus.DOWNLOADING
        ).count()
        
        available_slots = max_concurrent - active_downloads
        
        if available_slots > 0 and pending_downloads:
            for download in pending_downloads[:available_slots]:
                # Start download task
                download_task.delay(download.id)
                
                logger.log_system(
                    'info',
                    f'Queued download: {download.title}',
                    details={'download_id': download.id, 'priority': download.priority.value}
                )
        
        return {
            'status': 'success',
            'queued_downloads': len(pending_downloads[:available_slots]),
            'active_downloads': active_downloads,
            'available_slots': available_slots
        }
    
    except Exception as e:
        logger.log_system('error', f'Error processing download queue: {str(e)}')
        raise

@celery.task(bind=True, name='workers.download_worker.retry_failed_downloads')
def retry_failed_downloads(self):
    """Retry failed downloads"""
    try:
        failed_downloads = Download.query.filter_by(
            status=DownloadStatus.FAILED
        ).filter(
            Download.retry_count < Download.max_retries
        ).all()
        
        retried_count = 0
        for download in failed_downloads:
            if download.retry():
                db.session.commit()
                download_task.delay(download.id)
                retried_count += 1
                
                logger.log_download(
                    download.id,
                    'info',
                    f'Retrying download (attempt {download.retry_count})'
                )
        
        return {
            'status': 'success',
            'retried_downloads': retried_count
        }
    
    except Exception as e:
        logger.log_system('error', f'Error retrying failed downloads: {str(e)}')
        raise




