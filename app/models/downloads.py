from app import db
from datetime import datetime
import enum
import json

class DownloadStatus(enum.Enum):
    PENDING = 'pending'
    DOWNLOADING = 'downloading'
    DOWNLOADED = 'downloaded'
    TRANSFERRING = 'transferring'
    COMPLETED = 'completed'
    FAILED = 'failed'
    PAUSED = 'paused'
    CANCELLED = 'cancelled'

class DownloadPriority(enum.Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'

class Download(db.Model):
    __tablename__ = 'downloads'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Content information
    title = db.Column(db.String(255), nullable=False)
    original_title = db.Column(db.String(255))
    content_type = db.Column(db.String(50), nullable=False)  # movie, series, novela
    season = db.Column(db.Integer)
    episode = db.Column(db.Integer)
    episode_title = db.Column(db.String(255))
    year = db.Column(db.Integer)
    quality = db.Column(db.String(20), nullable=False)
    url = db.Column(db.Text, nullable=False)
    
    # TMDB integration
    tmdb_id = db.Column(db.Integer)
    tmdb_title = db.Column(db.String(255))
    tmdb_poster = db.Column(db.String(500))
    tmdb_genre = db.Column(db.String(100))
    tmdb_platform = db.Column(db.String(100))
    
    # Download information
    file_size = db.Column(db.BigInteger)  # in bytes
    downloaded_size = db.Column(db.BigInteger, default=0)
    download_path = db.Column(db.String(500))
    filename = db.Column(db.String(255))
    
    # Server and destination
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    destination_path = db.Column(db.String(500), nullable=False)
    
    # Status and priority
    status = db.Column(db.Enum(DownloadStatus), default=DownloadStatus.PENDING)
    priority = db.Column(db.Enum(DownloadPriority), default=DownloadPriority.MEDIUM)
    
    # Progress tracking
    progress_percentage = db.Column(db.Float, default=0.0)
    download_speed = db.Column(db.String(20))
    estimated_time = db.Column(db.String(20))
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User who added the download
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Error information
    error_message = db.Column(db.Text)
    error_details = db.Column(db.Text)  # JSON with detailed error info
    
    # Relationships
    download_logs = db.relationship('DownloadLog', backref='download', lazy=True)
    transfer_logs = db.relationship('TransferLog', backref='download', lazy=True)
    
    def __init__(self, title, content_type, quality, url, server_id, destination_path, 
                 user_id, **kwargs):
        self.title = title
        self.content_type = content_type
        self.quality = quality
        self.url = url
        self.server_id = server_id
        self.destination_path = destination_path
        self.user_id = user_id
        
        # Set optional fields
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def start_download(self):
        """Start the download process"""
        self.status = DownloadStatus.DOWNLOADING
        self.started_at = datetime.utcnow()
        self.progress_percentage = 0.0
    
    def update_progress(self, percentage, downloaded_size=None, speed=None, eta=None):
        """Update download progress"""
        self.progress_percentage = percentage
        if downloaded_size is not None:
            self.downloaded_size = downloaded_size
        if speed is not None:
            self.download_speed = speed
        if eta is not None:
            self.estimated_time = eta
        self.updated_at = datetime.utcnow()
    
    def complete_download(self):
        """Mark download as completed"""
        self.status = DownloadStatus.DOWNLOADED
        self.progress_percentage = 100.0
        self.completed_at = datetime.utcnow()
    
    def start_transfer(self):
        """Start file transfer to destination server"""
        self.status = DownloadStatus.TRANSFERRING
    
    def complete_transfer(self):
        """Mark transfer as completed"""
        self.status = DownloadStatus.COMPLETED
        self.completed_at = datetime.utcnow()
    
    def fail(self, error_message, error_details=None):
        """Mark download as failed"""
        self.status = DownloadStatus.FAILED
        self.error_message = error_message
        if error_details:
            self.error_details = json.dumps(error_details)
        self.completed_at = datetime.utcnow()
    
    def retry(self):
        """Retry the download"""
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = DownloadStatus.PENDING
            self.error_message = None
            self.error_details = None
            return True
        return False
    
    def pause(self):
        """Pause the download"""
        if self.status in [DownloadStatus.DOWNLOADING, DownloadStatus.TRANSFERRING]:
            self.status = DownloadStatus.PAUSED
    
    def resume(self):
        """Resume the download"""
        if self.status == DownloadStatus.PAUSED:
            if self.progress_percentage < 100:
                self.status = DownloadStatus.DOWNLOADING
            else:
                self.status = DownloadStatus.TRANSFERRING
    
    def cancel(self):
        """Cancel the download"""
        self.status = DownloadStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def get_formatted_title(self):
        """Get formatted title based on content type"""
        if self.content_type == 'movie':
            return f"{self.title} ({self.year})" if self.year else self.title
        elif self.content_type == 'series':
            if self.season and self.episode:
                return f"{self.title} S{self.season:02d}E{self.episode:02d}"
            return self.title
        elif self.content_type == 'novela':
            if self.season and self.episode:
                return f"{self.title} - {self.season}x{self.episode:02d}"
            return self.title
        return self.title
    
    def get_destination_filename(self):
        """Get the final filename for the destination"""
        base_title = self.get_formatted_title()
        extension = '.mp4'  # Default extension
        
        if self.filename:
            # Extract extension from original filename
            import os
            _, ext = os.path.splitext(self.filename)
            if ext:
                extension = ext
        
        return f"{base_title}{extension}"
    
    def is_acceptable_quality(self):
        """Check if quality is acceptable"""
        from app import current_app
        accepted_qualities = current_app.config['ACCEPTED_QUALITIES']
        return self.quality in accepted_qualities
    
    def get_priority_value(self):
        """Get numeric priority value for sorting"""
        priority_values = {
            DownloadPriority.LOW: 1,
            DownloadPriority.MEDIUM: 2,
            DownloadPriority.HIGH: 3
        }
        return priority_values.get(self.priority, 2)
    
    def __repr__(self):
        return f'<Download {self.title} ({self.status.value})>'

