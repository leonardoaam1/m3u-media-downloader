import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://media_user:yZyERmabaBeJ@localhost/mediadownloader')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'media-downloader-secret-key-super-secure-2025')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'media-downloader-jwt-secret-key-2025')
    
    # Application Settings
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # Download Settings
    ACCEPTED_QUALITIES = os.getenv('ACCEPTED_QUALITIES', '480p,720p,1080p').split(',')
    TEMP_DOWNLOAD_DIR = os.getenv('TEMP_DOWNLOAD_DIR', '/www/wwwroot/media_downloader/temp_downloads')
    UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/www/wwwroot/media_downloader/uploads')
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', 3))
    MAX_CONCURRENT_TRANSFERS = int(os.getenv('MAX_CONCURRENT_TRANSFERS', 3))
    BANDWIDTH_LIMIT = os.getenv('BANDWIDTH_LIMIT', '100MB/s')
    
    # TMDB Configuration
    TMDB_API_KEY = os.getenv('TMDB_API_KEY', 'your_tmdb_api_key_here')
    TMDB_LANGUAGE = os.getenv('TMDB_LANGUAGE', 'pt-BR')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = os.getenv('LOG_DIR', '/www/wwwroot/media_downloader/logs')
    
    # Server Settings
    DEFAULT_SESSION_TIMEOUT = int(os.getenv('DEFAULT_SESSION_TIMEOUT', 3600))
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 100 * 1024 * 1024))  # 100MB
    ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', 'm3u,m3u8').split(',')
    
    # Email Settings
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'your_email@gmail.com')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'your_app_password')

class DevelopmentConfig(Config):
    FLASK_DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    FLASK_DEBUG = False
    FLASK_ENV = 'production'

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}

