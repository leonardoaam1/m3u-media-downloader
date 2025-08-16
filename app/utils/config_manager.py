#!/usr/bin/env python3
"""
Sistema seguro de gerenciamento de configurações
"""

import os
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import base64

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """Exceção para erros de configuração"""
    pass

class ConfigValidator:
    """Validador de configurações"""
    
    @staticmethod
    def validate_database_url(url: str) -> bool:
        """Validar URL do banco de dados"""
        if not url:
            return False
        
        # Verificar formato básico PostgreSQL
        if url.startswith('postgresql://') or url.startswith('postgres://'):
            return True
        
        # Verificar formato SQLite para testes
        if url.startswith('sqlite://'):
            return True
            
        return False
    
    @staticmethod
    def validate_redis_url(url: str) -> bool:
        """Validar URL do Redis"""
        return url and url.startswith('redis://')
    
    @staticmethod
    def validate_secret_key(key: str) -> bool:
        """Validar chave secreta"""
        return key and len(key) >= 32 and key != 'your-secret-key-here-change-this'
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validar formato de email"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_path(path: str) -> bool:
        """Validar se o caminho é válido"""
        try:
            Path(path).resolve()
            return True
        except:
            return False
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """Validar número da porta"""
        return 1 <= port <= 65535

class SecureConfigManager:
    """Gerenciador seguro de configurações"""
    
    def __init__(self, env_file: Optional[str] = None):
        self.env_file = env_file or '.env'
        self.encryption_key = None
        self._config_cache = {}
        
        # Carregar arquivo .env se existir
        if Path(self.env_file).exists():
            load_dotenv(self.env_file)
        
        # Inicializar chave de criptografia
        self._init_encryption()
    
    def _init_encryption(self):
        """Inicializar sistema de criptografia"""
        key_file = Path('.encryption_key')
        
        if key_file.exists():
            try:
                with open(key_file, 'rb') as f:
                    self.encryption_key = f.read()
            except Exception as e:
                logger.warning(f"Erro carregando chave de criptografia: {e}")
                self._generate_encryption_key()
        else:
            self._generate_encryption_key()
    
    def _generate_encryption_key(self):
        """Gerar nova chave de criptografia"""
        self.encryption_key = Fernet.generate_key()
        
        try:
            with open('.encryption_key', 'wb') as f:
                f.write(self.encryption_key)
            
            # Definir permissões restritivas
            os.chmod('.encryption_key', 0o600)
            logger.info("Nova chave de criptografia gerada")
        except Exception as e:
            logger.error(f"Erro salvando chave de criptografia: {e}")
    
    def encrypt_value(self, value: str) -> str:
        """Criptografar valor"""
        if not self.encryption_key:
            raise ConfigurationError("Chave de criptografia não disponível")
        
        fernet = Fernet(self.encryption_key)
        encrypted = fernet.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Descriptografar valor"""
        if not self.encryption_key:
            raise ConfigurationError("Chave de criptografia não disponível")
        
        try:
            fernet = Fernet(self.encryption_key)
            encrypted_bytes = base64.b64decode(encrypted_value.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Erro descriptografando valor: {e}")
            raise ConfigurationError("Erro na descriptografia")
    
    def get(self, key: str, default: Any = None, required: bool = False, 
            encrypted: bool = False) -> Any:
        """Obter valor de configuração"""
        
        # Cache primeiro
        if key in self._config_cache:
            return self._config_cache[key]
        
        # Obter do ambiente
        value = os.getenv(key, default)
        
        if required and value is None:
            raise ConfigurationError(f"Configuração obrigatória ausente: {key}")
        
        if value is None:
            return default
        
        # Descriptografar se necessário
        if encrypted and value != default:
            try:
                value = self.decrypt_value(value)
            except:
                if required:
                    raise ConfigurationError(f"Erro descriptografando {key}")
                logger.warning(f"Usando valor padrão para {key} devido a erro de descriptografia")
                value = default
        
        # Cache do valor
        self._config_cache[key] = value
        return value
    
    def get_int(self, key: str, default: int = 0, required: bool = False) -> int:
        """Obter valor inteiro"""
        value = self.get(key, str(default), required)
        try:
            return int(value)
        except ValueError:
            if required:
                raise ConfigurationError(f"Valor inválido para {key}: deve ser um número")
            return default
    
    def get_bool(self, key: str, default: bool = False, required: bool = False) -> bool:
        """Obter valor booleano"""
        value = self.get(key, str(default), required)
        return str(value).lower() in ('true', '1', 'yes', 'on')
    
    def get_list(self, key: str, default: List[str] = None, 
                 separator: str = ',', required: bool = False) -> List[str]:
        """Obter lista de valores"""
        if default is None:
            default = []
        
        value = self.get(key, separator.join(default), required)
        if not value:
            return default
        
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    def validate_config(self) -> Dict[str, List[str]]:
        """Validar todas as configurações"""
        errors = {}
        warnings = []
        
        # Validações críticas
        database_url = self.get('DATABASE_URL')
        if not ConfigValidator.validate_database_url(database_url):
            errors.setdefault('critical', []).append('DATABASE_URL inválida')
        
        redis_url = self.get('REDIS_URL')
        if not ConfigValidator.validate_redis_url(redis_url):
            errors.setdefault('critical', []).append('REDIS_URL inválida')
        
        secret_key = self.get('SECRET_KEY')
        if not ConfigValidator.validate_secret_key(secret_key):
            errors.setdefault('critical', []).append('SECRET_KEY insegura ou padrão')
        
        jwt_secret = self.get('JWT_SECRET_KEY')
        if not ConfigValidator.validate_secret_key(jwt_secret):
            errors.setdefault('critical', []).append('JWT_SECRET_KEY insegura ou padrão')
        
        # Validações importantes
        port = self.get_int('PORT', 5000)
        if not ConfigValidator.validate_port(port):
            errors.setdefault('important', []).append(f'PORT inválida: {port}')
        
        temp_dir = self.get('TEMP_DOWNLOAD_DIR')
        if not ConfigValidator.validate_path(temp_dir):
            errors.setdefault('important', []).append('TEMP_DOWNLOAD_DIR inválido')
        
        upload_dir = self.get('UPLOAD_DIR')
        if not ConfigValidator.validate_path(upload_dir):
            errors.setdefault('important', []).append('UPLOAD_DIR inválido')
        
        # Validações opcionais
        smtp_username = self.get('SMTP_USERNAME')
        if smtp_username and smtp_username != 'your_email@gmail.com':
            if not ConfigValidator.validate_email(smtp_username):
                warnings.append('SMTP_USERNAME formato inválido')
        
        tmdb_key = self.get('TMDB_API_KEY')
        if not tmdb_key or tmdb_key == 'your_tmdb_api_key_here':
            warnings.append('TMDB_API_KEY não configurada')
        
        return {
            'errors': errors,
            'warnings': warnings,
            'valid': len(errors) == 0
        }
    
    def generate_secure_defaults(self) -> Dict[str, str]:
        """Gerar valores padrão seguros"""
        return {
            'SECRET_KEY': secrets.token_urlsafe(64),
            'JWT_SECRET_KEY': secrets.token_urlsafe(64),
            'API_KEY': secrets.token_urlsafe(32),
            'WEBHOOK_SECRET': secrets.token_urlsafe(32),
            'ENCRYPTION_KEY': base64.b64encode(Fernet.generate_key()).decode()
        }
    
    def create_secure_env_template(self) -> str:
        """Criar template .env seguro"""
        secure_defaults = self.generate_secure_defaults()
        
        template = f"""# MediaDown - Configuração Segura
# IMPORTANTE: Altere todos os valores padrão antes de usar em produção!

# ================================
# CONFIGURAÇÕES CRÍTICAS
# ================================

# Database Configuration
DATABASE_URL=postgresql://media_user:CHANGE_PASSWORD@localhost/mediadownloader
REDIS_URL=redis://localhost:6379/0

# Security Keys (OBRIGATÓRIO ALTERAR!)
SECRET_KEY={secure_defaults['SECRET_KEY']}
JWT_SECRET_KEY={secure_defaults['JWT_SECRET_KEY']}
API_KEY={secure_defaults['API_KEY']}
WEBHOOK_SECRET={secure_defaults['WEBHOOK_SECRET']}

# ================================
# CONFIGURAÇÕES DE APLICAÇÃO
# ================================

# Environment
FLASK_ENV=production
FLASK_DEBUG=False
HOST=0.0.0.0
PORT=5000

# Download Settings
ACCEPTED_QUALITIES=480p,720p,1080p
TEMP_DOWNLOAD_DIR=/app/temp_downloads
UPLOAD_DIR=/app/uploads
MAX_CONCURRENT_DOWNLOADS=3
MAX_CONCURRENT_TRANSFERS=3
BANDWIDTH_LIMIT=100MB/s

# ================================
# SERVIÇOS EXTERNOS
# ================================

# TMDB Configuration
TMDB_API_KEY=your_tmdb_api_key_here
TMDB_LANGUAGE=pt-BR

# Email Settings (Opcional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_USE_TLS=True

# ================================
# CONFIGURAÇÕES AVANÇADAS
# ================================

# Logging
LOG_LEVEL=INFO
LOG_DIR=/app/logs
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5

# Security
DEFAULT_SESSION_TIMEOUT=3600
MAX_FILE_SIZE=104857600
ALLOWED_EXTENSIONS=m3u,m3u8
RATE_LIMIT_ENABLED=True
RATE_LIMIT_PER_MINUTE=60

# Backup (S3)
S3_BUCKET_NAME=your-backup-bucket
S3_ACCESS_KEY_ID=your-access-key
S3_SECRET_ACCESS_KEY=your-secret-key
S3_REGION=us-east-1
BACKUP_ENABLED=False
BACKUP_RETENTION_DAYS=30

# Monitoring
PROMETHEUS_ENABLED=False
PROMETHEUS_PORT=9090
HEALTH_CHECK_INTERVAL=30

# ================================
# CONFIGURAÇÕES DE DESENVOLVIMENTO
# ================================

# Development only (set FLASK_ENV=development)
DEV_AUTO_RELOAD=True
DEV_SQL_ECHO=False
DEV_PROFILER_ENABLED=False

# Testing
TEST_DATABASE_URL=sqlite:///:memory:
TEST_SKIP_AUTH=False
"""
        return template
    
    def setup_secure_config(self, force: bool = False) -> bool:
        """Configurar ambiente com configurações seguras"""
        env_path = Path(self.env_file)
        
        if env_path.exists() and not force:
            logger.info("Arquivo .env já existe. Use force=True para sobrescrever.")
            return False
        
        try:
            # Gerar template seguro
            template = self.create_secure_env_template()
            
            # Salvar arquivo
            with open(env_path, 'w') as f:
                f.write(template)
            
            # Definir permissões restritivas
            os.chmod(env_path, 0o600)
            
            logger.info(f"Arquivo {self.env_file} criado com configurações seguras")
            logger.warning("IMPORTANTE: Altere as configurações padrão antes de usar em produção!")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro criando arquivo de configuração: {e}")
            return False

# Instância global do gerenciador
config_manager = SecureConfigManager()

def get_secure_config(key: str, default: Any = None, **kwargs) -> Any:
    """Função helper para obter configuração segura"""
    return config_manager.get(key, default, **kwargs)

def validate_current_config() -> Dict[str, Any]:
    """Validar configuração atual"""
    return config_manager.validate_config()

def setup_environment(force: bool = False) -> bool:
    """Configurar ambiente seguro"""
    return config_manager.setup_secure_config(force)
