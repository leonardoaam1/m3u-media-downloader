from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from celery import Celery
import logging
import os
from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
celery = Celery()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Configure Celery
    celery.conf.update(app.config)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'info'
    
    # Setup logging
    setup_logging(app)
    
    # Create directories if they don't exist
    create_directories(app)
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.downloads import downloads_bp
    from app.routes.servers import servers_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(downloads_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(admin_bp)
    
    return app

def setup_logging(app):
    """Setup logging configuration"""
    if not os.path.exists(app.config['LOG_DIR']):
        os.makedirs(app.config['LOG_DIR'])
    
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
        handlers=[
            logging.FileHandler(os.path.join(app.config['LOG_DIR'], 'app.log')),
            logging.StreamHandler()
        ]
    )

def create_directories(app):
    """Create necessary directories"""
    directories = [
        app.config['TEMP_DOWNLOAD_DIR'],
        app.config['UPLOAD_DIR'],
        app.config['LOG_DIR']
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, mode=0o750)

# Import models to ensure they are registered with SQLAlchemy
from app.models import users, servers, downloads, logs

