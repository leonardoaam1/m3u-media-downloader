#!/usr/bin/env python3
"""
Configuração segura do MediaDown
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Carregar configurações do .env
load_dotenv()

class BaseConfig:
    """Configuração base com valores seguros"""
    
    # ================================
    # CONFIGURAÇÕES CRÍTICAS
    # ================================
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', 
        'postgresql://media_user:CHANGE_PASSWORD@localhost/mediadownloader'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0
    }
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    API_KEY = os.getenv('API_KEY')
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
    
    # Validar chaves críticas
    if not SECRET_KEY or SECRET_KEY == 'your-secret-key-here-change-this':
        raise ValueError("SECRET_KEY deve ser definida com valor seguro!")
    
    if not JWT_SECRET_KEY or JWT_SECRET_KEY == 'your-jwt-secret-key-here-change-this':
        raise ValueError("JWT_SECRET_KEY deve ser definida com valor seguro!")
    
    # ================================
    # CONFIGURAÇÕES DE APLICAÇÃO
    # ================================
    
    # Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # Session
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = int(os.getenv('DEFAULT_SESSION_TIMEOUT', 3600))
    
    # ================================
    # CONFIGURAÇÕES DE DOWNLOAD
    # ================================
    
    # Qualidades aceitas
    ACCEPTED_QUALITIES = os.getenv('ACCEPTED_QUALITIES', '480p,720p,1080p').split(',')
    
    # Diretórios
    TEMP_DOWNLOAD_DIR = os.getenv('TEMP_DOWNLOAD_DIR', '/app/temp_downloads')
    UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/app/uploads')
    LOG_DIR = os.getenv('LOG_DIR', '/app/logs')
    
    # Limites
    MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', 3))
    MAX_CONCURRENT_TRANSFERS = int(os.getenv('MAX_CONCURRENT_TRANSFERS', 3))
    BANDWIDTH_LIMIT = os.getenv('BANDWIDTH_LIMIT', '100MB/s')
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 104857600))  # 100MB
    
    # Extensões permitidas
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'm3u,m3u8').split(','))
    
    # ================================
    # SERVIÇOS EXTERNOS
    # ================================
    
    # TMDB
    TMDB_API_KEY = os.getenv('TMDB_API_KEY')
    TMDB_LANGUAGE = os.getenv('TMDB_LANGUAGE', 'pt-BR')
    
    # Email/SMTP
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'
    
    # ================================
    # CONFIGURAÇÕES AVANÇADAS
    # ================================
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', 10485760))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 60))
    RATE_LIMIT_STORAGE_URL = REDIS_URL
    
    # Backup S3
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    S3_ACCESS_KEY_ID = os.getenv('S3_ACCESS_KEY_ID')
    S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')
    S3_REGION = os.getenv('S3_REGION', 'us-east-1')
    BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'False').lower() == 'true'
    BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', 30))
    
    # Monitoring
    PROMETHEUS_ENABLED = os.getenv('PROMETHEUS_ENABLED', 'False').lower() == 'true'
    PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', 9090))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', 30))
    
    # ================================
    # VALIDAÇÕES DE SEGURANÇA
    # ================================
    
    @classmethod
    def validate_security(cls):
        """Validar configurações de segurança"""
        errors = []
        warnings = []
        
        # Verificar chaves secretas
        if not cls.SECRET_KEY or len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY muito curta (mínimo 32 caracteres)")
        
        if not cls.JWT_SECRET_KEY or len(cls.JWT_SECRET_KEY) < 32:
            errors.append("JWT_SECRET_KEY muito curta (mínimo 32 caracteres)")
        
        # Verificar URLs de banco
        if not cls.SQLALCHEMY_DATABASE_URI.startswith(('postgresql://', 'sqlite://')):
            errors.append("DATABASE_URL formato inválido")
        
        if not cls.REDIS_URL.startswith('redis://'):
            errors.append("REDIS_URL formato inválido")
        
        # Verificar diretórios
        for dir_name, dir_path in [
            ('TEMP_DOWNLOAD_DIR', cls.TEMP_DOWNLOAD_DIR),
            ('UPLOAD_DIR', cls.UPLOAD_DIR),
            ('LOG_DIR', cls.LOG_DIR)
        ]:
            path = Path(dir_path)
            if not path.parent.exists():
                warnings.append(f"{dir_name} diretório pai não existe: {dir_path}")
        
        # Verificar configurações opcionais
        if not cls.TMDB_API_KEY or cls.TMDB_API_KEY == 'your_tmdb_api_key_here':
            warnings.append("TMDB_API_KEY não configurada")
        
        if not cls.SMTP_USERNAME or cls.SMTP_USERNAME == 'your_email@gmail.com':
            warnings.append("SMTP não configurado (email opcional)")
        
        return {
            'errors': errors,
            'warnings': warnings,
            'valid': len(errors) == 0
        }
    
    @classmethod
    def create_directories(cls):
        """Criar diretórios necessários"""
        directories = [
            cls.TEMP_DOWNLOAD_DIR,
            cls.UPLOAD_DIR,
            cls.LOG_DIR
        ]
        
        for directory in directories:
            path = Path(directory)
            try:
                path.mkdir(parents=True, exist_ok=True)
                # Definir permissões seguras
                os.chmod(path, 0o755)
                logging.info(f"Diretório criado/verificado: {directory}")
            except Exception as e:
                logging.error(f"Erro criando diretório {directory}: {e}")
                raise

class DevelopmentConfig(BaseConfig):
    """Configuração para desenvolvimento"""
    
    FLASK_DEBUG = True
    FLASK_ENV = 'development'
    SESSION_COOKIE_SECURE = False  # HTTP em desenvolvimento
    
    # Desenvolvimento específico
    DEV_AUTO_RELOAD = os.getenv('DEV_AUTO_RELOAD', 'True').lower() == 'true'
    DEV_SQL_ECHO = os.getenv('DEV_SQL_ECHO', 'False').lower() == 'true'
    DEV_PROFILER_ENABLED = os.getenv('DEV_PROFILER_ENABLED', 'False').lower() == 'true'
    
    # Database para desenvolvimento (pode usar SQLite)
    if os.getenv('DEV_USE_SQLITE', 'False').lower() == 'true':
        SQLALCHEMY_DATABASE_URI = 'sqlite:///mediadown_dev.db'

class ProductionConfig(BaseConfig):
    """Configuração para produção"""
    
    FLASK_DEBUG = False
    FLASK_ENV = 'production'
    SESSION_COOKIE_SECURE = True  # HTTPS obrigatório
    
    # Configurações específicas de produção
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size': 20,
        'max_overflow': 10
    }
    
    @classmethod
    def validate_production(cls):
        """Validações específicas para produção"""
        validation = cls.validate_security()
        errors = validation['errors']
        
        # Verificações adicionais para produção
        if cls.FLASK_DEBUG:
            errors.append("DEBUG não pode estar ativo em produção")
        
        if not cls.SESSION_COOKIE_SECURE:
            errors.append("Cookies devem ser seguros em produção (HTTPS)")
        
        if 'localhost' in cls.SQLALCHEMY_DATABASE_URI:
            errors.append("Database não pode ser localhost em produção")
        
        return {
            'errors': errors,
            'warnings': validation['warnings'],
            'valid': len(errors) == 0
        }

class TestingConfig(BaseConfig):
    """Configuração para testes"""
    
    TESTING = True
    FLASK_DEBUG = True
    
    # Database em memória para testes
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'TEST_DATABASE_URL', 
        'sqlite:///:memory:'
    )
    
    # Configurações de teste
    TEST_SKIP_AUTH = os.getenv('TEST_SKIP_AUTH', 'False').lower() == 'true'
    WTF_CSRF_ENABLED = False
    
    # Rate limiting desabilitado em testes
    RATE_LIMIT_ENABLED = False

# ================================
# SELEÇÃO DE CONFIGURAÇÃO
# ================================

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}

def get_config(env: str = None) -> BaseConfig:
    """Obter configuração baseada no ambiente"""
    if env is None:
        env = os.getenv('FLASK_ENV', 'production')
    
    config_class = config.get(env, config['default'])
    
    # Validar configuração
    validation = config_class.validate_security()
    
    if not validation['valid']:
        error_msg = "Erros de configuração encontrados:\n"
        for error in validation['errors']:
            error_msg += f"  - {error}\n"
        raise ValueError(error_msg)
    
    # Log warnings
    for warning in validation['warnings']:
        logging.warning(f"Configuração: {warning}")
    
    # Criar diretórios necessários
    try:
        config_class.create_directories()
    except Exception as e:
        logging.error(f"Erro criando diretórios: {e}")
        raise
    
    return config_class

# ================================
# UTILITÁRIOS
# ================================

def is_production() -> bool:
    """Verificar se está em produção"""
    return os.getenv('FLASK_ENV', 'production') == 'production'

def is_development() -> bool:
    """Verificar se está em desenvolvimento"""
    return os.getenv('FLASK_ENV', 'production') == 'development'

def get_app_version() -> str:
    """Obter versão da aplicação"""
    return os.getenv('APP_VERSION', '1.0.0')

def setup_logging():
    """Configurar logging baseado na configuração"""
    config_obj = get_config()
    
    log_level = getattr(logging, config_obj.LOG_LEVEL.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{config_obj.LOG_DIR}/app.log")
        ]
    )