# Documentação Técnica - Sistema de Download de Vídeos M3U

## Arquitetura do Sistema

### Visão Geral
O sistema é construído seguindo uma arquitetura modular baseada em Flask, com separação clara entre camadas de apresentação, lógica de negócio e persistência de dados.

### Stack Tecnológico
```
Backend:
├── Flask 3.0.0 (Web Framework)
├── SQLAlchemy 2.0.25 (ORM)
├── Celery 5.3.4 (Task Queue)
├── Redis 7.2.10 (Cache/Broker)
├── PostgreSQL 16 (Database)
└── yt-dlp 2025.7.21 (Download Engine)

Infraestrutura:
├── Nginx 1.24.0 (Reverse Proxy)
├── Gunicorn 21.2.0 (WSGI Server)
├── Supervisor 3.0.6 (Process Manager)
└── Let's Encrypt (SSL)

Protocolos de Transferência:
├── SFTP (Paramiko)
├── NFS (Mount)
├── SMB/CIFS (pysmb)
└── Rsync (subprocess)
```

## Estrutura de Dados

### Modelos do Banco de Dados

#### User (Usuários)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'operator', 'viewer') DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Server (Servidores de Destino)
```sql
CREATE TABLE servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    host VARCHAR(255) NOT NULL,
    protocol ENUM('sftp', 'nfs', 'smb', 'rsync') NOT NULL,
    port INTEGER NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255),
    ssh_key_path VARCHAR(500),
    base_path VARCHAR(500) NOT NULL,
    content_types TEXT NOT NULL, -- JSON array
    auto_suggest BOOLEAN DEFAULT TRUE,
    min_quality VARCHAR(20) DEFAULT '480p',
    max_quality VARCHAR(20) DEFAULT '1080p',
    accepted_qualities TEXT NOT NULL, -- JSON array
    directory_structure TEXT NOT NULL, -- JSON object
    cleanup_after_transfer BOOLEAN DEFAULT TRUE,
    max_concurrent_transfers INTEGER DEFAULT 3,
    bandwidth_limit VARCHAR(20) DEFAULT '100MB/s',
    status ENUM('online', 'offline', 'maintenance', 'error') DEFAULT 'offline',
    last_check TIMESTAMP,
    disk_usage TEXT DEFAULT '{}', -- JSON object
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Download (Downloads)
```sql
CREATE TABLE downloads (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    original_title VARCHAR(255),
    content_type VARCHAR(50) NOT NULL,
    season INTEGER,
    episode INTEGER,
    episode_title VARCHAR(255),
    year INTEGER,
    quality VARCHAR(20) NOT NULL,
    url TEXT NOT NULL,
    tmdb_id INTEGER,
    tmdb_title VARCHAR(255),
    tmdb_poster VARCHAR(500),
    tmdb_genre VARCHAR(100),
    tmdb_platform VARCHAR(100),
    file_size BIGINT,
    downloaded_size BIGINT DEFAULT 0,
    download_path VARCHAR(500),
    filename VARCHAR(255),
    server_id INTEGER REFERENCES servers(id),
    destination_path VARCHAR(500) NOT NULL,
    status ENUM('pending', 'downloading', 'downloaded', 'transferring', 'completed', 'failed', 'paused', 'cancelled') DEFAULT 'pending',
    priority ENUM('low', 'medium', 'high') DEFAULT 'medium',
    progress_percentage FLOAT DEFAULT 0.0,
    download_speed VARCHAR(20),
    estimated_time VARCHAR(20),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id),
    error_message TEXT,
    error_details TEXT -- JSON object
);
```

### Logs Estruturados

#### SystemLog
```sql
CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level ENUM('debug', 'info', 'warning', 'error', 'critical') NOT NULL,
    message TEXT NOT NULL,
    details TEXT, -- JSON object
    source VARCHAR(100),
    session_id VARCHAR(100),
    ip_address VARCHAR(45)
);
```

#### UserActivityLog
```sql
CREATE TABLE user_activity_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    details TEXT, -- JSON object
    session_id VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent VARCHAR(500)
);
```

## Fluxo de Processamento

### 1. Upload e Processamento de Lista M3U

```mermaid
graph TD
    A[Upload Lista M3U] --> B[Parser M3U]
    B --> C[Extract Metadata]
    C --> D[Quality Filter]
    D --> E[Compare with Main List]
    E --> F[Show Differences]
    F --> G[User Selection]
    G --> H[Create Download Objects]
    H --> I[Add to Queue]
```

#### Parser M3U
```python
def parse_m3u_file(file_path: str) -> List[Dict]:
    """
    Parse M3U file and extract:
    - Title and metadata
    - Content type (movie/series/novela)
    - Season/episode information
    - Quality detection
    - Year extraction
    """
```

#### Quality Filter
```python
def _is_acceptable_quality(quality: str) -> bool:
    """
    Filter qualities:
    - Accept: 480p, 720p, 1080p
    - Reject: < 480p, > 4K
    """
```

### 2. Sistema de Fila de Downloads

#### Priorização Inteligente
```python
def _determine_priority(item: Dict) -> DownloadPriority:
    """
    Priority logic:
    - HIGH: Recent movies (last 2 years)
    - MEDIUM: Series, novelas, older movies
    - LOW: Old content (> 5 years)
    """
```

#### Processamento Paralelo
```python
@celery.task
def download_task(download_id: int):
    """
    Download process:
    1. Update status to DOWNLOADING
    2. Configure yt-dlp options
    3. Download with progress tracking
    4. Update database with results
    5. Trigger transfer task
    """
```

### 3. Sistema de Transferência

#### Protocolos Suportados

##### SFTP (Paramiko)
```python
def transfer_sftp(server, source, destination, callback):
    """
    SFTP transfer with:
    - Progress tracking
    - Resume capability
    - Directory creation
    - Error handling
    """
```

##### NFS (Mount)
```python
def transfer_nfs(server, source, destination, callback):
    """
    NFS transfer:
    - Direct file copy
    - High performance
    - Local mount required
    """
```

##### SMB/CIFS (pysmb)
```python
def transfer_smb(server, source, destination, callback):
    """
    SMB transfer:
    - Windows compatibility
    - Share-based access
    - Authentication support
    """
```

##### Rsync
```python
def transfer_rsync(server, source, destination, callback):
    """
    Rsync transfer:
    - Incremental sync
    - Resume capability
    - Bandwidth control
    """
```

### 4. Integração TMDB

#### Busca de Metadados
```python
def search_content(title: str, content_type: str, year: int = None):
    """
    TMDB integration:
    1. Cache check
    2. API search (movies/TV)
    3. Fuzzy matching
    4. Metadata extraction
    5. Cache storage
    """
```

#### Cache Strategy
```python
cache_config = {
    'ttl': 3600,  # 1 hour
    'max_size': 1000,
    'eviction_policy': 'lru'
}
```

## Monitoramento e Logs

### Sistema de Logs Estruturado

#### Níveis de Log
- **DEBUG**: Informações técnicas detalhadas
- **INFO**: Operações normais
- **WARNING**: Situações que precisam atenção
- **ERROR**: Erros recuperáveis
- **CRITICAL**: Erros que param o sistema

#### Formato JSON
```json
{
  "timestamp": "2025-07-21T10:30:00Z",
  "level": "INFO",
  "user": "admin@system.com",
  "action": "download_started",
  "details": {
    "title": "Movie Name (2023)",
    "url": "https://...",
    "file_size": "2.5GB",
    "estimated_time": "45min"
  },
  "session_id": "abc123",
  "ip_address": "192.168.1.100"
}
```

### Monitoramento de Servidores

#### Health Check
```python
def check_server_status(server: Server):
    """
    Server monitoring:
    1. Connection test
    2. Response time measurement
    3. Disk usage check
    4. Status update
    5. Log generation
    """
```

#### Métricas Coletadas
- Status de conectividade
- Tempo de resposta
- Uso de disco
- Taxa de transferência
- Erros de conexão

## Segurança

### Autenticação e Autorização

#### Hash de Senhas
```python
def set_password(self, password):
    """bcrypt hash with salt"""
    self.password_hash = generate_password_hash(password)
```

#### Sistema de Roles
```python
permissions = {
    'admin': [
        'manage_users', 'manage_servers', 'manage_system',
        'view_all_logs', 'control_queues', 'manage_backups'
    ],
    'operator': [
        'upload_m3u', 'manage_downloads', 'select_server',
        'pause_resume_downloads', 'view_progress'
    ],
    'viewer': [
        'view_progress', 'view_library', 'search_content'
    ]
}
```

### Validação de Entrada
```python
def validate_m3u_upload(file):
    """
    Upload validation:
    1. File type check
    2. Size limit
    3. Content validation
    4. Malware scan
    """
```

## Performance e Otimização

### Cache Strategy
- **TMDB API**: 1 hora TTL
- **Server Status**: 5 minutos
- **User Sessions**: Configurável
- **Download Progress**: Real-time

### Database Optimization
```sql
-- Indexes for performance
CREATE INDEX idx_downloads_status ON downloads(status);
CREATE INDEX idx_downloads_priority ON downloads(priority);
CREATE INDEX idx_downloads_created_at ON downloads(created_at);
CREATE INDEX idx_logs_timestamp ON system_logs(timestamp);
CREATE INDEX idx_logs_level ON system_logs(level);
```

### Concurrency Control
```python
# Download queue management
MAX_CONCURRENT_DOWNLOADS = 3
MAX_CONCURRENT_TRANSFERS = 3

# Database connection pooling
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}
```

## Backup e Recuperação

### Database Backup
```bash
# Automated backup script
pg_dump -U media_user -h localhost mediadownloader | gzip > backup_$(date +%Y%m%d).sql.gz
```

### File Backup Strategy
```python
backup_config = {
    'database': {
        'frequency': 'daily',
        'retention': '30 days',
        'compression': True
    },
    'logs': {
        'frequency': 'weekly',
        'retention': '90 days',
        'compression': True
    },
    'config': {
        'frequency': 'on_change',
        'retention': 'unlimited'
    }
}
```

## Troubleshooting

### Problemas Comuns

#### Downloads Falhando
```bash
# Check logs
tail -f logs/celery.log

# Check disk space
df -h temp_downloads/

# Check yt-dlp
yt-dlp --version

# Test URL manually
yt-dlp --dry-run "URL"
```

#### Transferências Falhando
```bash
# Test server connectivity
flask test-servers

# Check server logs
tail -f logs/transfer.log

# Verify credentials
ssh user@server "echo test"
```

#### Performance Issues
```bash
# Check system resources
htop
iotop
nethogs

# Check database performance
psql -c "SELECT * FROM pg_stat_activity;"

# Check Redis
redis-cli info memory
```

## API Endpoints

### REST API

#### Downloads
```
GET    /api/downloads          # List downloads
POST   /api/downloads          # Create download
GET    /api/downloads/{id}     # Get download
PUT    /api/downloads/{id}     # Update download
DELETE /api/downloads/{id}     # Delete download
```

#### Servers
```
GET    /api/servers            # List servers
POST   /api/servers            # Create server
GET    /api/servers/{id}       # Get server
PUT    /api/servers/{id}       # Update server
DELETE /api/servers/{id}       # Delete server
POST   /api/servers/{id}/test  # Test connection
```

#### Statistics
```
GET    /api/stats              # System statistics
GET    /api/stats/downloads    # Download statistics
GET    /api/stats/servers      # Server statistics
GET    /api/stats/users        # User statistics
```

## Configuração de Produção

### Environment Variables
```bash
# Required
DATABASE_URL=postgresql://user:pass@host/db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key

# Optional
FLASK_ENV=production
LOG_LEVEL=INFO
MAX_CONCURRENT_DOWNLOADS=3
TMDB_API_KEY=your-api-key
```

### Process Management
```ini
[supervisord]
nodaemon=true
user=www-data

[program:mediadownloader]
command=gunicorn --bind 0.0.0.0:5000 --workers 4 wsgi:app
directory=/path/to/app
autostart=true
autorestart=true
```

### Monitoring
```python
# Health check endpoint
@app.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'database': check_db_connection(),
        'redis': check_redis_connection(),
        'servers': check_servers_status()
    }
```

## Desenvolvimento

### Setup de Desenvolvimento
```bash
# Clone repository
git clone <repo>
cd mediadown

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup database
flask init-db

# Run development server
python app.py
```

### Testing
```bash
# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=app tests/

# Run specific test
python -m pytest tests/test_m3u_parser.py::test_parse_file
```

### Code Quality
```bash
# Linting
flake8 app/ tests/

# Type checking
mypy app/

# Security check
bandit -r app/
```

---

**Documentação Técnica v1.0 - Sistema de Download de Vídeos M3U**








