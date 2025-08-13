from app import db
from app.models.logs import (
    SystemLog, UserActivityLog, DownloadLog, TransferLog, 
    TMDBLog, ServerLog, LogLevel
)
from flask import request, current_app
from datetime import datetime
import json

class LoggingService:
    def __init__(self):
        pass
    
    def log_system(self, level: str, message: str, details: dict = None, 
                   source: str = None, session_id: str = None, ip_address: str = None):
        """Log system events"""
        try:
            log_level = LogLevel(level.lower())
            
            # Get IP address from request if not provided
            if not ip_address and request:
                ip_address = request.remote_addr
            
            # Get session ID from request if not provided
            if not session_id and request:
                session_id = request.cookies.get('session')
            
            log_entry = SystemLog(
                level=log_level,
                message=message,
                details=details,
                source=source,
                session_id=session_id,
                ip_address=ip_address
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            # Fallback to console logging if database fails
            print(f"Logging error: {str(e)}")
            print(f"System Log: {level.upper()} - {message}")
    
    def log_user_activity(self, user_id: int, action: str, details: dict = None,
                         session_id: str = None, ip_address: str = None, user_agent: str = None):
        """Log user activities"""
        try:
            # Get values from request if not provided
            if not ip_address and request:
                ip_address = request.remote_addr
            
            if not session_id and request:
                session_id = request.cookies.get('session')
            
            if not user_agent and request:
                user_agent = request.headers.get('User-Agent')
            
            log_entry = UserActivityLog(
                user_id=user_id,
                action=action,
                details=details,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            print(f"User activity logging error: {str(e)}")
            print(f"User Activity: User {user_id} - {action}")
    
    def log_download(self, download_id: int, level: str, message: str, details: dict = None,
                    progress_percentage: float = None, download_speed: str = None, 
                    estimated_time: str = None):
        """Log download events"""
        try:
            log_level = LogLevel(level.lower())
            
            log_entry = DownloadLog(
                download_id=download_id,
                level=log_level,
                message=message,
                details=details,
                progress_percentage=progress_percentage,
                download_speed=download_speed,
                estimated_time=estimated_time
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            print(f"Download logging error: {str(e)}")
            print(f"Download Log: {level.upper()} - {message}")
    
    def log_transfer(self, download_id: int, server_id: int, level: str, message: str,
                    details: dict = None, transfer_speed: str = None, file_size: int = None,
                    transferred_size: int = None, checksum: str = None):
        """Log file transfer events"""
        try:
            log_level = LogLevel(level.lower())
            
            log_entry = TransferLog(
                download_id=download_id,
                server_id=server_id,
                level=log_level,
                message=message,
                details=details,
                transfer_speed=transfer_speed,
                file_size=file_size,
                transferred_size=transferred_size,
                checksum=checksum
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            print(f"Transfer logging error: {str(e)}")
            print(f"Transfer Log: {level.upper()} - {message}")
    
    def log_tmdb(self, level: LogLevel, message: str, details: dict = None,
                search_query: str = None, tmdb_id: int = None, match_type: str = None,
                cache_hit: bool = False, api_response_time: float = None, 
                rate_limit_remaining: int = None):
        """Log TMDB API interactions"""
        try:
            log_entry = TMDBLog(
                level=level,
                message=message,
                details=details,
                search_query=search_query,
                tmdb_id=tmdb_id,
                match_type=match_type,
                cache_hit=cache_hit,
                api_response_time=api_response_time,
                rate_limit_remaining=rate_limit_remaining
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            print(f"TMDB logging error: {str(e)}")
            print(f"TMDB Log: {level.value.upper()} - {message}")
    
    def log_server(self, server_id: int, level: str, message: str, details: dict = None,
                  action: str = None, response_time: float = None, 
                  disk_usage_percentage: float = None, connection_status: str = None):
        """Log server events"""
        try:
            log_level = LogLevel(level.lower())
            
            log_entry = ServerLog(
                server_id=server_id,
                level=log_level,
                message=message,
                details=details,
                action=action,
                response_time=response_time,
                disk_usage_percentage=disk_usage_percentage,
                connection_status=connection_status
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            print(f"Server logging error: {str(e)}")
            print(f"Server Log: {level.upper()} - {message}")
    
    def get_logs(self, log_type: str = 'system', filters: dict = None, limit: int = 100) -> list:
        """Get logs with optional filtering"""
        try:
            if log_type == 'system':
                query = SystemLog.query
            elif log_type == 'user_activity':
                query = UserActivityLog.query
            elif log_type == 'download':
                query = DownloadLog.query
            elif log_type == 'transfer':
                query = TransferLog.query
            elif log_type == 'tmdb':
                query = TMDBLog.query
            elif log_type == 'server':
                query = ServerLog.query
            else:
                return []
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    if hasattr(query.model, key):
                        query = query.filter(getattr(query.model, key) == value)
            
            # Order by timestamp descending and limit
            logs = query.order_by(db.desc('timestamp')).limit(limit).all()
            
            return logs
            
        except Exception as e:
            print(f"Error getting logs: {str(e)}")
            return []
    
    def cleanup_old_logs(self, days: int = 30):
        """Clean up logs older than specified days"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Clean up different log types
            log_types = [SystemLog, UserActivityLog, DownloadLog, TransferLog, TMDBLog, ServerLog]
            
            for log_type in log_types:
                deleted_count = log_type.query.filter(
                    log_type.timestamp < cutoff_date
                ).delete()
                
                print(f"Deleted {deleted_count} old {log_type.__name__} entries")
            
            db.session.commit()
            
        except Exception as e:
            print(f"Error cleaning up old logs: {str(e)}")
            db.session.rollback()
    
    def get_log_statistics(self) -> dict:
        """Get log statistics"""
        try:
            stats = {}
            
            # Count logs by type and level
            log_types = [
                ('system', SystemLog),
                ('user_activity', UserActivityLog),
                ('download', DownloadLog),
                ('transfer', TransferLog),
                ('tmdb', TMDBLog),
                ('server', ServerLog)
            ]
            
            for log_name, log_model in log_types:
                stats[log_name] = {}
                
                # Total count
                stats[log_name]['total'] = log_model.query.count()
                
                # Count by level
                for level in LogLevel:
                    count = log_model.query.filter_by(level=level).count()
                    stats[log_name][level.value] = count
                
                # Recent activity (last 24 hours)
                from datetime import timedelta
                yesterday = datetime.utcnow() - timedelta(days=1)
                recent_count = log_model.query.filter(
                    log_model.timestamp >= yesterday
                ).count()
                stats[log_name]['recent_24h'] = recent_count
            
            return stats
            
        except Exception as e:
            print(f"Error getting log statistics: {str(e)}")
            return {}

