import os
import yt_dlp
import tempfile
from typing import Callable, Optional, Dict, Any
from app.services.logging_service import LoggingService
from app.models.downloads import Download

class DownloadService:
    def __init__(self):
        self.logger = LoggingService()
    
    def download_media(self, download_id: int, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Download media using yt-dlp
        
        Args:
            download_id: ID of the download record
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict with download results
        """
        try:
            # Get download record
            download = Download.query.get(download_id)
            if not download:
                raise Exception(f"Download {download_id} not found")
            
            # Configure yt-dlp options
            temp_dir = tempfile.gettempdir()
            output_template = os.path.join(temp_dir, f"download_{download_id}_%(title)s.%(ext)s")
            
            ydl_opts = {
                'format': self._get_format_selector(download.quality),
                'outtmpl': output_template,
                'progress_hooks': [self._create_progress_hook(download_id, progress_callback)],
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'writeinfojson': False,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['pt', 'pt-BR', 'en'],
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'retries': 3,
                'fragment_retries': 3,
                'socket_timeout': 30,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            }
            
            # Add quality-specific options
            if download.quality == '480p':
                ydl_opts['format'] = 'best[height<=480]'
            elif download.quality == '720p':
                ydl_opts['format'] = 'best[height<=720]'
            elif download.quality == '1080p':
                ydl_opts['format'] = 'best[height<=1080]'
            
            self.logger.log_download(
                download_id,
                'info',
                f'Starting download with yt-dlp: {download.title}',
                details={
                    'url': download.url,
                    'quality': download.quality,
                    'options': ydl_opts
                }
            )
            
            # Download the file
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first
                info = ydl.extract_info(download.url, download=False)
                
                # Validate quality
                if not self._validate_quality(info, download.quality):
                    raise Exception(f"Requested quality {download.quality} not available")
                
                # Perform actual download
                ydl.download([download.url])
                
                # Get the downloaded file path
                downloaded_file = self._find_downloaded_file(output_template, info)
                
                if not downloaded_file or not os.path.exists(downloaded_file):
                    raise Exception("Downloaded file not found")
                
                # Get file info
                file_size = os.path.getsize(downloaded_file)
                duration = info.get('duration', 0)
                
                result = {
                    'success': True,
                    'file_path': downloaded_file,
                    'file_size': file_size,
                    'duration': duration,
                    'title': info.get('title', download.title),
                    'format': info.get('format_id', 'unknown'),
                    'actual_quality': self._get_actual_quality(info)
                }
                
                self.logger.log_download(
                    download_id,
                    'info',
                    f'Download completed successfully: {os.path.basename(downloaded_file)}',
                    details=result
                )
                
                return result
                
        except Exception as e:
            error_msg = str(e)
            self.logger.log_download(
                download_id,
                'error',
                f'Download failed: {error_msg}',
                details={'error': error_msg, 'url': download.url if 'download' in locals() else 'unknown'}
            )
            return {
                'success': False,
                'error': error_msg
            }
    
    def _get_format_selector(self, quality: str) -> str:
        """Get yt-dlp format selector for quality"""
        quality_map = {
            '480p': 'best[height<=480]/best',
            '720p': 'best[height<=720]/best',
            '1080p': 'best[height<=1080]/best'
        }
        return quality_map.get(quality, 'best[height<=1080]/best')
    
    def _create_progress_hook(self, download_id: int, progress_callback: Optional[Callable]) -> Callable:
        """Create progress hook for yt-dlp"""
        def progress_hook(d):
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded_bytes = d.get('downloaded_bytes', 0)
                
                if total_bytes > 0:
                    percentage = (downloaded_bytes / total_bytes) * 100
                else:
                    percentage = 0
                
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                # Format speed and ETA
                speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"
                eta_str = f"{eta//60}m {eta%60}s" if eta else "N/A"
                
                # Call custom progress callback if provided
                if progress_callback:
                    progress_callback(percentage, downloaded_bytes, total_bytes, speed_str, eta_str)
                
                # Log progress periodically (every 10%)
                if int(percentage) % 10 == 0:
                    self.logger.log_download(
                        download_id,
                        'info',
                        f'Download progress: {percentage:.1f}%',
                        progress_percentage=percentage,
                        download_speed=speed_str,
                        estimated_time=eta_str
                    )
            
            elif d['status'] == 'finished':
                self.logger.log_download(
                    download_id,
                    'info',
                    f'Download finished: {d.get("filename", "unknown")}'
                )
            
            elif d['status'] == 'error':
                self.logger.log_download(
                    download_id,
                    'error',
                    f'Download error: {d.get("error", "unknown error")}'
                )
        
        return progress_hook
    
    def _validate_quality(self, info: Dict, requested_quality: str) -> bool:
        """Validate if requested quality is available"""
        available_formats = info.get('formats', [])
        
        quality_heights = {
            '480p': 480,
            '720p': 720,
            '1080p': 1080
        }
        
        requested_height = quality_heights.get(requested_quality)
        if not requested_height:
            return True  # If quality not specified, accept any
        
        # Check if any format meets the quality requirement
        for fmt in available_formats:
            height = fmt.get('height', 0)
            if height and height >= requested_height:
                return True
        
        return False
    
    def _find_downloaded_file(self, output_template: str, info: Dict) -> Optional[str]:
        """Find the downloaded file path"""
        # yt-dlp fills in the template with actual values
        import glob
        
        # Extract directory from template
        base_dir = os.path.dirname(output_template)
        
        # Look for files with the download ID
        pattern = output_template.replace('%(title)s', '*').replace('%(ext)s', '*')
        matching_files = glob.glob(pattern)
        
        if matching_files:
            # Return the most recent file
            return max(matching_files, key=os.path.getctime)
        
        # Fallback: look for any recent file in the temp directory
        temp_files = glob.glob(os.path.join(base_dir, f"download_{info.get('id', '*')}*"))
        if temp_files:
            return max(temp_files, key=os.path.getctime)
        
        return None
    
    def _get_actual_quality(self, info: Dict) -> str:
        """Get actual quality from download info"""
        height = info.get('height', 0)
        
        if height >= 1080:
            return '1080p'
        elif height >= 720:
            return '720p'
        elif height >= 480:
            return '480p'
        else:
            return f"{height}p" if height else 'unknown'
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'success': True,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'upload_date': info.get('upload_date', ''),
                    'view_count': info.get('view_count', 0),
                    'description': info.get('description', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': [
                        {
                            'format_id': f.get('format_id'),
                            'quality': f"{f.get('height', 0)}p" if f.get('height') else 'audio',
                            'filesize': f.get('filesize', 0),
                            'ext': f.get('ext', 'unknown')
                        }
                        for f in info.get('formats', [])
                        if f.get('height')  # Only video formats
                    ]
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_url(self, url: str) -> bool:
        """Validate if URL is supported by yt-dlp"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=False)
                return True
                
        except Exception:
            return False
