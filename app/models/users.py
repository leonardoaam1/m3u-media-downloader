from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import enum

class UserRole(enum.Enum):
    ADMIN = 'admin'
    OPERATOR = 'operator'
    VIEWER = 'viewer'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    downloads = db.relationship('Download', backref='user', lazy=True)
    activity_logs = db.relationship('UserActivityLog', backref='user', lazy=True)
    
    def __init__(self, username, email, password, role=UserRole.VIEWER):
        self.username = username
        self.email = email
        self.set_password(password)
        self.role = role
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        """Check if user has specific permission based on role"""
        permissions = {
            UserRole.ADMIN: [
                'manage_users', 'manage_servers', 'manage_system', 
                'view_all_logs', 'control_queues', 'manage_backups',
                'view_statistics', 'monitor_servers'
            ],
            UserRole.OPERATOR: [
                'upload_m3u', 'manage_downloads', 'select_server',
                'edit_directory', 'pause_resume_downloads',
                'view_progress', 'edit_tmdb_matches', 'view_own_logs',
                'view_servers'
            ],
            UserRole.VIEWER: [
                'view_progress', 'view_library', 'search_content',
                'view_basic_stats'
            ]
        }
        return permission in permissions.get(self.role, [])
    
    def is_admin(self):
        return self.role == UserRole.ADMIN
    
    def is_operator(self):
        return self.role in [UserRole.ADMIN, UserRole.OPERATOR]
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

