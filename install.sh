#!/bin/bash

# Sistema de Download de Vídeos M3U - Script de Instalação
# Ubuntu 24.04.2 LTS

set -e

echo "🚀 Iniciando instalação do Sistema de Download de Vídeos M3U"
echo "=================================================="

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para log
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERRO] $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[AVISO] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Verificar se é root
if [[ $EUID -eq 0 ]]; then
   error "Este script não deve ser executado como root"
fi

# Verificar sistema operacional
if [[ ! -f /etc/os-release ]]; then
    error "Sistema operacional não suportado"
fi

source /etc/os-release
if [[ "$ID" != "ubuntu" ]]; then
    error "Este script é específico para Ubuntu"
fi

log "Sistema operacional detectado: $PRETTY_NAME"

# Atualizar sistema
log "Atualizando sistema..."
sudo apt update && sudo apt upgrade -y

# Instalar dependências do sistema
log "Instalando dependências do sistema..."
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    ffmpeg \
    rsync \
    openssh-client \
    curl \
    wget \
    git \
    supervisor \
    certbot \
    python3-certbot-nginx

# Verificar se Python 3.12 foi instalado
if ! command -v python3.12 &> /dev/null; then
    error "Python 3.12 não foi instalado corretamente"
fi

log "Python 3.12 instalado: $(python3.12 --version)"

# Configurar PostgreSQL
log "Configurando PostgreSQL..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Criar usuário e database
sudo -u postgres psql -c "CREATE DATABASE mediadownloader;" || warning "Database já existe"
sudo -u postgres psql -c "CREATE USER media_user WITH PASSWORD 'yZyERmabaBeJ';" || warning "Usuário já existe"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mediadownloader TO media_user;"
sudo -u postgres psql -c "ALTER USER media_user CREATEDB;"

# Configurar Redis
log "Configurando Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verificar se Redis está funcionando
if ! redis-cli ping | grep -q "PONG"; then
    error "Redis não está funcionando corretamente"
fi

log "Redis configurado e funcionando"

# Criar diretórios do projeto
log "Criando diretórios do projeto..."
sudo mkdir -p /www/wwwroot/media_downloader
sudo chown $USER:$USER /www/wwwroot/media_downloader

# Criar ambiente virtual Python
log "Criando ambiente virtual Python..."
cd /www/wwwroot/media_downloader
python3.12 -m venv venv
source venv/bin/activate

# Atualizar pip
pip install --upgrade pip

# Instalar dependências Python
log "Instalando dependências Python..."
pip install -r requirements.txt

# Configurar arquivo .env
log "Configurando variáveis de ambiente..."
if [[ ! -f .env ]]; then
    cp env.example .env
    warning "Arquivo .env criado. Por favor, configure as variáveis necessárias."
fi

# Criar diretórios necessários
log "Criando diretórios necessários..."
mkdir -p logs temp_downloads uploads

# Configurar permissões
log "Configurando permissões..."
chmod 750 logs temp_downloads uploads

# Inicializar banco de dados
log "Inicializando banco de dados..."
flask init-db

# Configurar servidores padrão
log "Configurando servidores padrão..."
flask setup-servers

# Configurar Nginx
log "Configurando Nginx..."
sudo tee /etc/nginx/sites-available/mediadownloader > /dev/null <<EOF
server {
    listen 80;
    server_name hubservices.host;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Habilitar site
sudo ln -sf /etc/nginx/sites-available/mediadownloader /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# Configurar Supervisor
log "Configurando Supervisor..."
sudo tee /etc/supervisor/conf.d/mediadownloader.conf > /dev/null <<EOF
[program:mediadownloader]
command=/www/wwwroot/media_downloader/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 wsgi:app
directory=/www/wwwroot/media_downloader
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadownloader/app.log
environment=PATH="/www/wwwroot/media_downloader/venv/bin"

[program:celery_worker]
command=/www/wwwroot/media_downloader/venv/bin/celery -A workers.celery_app worker --loglevel=info -Q downloads,transfers
directory=/www/wwwroot/media_downloader
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadownloader/celery.log
environment=PATH="/www/wwwroot/media_downloader/venv/bin"

[program:celery_beat]
command=/www/wwwroot/media_downloader/venv/bin/celery -A workers.celery_app beat --loglevel=info
directory=/www/wwwroot/media_downloader
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadownloader/celery_beat.log
environment=PATH="/www/wwwroot/media_downloader/venv/bin"
EOF

# Criar diretório de logs
sudo mkdir -p /var/log/mediadownloader
sudo chown $USER:$USER /var/log/mediadownloader

# Recarregar Supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Configurar firewall
log "Configurando firewall..."
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 5000
sudo ufw --force enable

# Configurar SSL (opcional)
read -p "Deseja configurar SSL com Let's Encrypt? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Configurando SSL..."
    sudo certbot --nginx -d hubservices.host --non-interactive --agree-tos --email admin@hubservices.host
fi

# Iniciar serviços
log "Iniciando serviços..."
sudo supervisorctl start mediadownloader celery_worker celery_beat

# Verificar status dos serviços
log "Verificando status dos serviços..."
sleep 5

if sudo supervisorctl status mediadownloader | grep -q "RUNNING"; then
    log "✅ Aplicação Flask iniciada com sucesso"
else
    error "❌ Falha ao iniciar aplicação Flask"
fi

if sudo supervisorctl status celery_worker | grep -q "RUNNING"; then
    log "✅ Worker Celery iniciado com sucesso"
else
    error "❌ Falha ao iniciar Worker Celery"
fi

if sudo supervisorctl status celery_beat | grep -q "RUNNING"; then
    log "✅ Celery Beat iniciado com sucesso"
else
    error "❌ Falha ao iniciar Celery Beat"
fi

# Criar script de gerenciamento
log "Criando script de gerenciamento..."
sudo tee /usr/local/bin/mediadownloader > /dev/null <<EOF
#!/bin/bash
case "\$1" in
    start)
        sudo supervisorctl start mediadownloader celery_worker celery_beat
        ;;
    stop)
        sudo supervisorctl stop mediadownloader celery_worker celery_beat
        ;;
    restart)
        sudo supervisorctl restart mediadownloader celery_worker celery_beat
        ;;
    status)
        sudo supervisorctl status mediadownloader celery_worker celery_beat
        ;;
    logs)
        tail -f /var/log/mediadownloader/\$2.log
        ;;
    *)
        echo "Uso: \$0 {start|stop|restart|status|logs [app|celery|celery_beat]}"
        exit 1
        ;;
esac
EOF

sudo chmod +x /usr/local/bin/mediadownloader

# Informações finais
echo
echo "🎉 Instalação concluída com sucesso!"
echo "=================================================="
echo
echo "📋 Informações importantes:"
echo "• URL da aplicação: http://hubservices.host"
echo "• Credenciais padrão: admin/admin123"
echo "• Diretório do projeto: /www/wwwroot/media_downloader"
echo "• Logs da aplicação: /var/log/mediadownloader/"
echo
echo "🔧 Comandos úteis:"
echo "• Gerenciar serviços: mediadownloader {start|stop|restart|status}"
echo "• Ver logs: mediadownloader logs app"
echo "• Acessar aplicação: cd /www/wwwroot/media_downloader && source venv/bin/activate"
echo
echo "⚠️  Próximos passos:"
echo "1. Configure o arquivo .env com suas configurações"
echo "2. Configure os servidores de destino com IPs corretos"
echo "3. Obtenha uma chave API do TMDB (opcional)"
echo "4. Configure SSL se necessário"
echo
echo "📞 Para suporte: suporte@hubservices.host"
echo








