import os
import shutil
import hashlib
import time
from datetime import datetime
from workers.celery_app import celery
from app import db
from app.models.downloads import Download, DownloadStatus
from app.models.servers import Server, ServerStatus
from app.services.logging_service import LoggingService
from app.services.file_transfer_service import FileTransferService

logger = LoggingService()
transfer_service = FileTransferService()

class TransferProgressCallback:
    def __init__(self, download_id, server_id, logger):
        self.download_id = download_id
        self.server_id = server_id
        self.logger = logger
        self.start_time = time.time()
        self.last_update = time.time()
    
    def __call__(self, transferred_bytes, total_bytes, speed=None):
        current_time = time.time()
        
        # Update every 5 seconds to avoid too many database writes
        if current_time - self.last_update >= 5:
            progress = (transferred_bytes / total_bytes) * 100 if total_bytes > 0 else 0
            speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"
            
            self.logger.log_transfer(
                self.download_id,
                self.server_id,
                'info',
                f'Transfer progress: {progress:.1f}%',
                transfer_speed=speed_str,
                file_size=total_bytes,
                transferred_size=transferred_bytes
            )
            
            self.last_update = current_time

@celery.task(bind=True, name='workers.transfer_worker.transfer_task')
def transfer_task(self, download_id):
    """Transfer a downloaded file to destination server"""
    try:
        # Get download record
        download = Download.query.get(download_id)
        if not download:
            raise Exception(f"Download {download_id} not found")
        
        # Get server record
        server = Server.query.get(download.server_id)
        if not server:
            raise Exception(f"Server {download.server_id} not found")
        
        # Check if file exists
        if not os.path.exists(download.download_path):
            raise Exception(f"Download file not found: {download.download_path}")
        
        # Update status to transferring
        download.start_transfer()
        db.session.commit()
        
        logger.log_transfer(
            download_id,
            download.server_id,
            'info',
            f'Starting transfer: {download.title} to {server.name}',
            details={
                'source': download.download_path,
                'destination': download.destination_path,
                'file_size': download.file_size
            }
        )
        
        # Calculate file checksum for integrity verification
        file_checksum = calculate_file_checksum(download.download_path)
        
        # Create destination directory if it doesn't exist
        destination_dir = os.path.dirname(download.destination_path)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir, exist_ok=True)
        
        # Transfer file based on server protocol
        transfer_success = False
        transfer_speed = None
        
        if server.protocol.value == 'sftp':
            transfer_success, transfer_speed = transfer_service.transfer_sftp(
                server, download.download_path, download.destination_path,
                TransferProgressCallback(download_id, download.server_id, logger)
            )
        elif server.protocol.value == 'nfs':
            transfer_success, transfer_speed = transfer_service.transfer_nfs(
                server, download.download_path, download.destination_path,
                TransferProgressCallback(download_id, download.server_id, logger)
            )
        elif server.protocol.value == 'smb':
            transfer_success, transfer_speed = transfer_service.transfer_smb(
                server, download.download_path, download.destination_path,
                TransferProgressCallback(download_id, download.server_id, logger)
            )
        elif server.protocol.value == 'rsync':
            transfer_success, transfer_speed = transfer_service.transfer_rsync(
                server, download.download_path, download.destination_path,
                TransferProgressCallback(download_id, download.server_id, logger)
            )
        else:
            raise Exception(f"Unsupported protocol: {server.protocol.value}")
        
        if transfer_success:
            # Verify transfer integrity
            if verify_transfer_integrity(download.destination_path, file_checksum):
                # Mark transfer as completed
                download.complete_transfer()
                db.session.commit()
                
                logger.log_transfer(
                    download_id,
                    download.server_id,
                    'info',
                    f'Transfer completed successfully: {download.title}',
                    transfer_speed=transfer_speed,
                    file_size=download.file_size,
                    transferred_size=download.file_size,
                    checksum=file_checksum
                )
                
                # Cleanup local file if configured
                if server.cleanup_after_transfer and os.path.exists(download.download_path):
                    os.remove(download.download_path)
                    logger.log_transfer(
                        download_id,
                        download.server_id,
                        'info',
                        f'Local file cleaned up: {download.download_path}'
                    )
                
                return {
                    'status': 'success',
                    'download_id': download_id,
                    'server_id': download.server_id,
                    'transfer_speed': transfer_speed,
                    'checksum': file_checksum
                }
            else:
                raise Exception("Transfer integrity check failed")
        else:
            raise Exception("Transfer failed")
    
    except Exception as e:
        # Update download status to failed
        try:
            download = Download.query.get(download_id)
            if download:
                download.fail(str(e))
                db.session.commit()
        except:
            pass
        
        logger.log_transfer(
            download_id,
            download.server_id if 'download' in locals() else None,
            'error',
            f'Transfer failed: {str(e)}',
            details={'error': str(e)}
        )
        
        raise

@celery.task(bind=True, name='workers.transfer_worker.process_transfer_queue')
def process_transfer_queue(self):
    """Process the transfer queue"""
    try:
        from app import current_app
        max_concurrent = current_app.config['MAX_CONCURRENT_TRANSFERS']
        
        # Get downloaded files ready for transfer
        ready_transfers = Download.query.filter_by(
            status=DownloadStatus.DOWNLOADED
        ).order_by(
            Download.priority.desc(),
            Download.created_at.asc()
        ).limit(max_concurrent).all()
        
        active_transfers = Download.query.filter_by(
            status=DownloadStatus.TRANSFERRING
        ).count()
        
        available_slots = max_concurrent - active_transfers
        
        if available_slots > 0 and ready_transfers:
            for download in ready_transfers[:available_slots]:
                # Start transfer task
                transfer_task.delay(download.id)
                
                logger.log_system(
                    'info',
                    f'Queued transfer: {download.title} to {download.server.name}',
                    details={'download_id': download.id, 'server_id': download.server_id}
                )
        
        return {
            'status': 'success',
            'queued_transfers': len(ready_transfers[:available_slots]),
            'active_transfers': active_transfers,
            'available_slots': available_slots
        }
    
    except Exception as e:
        logger.log_system('error', f'Error processing transfer queue: {str(e)}')
        raise

@celery.task(bind=True, name='workers.transfer_worker.retry_failed_transfers')
def retry_failed_transfers(self):
    """Retry failed transfers"""
    try:
        failed_transfers = Download.query.filter_by(
            status=DownloadStatus.FAILED
        ).filter(
            Download.retry_count < Download.max_retries
        ).all()
        
        retried_count = 0
        for download in failed_transfers:
            if download.retry():
                db.session.commit()
                transfer_task.delay(download.id)
                retried_count += 1
                
                logger.log_transfer(
                    download.id,
                    download.server_id,
                    'info',
                    f'Retrying transfer (attempt {download.retry_count})'
                )
        
        return {
            'status': 'success',
            'retried_transfers': retried_count
        }
    
    except Exception as e:
        logger.log_system('error', f'Error retrying failed transfers: {str(e)}')
        raise

def calculate_file_checksum(file_path: str) -> str:
    """Calculate SHA256 checksum of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def verify_transfer_integrity(destination_path: str, expected_checksum: str) -> bool:
    """Verify file integrity after transfer"""
    try:
        if not os.path.exists(destination_path):
            return False
        
        actual_checksum = calculate_file_checksum(destination_path)
        return actual_checksum == expected_checksum
    except Exception as e:
        logger.log_system('error', f'Error verifying transfer integrity: {str(e)}')
        return False









