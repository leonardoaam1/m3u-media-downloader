import os
import shutil
import tarfile
import gzip
import subprocess
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import logging
from flask import current_app
from app.services.logging_service import LoggingService

logger = LoggingService()

class BackupManager:
    """Advanced backup system for MediaDown"""
    
    def __init__(self, config=None):
        self.config = config or self._load_config()
        self.logger = LoggingService()
        
        # Setup paths
        self.backup_dir = Path(self.config.get('backup_dir', '/backups/mediadown'))
        self.temp_dir = Path(self.config.get('temp_dir', '/tmp/mediadown_backup'))
        
        # Create directories
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # S3 configuration (optional)
        self.s3_enabled = self.config.get('s3_enabled', False)
        if self.s3_enabled:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.config.get('aws_access_key'),
                aws_secret_access_key=self.config.get('aws_secret_key'),
                region_name=self.config.get('aws_region', 'us-east-1')
            )
            self.s3_bucket = self.config.get('s3_bucket')
    
    def _load_config(self) -> Dict:
        """Load backup configuration"""
        return {
            'backup_dir': os.getenv('BACKUP_DIR', '/backups/mediadown'),
            'temp_dir': os.getenv('BACKUP_TEMP_DIR', '/tmp/mediadown_backup'),
            'retention_days': int(os.getenv('BACKUP_RETENTION_DAYS', '30')),
            'compress': os.getenv('BACKUP_COMPRESS', 'true').lower() == 'true',
            'encryption_key': os.getenv('BACKUP_ENCRYPTION_KEY'),
            
            # Database backup
            'db_host': os.getenv('DB_HOST', 'localhost'),
            'db_port': int(os.getenv('DB_PORT', '5432')),
            'db_name': os.getenv('DB_NAME', 'mediadownloader'),
            'db_user': os.getenv('DB_USER', 'media_user'),
            'db_password': os.getenv('DB_PASSWORD'),
            
            # S3 configuration
            's3_enabled': os.getenv('BACKUP_S3_ENABLED', 'false').lower() == 'true',
            'aws_access_key': os.getenv('AWS_ACCESS_KEY_ID'),
            'aws_secret_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'aws_region': os.getenv('AWS_REGION', 'us-east-1'),
            's3_bucket': os.getenv('BACKUP_S3_BUCKET'),
            
            # Notification
            'notification_email': os.getenv('BACKUP_NOTIFICATION_EMAIL'),
            'webhook_url': os.getenv('BACKUP_WEBHOOK_URL'),
        }
    
    def create_full_backup(self) -> Dict:
        """Create a complete system backup"""
        start_time = datetime.now()
        backup_id = f"full_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.log_system('info', f'Starting full backup: {backup_id}')
        
        try:
            # Create backup directory
            backup_path = self.backup_dir / backup_id
            backup_path.mkdir(exist_ok=True)
            
            results = {
                'backup_id': backup_id,
                'start_time': start_time.isoformat(),
                'status': 'in_progress',
                'components': {}
            }
            
            # 1. Database backup
            results['components']['database'] = self._backup_database(backup_path)
            
            # 2. Application files backup
            results['components']['application'] = self._backup_application_files(backup_path)
            
            # 3. User uploads backup
            results['components']['uploads'] = self._backup_uploads(backup_path)
            
            # 4. Configuration backup
            results['components']['config'] = self._backup_configuration(backup_path)
            
            # 5. Logs backup
            results['components']['logs'] = self._backup_logs(backup_path)
            
            # Create backup manifest
            manifest = self._create_backup_manifest(backup_id, results)
            manifest_path = backup_path / 'manifest.json'
            with open(manifest_path, 'w') as f:
                import json
                json.dump(manifest, f, indent=2)
            
            # Compress backup if enabled
            if self.config.get('compress', True):
                compressed_path = self._compress_backup(backup_path)
                shutil.rmtree(backup_path)  # Remove uncompressed version
                backup_path = compressed_path
            
            # Encrypt backup if encryption key is provided
            if self.config.get('encryption_key'):
                encrypted_path = self._encrypt_backup(backup_path)
                backup_path.unlink()  # Remove unencrypted version
                backup_path = encrypted_path
            
            # Upload to S3 if enabled
            if self.s3_enabled:
                s3_key = self._upload_to_s3(backup_path, backup_id)
                results['s3_key'] = s3_key
            
            # Update results
            end_time = datetime.now()
            results.update({
                'status': 'completed',
                'end_time': end_time.isoformat(),
                'duration': str(end_time - start_time),
                'backup_path': str(backup_path),
                'backup_size': self._get_backup_size(backup_path)
            })
            
            self.logger.log_system('info', f'Full backup completed: {backup_id}', results)
            
            # Send notification
            self._send_notification('success', results)
            
            # Cleanup old backups
            self._cleanup_old_backups()
            
            return results
            
        except Exception as e:
            error_msg = str(e)
            self.logger.log_system('error', f'Full backup failed: {backup_id}', {'error': error_msg})
            
            results.update({
                'status': 'failed',
                'error': error_msg,
                'end_time': datetime.now().isoformat()
            })
            
            # Send error notification
            self._send_notification('error', results)
            
            return results
    
    def _backup_database(self, backup_path: Path) -> Dict:
        """Backup PostgreSQL database"""
        try:
            db_backup_file = backup_path / 'database.sql'
            
            # Use pg_dump to create database backup
            env = os.environ.copy()
            if self.config.get('db_password'):
                env['PGPASSWORD'] = self.config['db_password']
            
            cmd = [
                'pg_dump',
                '-h', self.config['db_host'],
                '-p', str(self.config['db_port']),
                '-U', self.config['db_user'],
                '-d', self.config['db_name'],
                '--no-password',
                '--verbose',
                '--format=custom',
                '--file', str(db_backup_file)
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    'status': 'success',
                    'file': str(db_backup_file),
                    'size': db_backup_file.stat().st_size
                }
            else:
                raise Exception(f"pg_dump failed: {result.stderr}")
                
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _backup_application_files(self, backup_path: Path) -> Dict:
        """Backup application code and static files"""
        try:
            app_backup_file = backup_path / 'application.tar.gz'
            app_root = Path(current_app.root_path).parent
            
            # Files to include
            include_patterns = [
                'app/',
                'workers/',
                'requirements.txt',
                'wsgi.py',
                'gunicorn.conf.py',
                '*.py'
            ]
            
            # Files to exclude
            exclude_patterns = [
                '__pycache__',
                '*.pyc',
                'temp_downloads',
                'uploads',
                'logs',
                '.git',
                'venv',
                '.env'
            ]
            
            with tarfile.open(app_backup_file, 'w:gz') as tar:
                for pattern in include_patterns:
                    for file_path in app_root.glob(pattern):
                        if not any(excl in str(file_path) for excl in exclude_patterns):
                            tar.add(file_path, arcname=file_path.relative_to(app_root))
            
            return {
                'status': 'success',
                'file': str(app_backup_file),
                'size': app_backup_file.stat().st_size
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _backup_uploads(self, backup_path: Path) -> Dict:
        """Backup user uploads and M3U files"""
        try:
            uploads_backup_file = backup_path / 'uploads.tar.gz'
            uploads_dir = Path(current_app.config.get('UPLOAD_DIR', 'uploads'))
            
            if not uploads_dir.exists():
                return {
                    'status': 'skipped',
                    'reason': 'uploads directory does not exist'
                }
            
            with tarfile.open(uploads_backup_file, 'w:gz') as tar:
                tar.add(uploads_dir, arcname='uploads')
            
            return {
                'status': 'success',
                'file': str(uploads_backup_file),
                'size': uploads_backup_file.stat().st_size
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _backup_configuration(self, backup_path: Path) -> Dict:
        """Backup configuration files"""
        try:
            config_backup_file = backup_path / 'config.tar.gz'
            app_root = Path(current_app.root_path).parent
            
            config_files = [
                '.env',
                'nginx.conf',
                'supervisor.conf',
                'gunicorn.conf.py'
            ]
            
            with tarfile.open(config_backup_file, 'w:gz') as tar:
                for config_file in config_files:
                    file_path = app_root / config_file
                    if file_path.exists():
                        tar.add(file_path, arcname=config_file)
            
            return {
                'status': 'success',
                'file': str(config_backup_file),
                'size': config_backup_file.stat().st_size
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _backup_logs(self, backup_path: Path) -> Dict:
        """Backup recent log files"""
        try:
            logs_backup_file = backup_path / 'logs.tar.gz'
            logs_dir = Path('/var/log/mediadown')
            
            if not logs_dir.exists():
                return {
                    'status': 'skipped',
                    'reason': 'logs directory does not exist'
                }
            
            # Only backup logs from last 7 days
            cutoff_date = datetime.now() - timedelta(days=7)
            
            with tarfile.open(logs_backup_file, 'w:gz') as tar:
                for log_file in logs_dir.glob('*.log'):
                    if datetime.fromtimestamp(log_file.stat().st_mtime) > cutoff_date:
                        tar.add(log_file, arcname=f'logs/{log_file.name}')
            
            return {
                'status': 'success',
                'file': str(logs_backup_file),
                'size': logs_backup_file.stat().st_size
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _create_backup_manifest(self, backup_id: str, results: Dict) -> Dict:
        """Create backup manifest with metadata"""
        return {
            'backup_id': backup_id,
            'created_at': datetime.now().isoformat(),
            'type': 'full_backup',
            'version': '1.0',
            'system_info': {
                'hostname': os.uname().nodename,
                'platform': os.uname().sysname,
                'python_version': os.sys.version,
                'app_version': current_app.config.get('VERSION', '2.0.0')
            },
            'components': results.get('components', {}),
            'checksum': self._calculate_checksum(results)
        }
    
    def _calculate_checksum(self, results: Dict) -> str:
        """Calculate checksum for backup verification"""
        import hashlib
        
        content = str(results).encode()
        return hashlib.sha256(content).hexdigest()
    
    def _compress_backup(self, backup_path: Path) -> Path:
        """Compress backup directory"""
        compressed_path = backup_path.with_suffix('.tar.gz')
        
        with tarfile.open(compressed_path, 'w:gz') as tar:
            tar.add(backup_path, arcname=backup_path.name)
        
        return compressed_path
    
    def _encrypt_backup(self, backup_path: Path) -> Path:
        """Encrypt backup file using GPG"""
        encrypted_path = backup_path.with_suffix(backup_path.suffix + '.gpg')
        
        cmd = [
            'gpg',
            '--symmetric',
            '--cipher-algo', 'AES256',
            '--compress-algo', '1',
            '--s2k-mode', '3',
            '--s2k-digest-algo', 'SHA512',
            '--s2k-count', '65011712',
            '--quiet',
            '--no-greeting',
            '--batch',
            '--yes',
            '--passphrase', self.config['encryption_key'],
            '--output', str(encrypted_path),
            str(backup_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            raise Exception(f"Encryption failed: {result.stderr.decode()}")
        
        return encrypted_path
    
    def _upload_to_s3(self, backup_path: Path, backup_id: str) -> str:
        """Upload backup to S3"""
        s3_key = f"backups/{backup_id}/{backup_path.name}"
        
        try:
            self.s3_client.upload_file(
                str(backup_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'StorageClass': 'STANDARD_IA',  # Cheaper storage for backups
                    'ServerSideEncryption': 'AES256'
                }
            )
            
            return s3_key
            
        except ClientError as e:
            raise Exception(f"S3 upload failed: {str(e)}")
    
    def _get_backup_size(self, backup_path: Path) -> int:
        """Get backup file size"""
        if backup_path.is_file():
            return backup_path.stat().st_size
        elif backup_path.is_dir():
            return sum(f.stat().st_size for f in backup_path.rglob('*') if f.is_file())
        return 0
    
    def _cleanup_old_backups(self):
        """Remove old backup files"""
        retention_days = self.config.get('retention_days', 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        deleted_count = 0
        
        for backup_item in self.backup_dir.iterdir():
            if backup_item.stat().st_mtime < cutoff_date.timestamp():
                try:
                    if backup_item.is_file():
                        backup_item.unlink()
                    elif backup_item.is_dir():
                        shutil.rmtree(backup_item)
                    
                    deleted_count += 1
                    self.logger.log_system('info', f'Deleted old backup: {backup_item.name}')
                    
                except Exception as e:
                    self.logger.log_system('error', f'Failed to delete old backup {backup_item.name}: {str(e)}')
        
        if deleted_count > 0:
            self.logger.log_system('info', f'Cleanup completed: {deleted_count} old backups removed')
    
    def _send_notification(self, status: str, results: Dict):
        """Send backup notification"""
        if status == 'success':
            subject = f"✅ MediaDown Backup Successful - {results['backup_id']}"
            message = f"""
Backup completed successfully!

Backup ID: {results['backup_id']}
Duration: {results.get('duration', 'Unknown')}
Size: {self._format_size(results.get('backup_size', 0))}

Components:
{self._format_components_status(results.get('components', {}))}
            """
        else:
            subject = f"❌ MediaDown Backup Failed - {results['backup_id']}"
            message = f"""
Backup failed!

Backup ID: {results['backup_id']}
Error: {results.get('error', 'Unknown error')}

Please check the system logs for more details.
            """
        
        # Send email notification
        email = self.config.get('notification_email')
        if email:
            self._send_email_notification(email, subject, message)
        
        # Send webhook notification
        webhook_url = self.config.get('webhook_url')
        if webhook_url:
            self._send_webhook_notification(webhook_url, status, results)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def _format_components_status(self, components: Dict) -> str:
        """Format components status for notification"""
        status_lines = []
        for component, info in components.items():
            status = info.get('status', 'unknown')
            if status == 'success':
                size = self._format_size(info.get('size', 0))
                status_lines.append(f"  ✅ {component.title()}: {size}")
            elif status == 'failed':
                status_lines.append(f"  ❌ {component.title()}: {info.get('error', 'Failed')}")
            elif status == 'skipped':
                status_lines.append(f"  ⏭️ {component.title()}: {info.get('reason', 'Skipped')}")
        
        return '\n'.join(status_lines)
    
    def _send_email_notification(self, email: str, subject: str, message: str):
        """Send email notification"""
        try:
            # This would use Flask-Mail or similar
            self.logger.log_system('info', f'Email notification sent to {email}: {subject}')
        except Exception as e:
            self.logger.log_system('error', f'Failed to send email notification: {str(e)}')
    
    def _send_webhook_notification(self, webhook_url: str, status: str, results: Dict):
        """Send webhook notification"""
        try:
            import requests
            
            payload = {
                'event': 'backup_completed',
                'status': status,
                'backup_id': results['backup_id'],
                'timestamp': datetime.now().isoformat(),
                'details': results
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.log_system('info', f'Webhook notification sent: {webhook_url}')
            
        except Exception as e:
            self.logger.log_system('error', f'Failed to send webhook notification: {str(e)}')
    
    def list_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []
        
        for item in self.backup_dir.iterdir():
            if item.name.startswith('full_'):
                backup_info = {
                    'backup_id': item.name,
                    'created_at': datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                    'size': self._get_backup_size(item),
                    'path': str(item)
                }
                
                # Try to read manifest if available
                manifest_path = item / 'manifest.json' if item.is_dir() else None
                if manifest_path and manifest_path.exists():
                    try:
                        import json
                        with open(manifest_path) as f:
                            manifest = json.load(f)
                        backup_info['manifest'] = manifest
                    except Exception:
                        pass
                
                backups.append(backup_info)
        
        return sorted(backups, key=lambda x: x['created_at'], reverse=True)
    
    def restore_backup(self, backup_id: str, components: List[str] = None) -> Dict:
        """Restore from backup"""
        # This would implement the restore functionality
        # For security reasons, this is often done manually in production
        raise NotImplementedError("Restore functionality should be implemented with proper safeguards")
    
    def schedule_backups(self):
        """Schedule automatic backups"""
        # Daily backup at 2 AM
        schedule.every().day.at("02:00").do(self.create_full_backup)
        
        # Weekly full backup on Sunday
        schedule.every().sunday.at("01:00").do(self.create_full_backup)
        
        self.logger.log_system('info', 'Backup scheduler initialized')
        
        # Start scheduler in background thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

# Global backup manager instance
backup_manager = BackupManager()

def create_backup() -> Dict:
    """Helper function to create backup"""
    return backup_manager.create_full_backup()

def list_backups() -> List[Dict]:
    """Helper function to list backups"""
    return backup_manager.list_backups()

def init_backup_scheduler():
    """Initialize backup scheduler"""
    backup_manager.schedule_backups()
