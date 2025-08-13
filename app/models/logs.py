from app import db
from datetime import datetime
import enum
import json

class LogLevel(enum.Enum):
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'

class SystemLog(db.Model):
    __tablename__ = 'system_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    level = db.Column(db.Enum(LogLevel), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)  # JSON with additional details
    source = db.Column(db.String(100))  # Component that generated the log
    session_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    
    def __init__(self, level, message, details=None, source=None, session_id=None, ip_address=None):
        self.level = level
        self.message = message
        self.details = json.dumps(details) if details else None
        self.source = source
        self.session_id = session_id
        self.ip_address = ip_address

class UserActivityLog(db.Model):
    __tablename__ = 'user_activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)  # JSON with action details
    session_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    def __init__(self, user_id, action, details=None, session_id=None, ip_address=None, user_agent=None):
        self.user_id = user_id
        self.action = action
        self.details = json.dumps(details) if details else None
        self.session_id = session_id
        self.ip_address = ip_address
        self.user_agent = user_agent

class DownloadLog(db.Model):
    __tablename__ = 'download_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    download_id = db.Column(db.Integer, db.ForeignKey('downloads.id'), nullable=False)
    level = db.Column(db.Enum(LogLevel), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)  # JSON with download details
    progress_percentage = db.Column(db.Float)
    download_speed = db.Column(db.String(20))
    estimated_time = db.Column(db.String(20))
    
    def __init__(self, download_id, level, message, details=None, progress_percentage=None, 
                 download_speed=None, estimated_time=None):
        self.download_id = download_id
        self.level = level
        self.message = message
        self.details = json.dumps(details) if details else None
        self.progress_percentage = progress_percentage
        self.download_speed = download_speed
        self.estimated_time = estimated_time

class TransferLog(db.Model):
    __tablename__ = 'transfer_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    download_id = db.Column(db.Integer, db.ForeignKey('downloads.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    level = db.Column(db.Enum(LogLevel), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)  # JSON with transfer details
    transfer_speed = db.Column(db.String(20))
    file_size = db.Column(db.BigInteger)
    transferred_size = db.Column(db.BigInteger)
    checksum = db.Column(db.String(64))  # SHA256 checksum for integrity verification
    
    def __init__(self, download_id, server_id, level, message, details=None, 
                 transfer_speed=None, file_size=None, transferred_size=None, checksum=None):
        self.download_id = download_id
        self.server_id = server_id
        self.level = level
        self.message = message
        self.details = json.dumps(details) if details else None
        self.transfer_speed = transfer_speed
        self.file_size = file_size
        self.transferred_size = transferred_size
        self.checksum = checksum

class TMDBLog(db.Model):
    __tablename__ = 'tmdb_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    level = db.Column(db.Enum(LogLevel), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)  # JSON with TMDB API details
    search_query = db.Column(db.String(255))
    tmdb_id = db.Column(db.Integer)
    match_type = db.Column(db.String(50))  # exact, fuzzy, manual, failed
    cache_hit = db.Column(db.Boolean, default=False)
    api_response_time = db.Column(db.Float)  # Response time in seconds
    rate_limit_remaining = db.Column(db.Integer)
    
    def __init__(self, level, message, details=None, search_query=None, tmdb_id=None,
                 match_type=None, cache_hit=False, api_response_time=None, rate_limit_remaining=None):
        self.level = level
        self.message = message
        self.details = json.dumps(details) if details else None
        self.search_query = search_query
        self.tmdb_id = tmdb_id
        self.match_type = match_type
        self.cache_hit = cache_hit
        self.api_response_time = api_response_time
        self.rate_limit_remaining = rate_limit_remaining

class ServerLog(db.Model):
    __tablename__ = 'server_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    level = db.Column(db.Enum(LogLevel), nullable=False)
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text)  # JSON with server details
    action = db.Column(db.String(100))  # connect, disconnect, transfer, health_check
    response_time = db.Column(db.Float)  # Response time in seconds
    disk_usage_percentage = db.Column(db.Float)
    connection_status = db.Column(db.String(20))  # success, failed, timeout
    
    def __init__(self, server_id, level, message, details=None, action=None, 
                 response_time=None, disk_usage_percentage=None, connection_status=None):
        self.server_id = server_id
        self.level = level
        self.message = message
        self.details = json.dumps(details) if details else None
        self.action = action
        self.response_time = response_time
        self.disk_usage_percentage = disk_usage_percentage
        self.connection_status = connection_status

