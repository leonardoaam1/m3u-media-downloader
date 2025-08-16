# 🚀 MediaDown - Guia de Deployment em Produção

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Requisitos do Sistema](#requisitos-do-sistema)
3. [Preparação do Ambiente](#preparação-do-ambiente)
4. [Instalação e Configuração](#instalação-e-configuração)
5. [Configuração de Serviços](#configuração-de-serviços)
6. [Deployment com Docker](#deployment-com-docker)
7. [Configuração de Segurança](#configuração-de-segurança)
8. [Monitoramento e Logs](#monitoramento-e-logs)
9. [Backup e Recuperação](#backup-e-recuperação)
10. [Troubleshooting](#troubleshooting)

## 🔍 Visão Geral

O MediaDown é um sistema completo para automação de downloads de vídeos baseado em listas M3U. Este guia fornece instruções detalhadas para deployment em ambiente de produção.

### Arquitetura do Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │────│  Flask App      │────│   PostgreSQL    │
│ (Reverse Proxy) │    │  (Gunicorn)     │    │   (Database)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐             │
         │              │     Redis       │─────────────┘
         │              │  (Cache/Queue)  │
         │              └─────────────────┘
         │                       │
┌─────────────────┐    ┌─────────────────┐
│   Static Files  │    │  Celery Workers │
│   (CSS/JS/IMG)  │    │ (Download Tasks)│
└─────────────────┘    └─────────────────┘
```

## 💻 Requisitos do Sistema

### Hardware Mínimo
- **CPU**: 4 cores (8 recomendado)
- **RAM**: 8GB (16GB recomendado)
- **Armazenamento**: 100GB SSD (500GB+ recomendado)
- **Rede**: 100Mbps (1Gbps recomendado)

### Software
- **SO**: Ubuntu 22.04 LTS / CentOS 8+ / RHEL 8+
- **Python**: 3.10+ (3.11 recomendado)
- **PostgreSQL**: 14+ (15 recomendado)
- **Redis**: 6.2+ (7.0 recomendado)
- **Nginx**: 1.20+
- **Supervisor**: 4.0+

## 🛠️ Preparação do Ambiente

### 1. Atualização do Sistema

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo dnf update -y
```

### 2. Instalação de Dependências Base

```bash
# Ubuntu/Debian
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib redis-server nginx supervisor \
    build-essential curl wget git ffmpeg

# CentOS/RHEL
sudo dnf install -y python3.11 python3.11-devel postgresql-server \
    postgresql-contrib redis nginx supervisor gcc gcc-c++ \
    curl wget git ffmpeg
```

### 3. Configuração de Usuário

```bash
# Criar usuário dedicado
sudo adduser --system --group --home /opt/mediadown mediadown

# Adicionar ao grupo www-data (Ubuntu) ou nginx (CentOS)
sudo usermod -a -G www-data mediadown  # Ubuntu
sudo usermod -a -G nginx mediadown     # CentOS
```

## 📦 Instalação e Configuração

### 1. Clone do Repositório

```bash
sudo -u mediadown git clone https://github.com/seu-usuario/mediadown.git /opt/mediadown
cd /opt/mediadown
```

### 2. Configuração do Python Virtual Environment

```bash
sudo -u mediadown python3.11 -m venv venv
sudo -u mediadown venv/bin/pip install --upgrade pip setuptools wheel
sudo -u mediadown venv/bin/pip install -r requirements.txt
```

### 3. Configuração do Banco de Dados

```bash
# Inicializar PostgreSQL (se necessário)
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Criar database e usuário
sudo -u postgres psql << EOF
CREATE DATABASE mediadownloader;
CREATE USER media_user WITH ENCRYPTED PASSWORD 'SuaSenhaSegura123!';
GRANT ALL PRIVILEGES ON DATABASE mediadownloader TO media_user;
ALTER USER media_user CREATEDB;
\q
EOF
```

### 4. Configuração do Redis

```bash
sudo systemctl enable redis
sudo systemctl start redis

# Configurar Redis para produção
sudo nano /etc/redis/redis.conf
```

**Configurações recomendadas para Redis:**

```
# Segurança
bind 127.0.0.1
protected-mode yes
requirepass SuaSenhaRedisSegura123!

# Performance
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000

# Logs
loglevel notice
logfile /var/log/redis/redis-server.log
```

### 5. Configuração do Ambiente

```bash
# Copiar arquivo de configuração
sudo -u mediadown cp env.example .env

# Editar configurações
sudo -u mediadown nano .env
```

**Arquivo `.env` de produção:**

```env
# Environment
FLASK_ENV=production
FLASK_DEBUG=False

# Database
DATABASE_URL=postgresql://media_user:SuaSenhaSegura123!@localhost/mediadownloader

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=SuaSenhaRedisSegura123!

# Security
SECRET_KEY=sua-chave-secreta-super-complexa-aqui-256-bits
JWT_SECRET_KEY=sua-chave-jwt-diferente-e-segura-256-bits
API_KEY=sua-api-key-para-integracoes-externas
WEBHOOK_SECRET=sua-chave-webhook-para-assinaturas

# Application
ACCEPTED_QUALITIES=480p,720p,1080p
TEMP_DOWNLOAD_DIR=/opt/mediadown/temp_downloads
UPLOAD_DIR=/opt/mediadown/uploads
LOG_LEVEL=INFO

# TMDB API
TMDB_API_KEY=sua-chave-tmdb-aqui

# Rate Limiting
RATE_LIMITING_ENABLED=True
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# Monitoring
REDIS_METRICS_DB=2
ENABLE_METRICS=True

# Email (opcional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-app
MAIL_DEFAULT_SENDER=seu-email@gmail.com
```

### 6. Inicialização do Banco de Dados

```bash
cd /opt/mediadown
sudo -u mediadown venv/bin/python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Database initialized successfully')
"

# Criar usuário administrador
sudo -u mediadown venv/bin/python create_admin.py
```

### 7. Criação de Diretórios

```bash
# Criar diretórios necessários
sudo -u mediadown mkdir -p /opt/mediadown/{temp_downloads,uploads,logs}
sudo chmod 750 /opt/mediadown/{temp_downloads,uploads,logs}

# Configurar logs
sudo mkdir -p /var/log/mediadown
sudo chown mediadown:mediadown /var/log/mediadown
sudo chmod 755 /var/log/mediadown
```

## ⚙️ Configuração de Serviços

### 1. Gunicorn (WSGI Server)

**Arquivo: `/opt/mediadown/gunicorn.conf.py`**

```python
# Gunicorn configuration for production

bind = "127.0.0.1:5000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/mediadown/gunicorn_access.log"
errorlog = "/var/log/mediadown/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "mediadown"

# Server mechanics
daemon = False
pidfile = "/var/run/mediadown/gunicorn.pid"
user = "mediadown"
group = "mediadown"
tmp_upload_dir = None

# SSL (se usando HTTPS direto no Gunicorn)
# keyfile = "/path/to/ssl/private.key"
# certfile = "/path/to/ssl/certificate.crt"

# Worker processes
preload_app = True
worker_tmp_dir = "/dev/shm"

# Performance tuning
max_requests_jitter = 50
worker_rlimit_nofile = 65535
```

### 2. Supervisor (Process Manager)

**Arquivo: `/etc/supervisor/conf.d/mediadown.conf`**

```ini
[group:mediadown]
programs=mediadown-web,mediadown-worker,mediadown-beat

[program:mediadown-web]
command=/opt/mediadown/venv/bin/gunicorn -c /opt/mediadown/gunicorn.conf.py wsgi:app
directory=/opt/mediadown
user=mediadown
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadown/web.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=3
environment=PATH="/opt/mediadown/venv/bin"

[program:mediadown-worker]
command=/opt/mediadown/venv/bin/celery -A workers.celery_app worker --loglevel=info --concurrency=4
directory=/opt/mediadown
user=mediadown
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadown/worker.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=3
environment=PATH="/opt/mediadown/venv/bin"
startsecs=10
stopwaitsecs=60
stopasgroup=true

[program:mediadown-beat]
command=/opt/mediadown/venv/bin/celery -A workers.celery_app beat --loglevel=info
directory=/opt/mediadown
user=mediadown
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadown/beat.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=3
environment=PATH="/opt/mediadown/venv/bin"
startsecs=10
```

### 3. Nginx (Reverse Proxy)

**Arquivo: `/etc/nginx/sites-available/mediadown`**

```nginx
upstream mediadown_app {
    server 127.0.0.1:5000;
    keepalive 32;
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general:10m rate=20r/s;

server {
    listen 80;
    server_name seu-dominio.com www.seu-dominio.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seu-dominio.com www.seu-dominio.com;
    
    # SSL Configuration
    ssl_certificate /path/to/ssl/certificate.crt;
    ssl_certificate_key /path/to/ssl/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'";
    
    # General settings
    client_max_body_size 100M;
    client_body_timeout 120s;
    client_header_timeout 120s;
    
    # Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
    
    # Static files
    location /static/ {
        alias /opt/mediadown/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        gzip_static on;
    }
    
    # Rate limiting for authentication
    location /auth/ {
        limit_req zone=auth burst=5 nodelay;
        include proxy_params;
        proxy_pass http://mediadown_app;
    }
    
    # Rate limiting for API
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        include proxy_params;
        proxy_pass http://mediadown_app;
    }
    
    # General rate limiting
    location / {
        limit_req zone=general burst=50 nodelay;
        include proxy_params;
        proxy_pass http://mediadown_app;
    }
    
    # WebSocket support (se necessário)
    location /socket.io/ {
        include proxy_params;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_pass http://mediadown_app;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Deny access to sensitive files
    location ~ /\. {
        deny all;
    }
    
    location ~ \.(env|ini|conf)$ {
        deny all;
    }
    
    # Error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
}

# Proxy parameters
# /etc/nginx/proxy_params
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Port $server_port;
proxy_buffering off;
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;
```

**Ativar site:**

```bash
sudo ln -s /etc/nginx/sites-available/mediadown /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Systemd Services (Alternativa ao Supervisor)

**Arquivo: `/etc/systemd/system/mediadown-web.service`**

```ini
[Unit]
Description=MediaDown Web Application
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=mediadown
Group=mediadown
WorkingDirectory=/opt/mediadown
Environment=PATH=/opt/mediadown/venv/bin
ExecStart=/opt/mediadown/venv/bin/gunicorn -c /opt/mediadown/gunicorn.conf.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Arquivo: `/etc/systemd/system/mediadown-worker.service`**

```ini
[Unit]
Description=MediaDown Celery Worker
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=mediadown
Group=mediadown
WorkingDirectory=/opt/mediadown
Environment=PATH=/opt/mediadown/venv/bin
ExecStart=/opt/mediadown/venv/bin/celery -A workers.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

### 5. Logrotate Configuration

**Arquivo: `/etc/logrotate.d/mediadown`**

```
/var/log/mediadown/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 0644 mediadown mediadown
    postrotate
        supervisorctl restart mediadown:*
    endscript
}
```

## 🐳 Deployment com Docker

### 1. Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash mediadown

# Set work directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .
RUN chown -R mediadown:mediadown /app

# Create necessary directories
USER mediadown
RUN mkdir -p temp_downloads uploads logs

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start command
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
```

### 2. Docker Compose

**Arquivo: `docker-compose.prod.yml`**

```yaml
version: '3.8'

services:
  app:
    build: .
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://mediauser:${POSTGRES_PASSWORD}@db:5432/mediadownloader
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./temp_downloads:/app/temp_downloads
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    depends_on:
      - db
      - redis
    networks:
      - mediadown-network

  worker:
    build: .
    restart: unless-stopped
    command: celery -A workers.celery_app worker --loglevel=info --concurrency=4
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://mediauser:${POSTGRES_PASSWORD}@db:5432/mediadownloader
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./temp_downloads:/app/temp_downloads
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    depends_on:
      - db
      - redis
    networks:
      - mediadown-network

  beat:
    build: .
    restart: unless-stopped
    command: celery -A workers.celery_app beat --loglevel=info
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://mediauser:${POSTGRES_PASSWORD}@db:5432/mediadownloader
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    networks:
      - mediadown-network

  db:
    image: postgres:15
    restart: unless-stopped
    environment:
      - POSTGRES_DB=mediadownloader
      - POSTGRES_USER=mediauser
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    networks:
      - mediadown-network

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - mediadown-network

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./app/static:/var/www/static:ro
    depends_on:
      - app
    networks:
      - mediadown-network

volumes:
  postgres_data:
  redis_data:

networks:
  mediadown-network:
    driver: bridge
```

### 3. Inicialização com Docker

```bash
# Criar arquivo de environment
echo "POSTGRES_PASSWORD=sua-senha-segura" > .env
echo "REDIS_PASSWORD=sua-senha-redis" >> .env

# Build e start
docker-compose -f docker-compose.prod.yml up -d

# Inicializar database
docker-compose -f docker-compose.prod.yml exec app python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
"

# Criar admin user
docker-compose -f docker-compose.prod.yml exec app python create_admin.py
```

## 🔒 Configuração de Segurança

### 1. Firewall (UFW)

```bash
# Configurar firewall
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable

# Verificar status
sudo ufw status verbose
```

### 2. SSL/TLS com Let's Encrypt

```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx

# Obter certificado
sudo certbot --nginx -d seu-dominio.com -d www.seu-dominio.com

# Configurar renovação automática
sudo crontab -e
# Adicionar linha:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

### 3. Configurações de Segurança do Sistema

```bash
# Configurar fail2ban
sudo apt install fail2ban
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# Configurar SSH
sudo nano /etc/ssh/sshd_config
# PermitRootLogin no
# PasswordAuthentication no (se usando chaves)
# Port 2222 (mudar porta padrão)

sudo systemctl reload sshd
```

### 4. Monitoramento de Segurança

**Arquivo: `/etc/fail2ban/jail.local`**

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
```

## 📊 Monitoramento e Logs

### 1. Configuração de Logs Centralizados

**Arquivo: `/etc/rsyslog.d/30-mediadown.conf`**

```
# MediaDown logs
if $programname == 'mediadown' then /var/log/mediadown/app.log
& stop
```

### 2. Monitoramento com Prometheus

**Arquivo: `prometheus.yml`**

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'mediadown'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']

  - job_name: 'nginx'
    static_configs:
      - targets: ['localhost:9113']
```

### 3. Alertas

**Arquivo: `alertmanager.yml`**

```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@seu-dominio.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
- name: 'web.hook'
  email_configs:
  - to: 'admin@seu-dominio.com'
    subject: 'MediaDown Alert: {{ .GroupLabels.alertname }}'
    body: |
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      {{ end }}
```

## 💾 Backup e Recuperação

### 1. Script de Backup

**Arquivo: `/opt/mediadown/scripts/backup.sh`**

```bash
#!/bin/bash

BACKUP_DIR="/backups/mediadown"
DATE=$(date +%Y%m%d_%H%M%S)
DB_BACKUP="$BACKUP_DIR/db_$DATE.sql"
FILES_BACKUP="$BACKUP_DIR/files_$DATE.tar.gz"

# Criar diretório de backup
mkdir -p $BACKUP_DIR

# Backup do banco de dados
pg_dump -h localhost -U media_user -d mediadownloader > $DB_BACKUP
gzip $DB_BACKUP

# Backup dos arquivos
tar -czf $FILES_BACKUP -C /opt/mediadown \
    uploads/ \
    .env \
    app/static/ \
    logs/

# Remover backups antigos (manter 30 dias)
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### 2. Configurar Cron para Backups

```bash
# Backup diário às 2h da manhã
0 2 * * * /opt/mediadown/scripts/backup.sh >> /var/log/mediadown/backup.log 2>&1
```

### 3. Script de Restauração

**Arquivo: `/opt/mediadown/scripts/restore.sh`**

```bash
#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_date>"
    echo "Example: $0 20240115_020000"
    exit 1
fi

BACKUP_DATE=$1
BACKUP_DIR="/backups/mediadown"
DB_BACKUP="$BACKUP_DIR/db_$BACKUP_DATE.sql.gz"
FILES_BACKUP="$BACKUP_DIR/files_$BACKUP_DATE.tar.gz"

# Parar serviços
sudo supervisorctl stop mediadown:*

# Restaurar banco de dados
zcat $DB_BACKUP | psql -h localhost -U media_user -d mediadownloader

# Restaurar arquivos
cd /opt/mediadown
tar -xzf $FILES_BACKUP

# Reiniciar serviços
sudo supervisorctl start mediadown:*

echo "Restore completed for backup: $BACKUP_DATE"
```

## 🔧 Troubleshooting

### Problemas Comuns

#### 1. Aplicação não inicia

```bash
# Verificar logs
sudo tail -f /var/log/mediadown/web.log

# Verificar configuração
sudo -u mediadown /opt/mediadown/venv/bin/python -c "from app import create_app; app = create_app()"

# Verificar permissões
ls -la /opt/mediadown/
```

#### 2. Banco de dados não conecta

```bash
# Testar conexão
psql -h localhost -U media_user -d mediadownloader

# Verificar status
sudo systemctl status postgresql

# Verificar logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

#### 3. Redis não conecta

```bash
# Testar conexão
redis-cli ping

# Verificar status
sudo systemctl status redis

# Verificar configuração
redis-cli config get "*"
```

#### 4. Workers Celery não funcionam

```bash
# Verificar workers
sudo supervisorctl status mediadown:mediadown-worker

# Testar Celery
sudo -u mediadown /opt/mediadown/venv/bin/celery -A workers.celery_app status

# Verificar Redis queues
redis-cli llen celery
```

#### 5. Nginx retorna 502/503

```bash
# Verificar upstream
curl -I http://127.0.0.1:5000/health

# Verificar logs
sudo tail -f /var/log/nginx/error.log

# Testar configuração
sudo nginx -t
```

### Comandos Úteis de Diagnóstico

```bash
# Status geral do sistema
sudo systemctl status mediadown-web mediadown-worker postgresql redis nginx

# Uso de recursos
htop
iotop
netstat -tulpn

# Logs em tempo real
sudo tail -f /var/log/mediadown/*.log

# Verificar conectividade
sudo netstat -tlnp | grep :5000
sudo ss -tlnp | grep :5000

# Verificar processos
ps aux | grep -E "(gunicorn|celery|postgres|redis)"

# Verificar espaço em disco
df -h
du -sh /opt/mediadown/*

# Verificar memória
free -h
sudo slabtop
```

### Performance Tuning

#### 1. PostgreSQL

```bash
# Editar configuração
sudo nano /etc/postgresql/15/main/postgresql.conf

# Configurações recomendadas:
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

#### 2. Nginx

```bash
# Otimizações no nginx.conf
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
client_max_body_size 100M;
```

#### 3. Sistema

```bash
# Aumentar limites de arquivos
echo "* soft nofile 65535" >> /etc/security/limits.conf
echo "* hard nofile 65535" >> /etc/security/limits.conf

# Otimizar TCP
echo "net.core.rmem_max = 16777216" >> /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" >> /etc/sysctl.conf
sudo sysctl -p
```

## 🚀 Deploy Automático com CI/CD

### GitHub Actions

**Arquivo: `.github/workflows/deploy.yml`**

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to server
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.HOST }}
        username: ${{ secrets.USERNAME }}
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /opt/mediadown
          git pull origin main
          source venv/bin/activate
          pip install -r requirements.txt
          python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
          sudo supervisorctl restart mediadown:*
```

---

## 📞 Suporte

Para suporte adicional:
- **Email**: support@mediadown.com
- **Documentação**: https://mediadown.readthedocs.io
- **Issues**: https://github.com/mediadown/mediadown/issues

---

**📝 Nota**: Este guia pressupõe conhecimento básico de administração de sistemas Linux. Para ambientes de produção críticos, recomenda-se consultoria especializada.
