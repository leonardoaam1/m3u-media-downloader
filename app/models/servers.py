from app import db
from datetime import datetime
import enum
import json

class ServerStatus(enum.Enum):
    ONLINE = 'online'
    OFFLINE = 'offline'
    MAINTENANCE = 'maintenance'
    ERROR = 'error'

class ServerProtocol(enum.Enum):
    SFTP = 'sftp'
    NFS = 'nfs'
    SMB = 'smb'
    RSYNC = 'rsync'

class Server(db.Model):
    __tablename__ = 'servers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    host = db.Column(db.String(255), nullable=False)
    protocol = db.Column(db.Enum(ServerProtocol), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    
    # Credentials (encrypted)
    username = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255))
    ssh_key_path = db.Column(db.String(500))
    
    # Paths and configuration
    base_path = db.Column(db.String(500), nullable=False)
    content_types = db.Column(db.Text, nullable=False)  # JSON array
    auto_suggest = db.Column(db.Boolean, default=True)
    
    # Quality filter
    min_quality = db.Column(db.String(20), default='480p')
    max_quality = db.Column(db.String(20), default='1080p')
    accepted_qualities = db.Column(db.Text, nullable=False)  # JSON array
    
    # Directory structure (JSON)
    directory_structure = db.Column(db.Text, nullable=False)
    
    # Transfer settings
    cleanup_after_transfer = db.Column(db.Boolean, default=True)
    max_concurrent_transfers = db.Column(db.Integer, default=3)
    bandwidth_limit = db.Column(db.String(20), default='100MB/s')
    
    # Status and monitoring
    status = db.Column(db.Enum(ServerStatus), default=ServerStatus.OFFLINE)
    last_check = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Disk usage (JSON)
    disk_usage = db.Column(db.Text, default='{}')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    downloads = db.relationship('Download', backref='server', lazy=True)
    transfer_logs = db.relationship('TransferLog', backref='server', lazy=True)
    
    def __init__(self, name, host, protocol, port, username, base_path, 
                 content_types=None, directory_structure=None):
        self.name = name
        self.host = host
        self.protocol = protocol
        self.port = port
        self.username = username
        self.base_path = base_path
        self.content_types = json.dumps(content_types or [])
        self.directory_structure = json.dumps(directory_structure or {})
        self.accepted_qualities = json.dumps(['480p', '720p', '1080p'])
    
    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    @property
    def content_types_list(self):
        """Get content types as list"""
        return json.loads(self.content_types)
    
    @property
    def accepted_qualities_list(self):
        """Get accepted qualities as list"""
        return json.loads(self.accepted_qualities)
    
    @property
    def directory_structure_dict(self):
        """Get directory structure as dict"""
        return json.loads(self.directory_structure)
    
    @property
    def disk_usage_dict(self):
        """Get disk usage as dict"""
        return json.loads(self.disk_usage)
    
    def supports_content_type(self, content_type):
        """Check if server supports specific content type"""
        return content_type in self.content_types_list
    
    def get_directory_for_content(self, content_type, title=None, season=None, episode=None):
        """Get appropriate directory for content type"""
        structure = self.directory_structure_dict
        
        if content_type == 'movie':
            # For movies, we need to determine genre from TMDB
            # For now, return a default directory
            return f"{self.base_path}/Lancamentos/"
        
        elif content_type == 'series':
            # For series, determine platform
            platforms = structure.get('series', [])
            if platforms:
                # This would be enhanced with TMDB data to determine platform
                return f"{self.base_path}/{platforms[0]}/"
        
        elif content_type == 'novela':
            return f"{self.base_path}/Novelas/{title}/" if title else f"{self.base_path}/Novelas/"
        
        return self.base_path
    
    def update_disk_usage(self, total, used, available, percentage):
        """Update disk usage information"""
        self.disk_usage = json.dumps({
            'total': total,
            'used': used,
            'available': available,
            'percentage': percentage
        })
        self.last_check = datetime.utcnow()
    
    def update_status(self, status):
        """Update server status"""
        self.status = status
        self.last_check = datetime.utcnow()
    
    def get_connection_string(self):
        """Get connection string based on protocol"""
        if self.protocol == ServerProtocol.SFTP:
            return f"sftp://{self.username}@{self.host}:{self.port}"
        elif self.protocol == ServerProtocol.NFS:
            return f"nfs://{self.host}:{self.base_path}"
        elif self.protocol == ServerProtocol.SMB:
            return f"smb://{self.host}/{self.base_path}"
        elif self.protocol == ServerProtocol.RSYNC:
            return f"rsync://{self.username}@{self.host}:{self.port}/{self.base_path}"
        return None
    
    def __repr__(self):
        return f'<Server {self.name} ({self.host})>'
