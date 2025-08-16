from .auth import auth_bp
from .main import main_bp
from .downloads import downloads_bp
from .servers import servers_bp
from .admin import admin_bp
from .api import api_bp
from .docs import docs_bp

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(downloads_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(docs_bp)









