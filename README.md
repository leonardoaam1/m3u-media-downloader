# Sistema de Download de Vídeos M3U

Sistema completo em Python para automação de downloads de vídeos, filmes e séries baseado em listas M3U, com interface web, sistema de usuários e logs detalhados.

## 🚀 Características Principais

### Funcionalidades Core
- **Gerenciamento de Listas M3U**: Upload e comparação inteligente de listas
- **Sistema de Fila de Downloads**: Fila inteligente com prioridades e downloads paralelos
- **Integração TMDB**: Busca automática de metadados e informações de conteúdo
- **Sistema de Renomeação e Organização**: Padrões específicos para filmes, séries e novelas
- **Gerenciamento de Servidores**: Suporte a múltiplos protocolos (SFTP, NFS, SMB, Rsync)
- **Sistema de Autenticação**: Roles e permissões (Admin, Operator, Viewer)
- **Logs Detalhados**: Sistema completo de auditoria e monitoramento

### Stack Tecnológico
- **Backend**: Flask 3.0.0, SQLAlchemy 2.0.25, Celery 5.3.4
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis 7.2.10
- **Download**: yt-dlp 2025.7.21
- **Transferência**: Paramiko (SFTP), pysmb (SMB), rsync
- **Frontend**: Bootstrap 5, Chart.js, Alpine.js

## 📋 Pré-requisitos

### Sistema Operacional
- Ubuntu 24.04.2 LTS (recomendado)
- Python 3.12.3
- PostgreSQL 16
- Redis 7.2.10

### Dependências do Sistema
```bash
# Instalar dependências do sistema
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y redis-server
sudo apt install -y nginx
sudo apt install -y ffmpeg
sudo apt install -y rsync
sudo apt install -y openssh-client
```

## 🛠️ Instalação

### 1. Clone o Repositório
```bash
git clone <repository-url>
cd mediadown
```

### 2. Configurar Ambiente Virtual
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configurar Banco de Dados
```bash
# Criar database e usuário
sudo -u postgres psql
CREATE DATABASE mediadownloader;
CREATE USER media_user WITH PASSWORD 'yZyERmabaBeJ';
GRANT ALL PRIVILEGES ON DATABASE mediadownloader TO media_user;
\q
```

### 4. Configurar Variáveis de Ambiente
```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar configurações
nano .env
```

### 5. Inicializar Sistema
```bash
# Ativar ambiente virtual
source venv/bin/activate

# Inicializar banco de dados
flask init-db

# Configurar servidores padrão
flask setup-servers

# Criar usuário adicional (opcional)
flask create-user
```

### 6. Configurar Nginx (Produção)
```nginx
server {
    listen 443 ssl http2;
    server_name hubservices.host;
    
    ssl_certificate /etc/letsencrypt/live/hubservices.host/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hubservices.host/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🚀 Execução

### Desenvolvimento
```bash
source venv/bin/activate
python app.py
```

### Produção
```bash
# Usando Gunicorn
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 --workers 2 wsgi:app

# Iniciar Celery workers
celery -A workers.celery_app worker --loglevel=info -Q downloads,transfers
celery -A workers.celery_app beat --loglevel=info
```

### Usando Supervisor (Recomendado)
```bash
# Instalar supervisor
sudo apt install supervisor

# Configurar serviços
sudo nano /etc/supervisor/conf.d/mediadownloader.conf
```

```ini
[program:mediadownloader]
command=/path/to/mediadown/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 wsgi:app
directory=/path/to/mediadown
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadownloader/app.log

[program:celery_worker]
command=/path/to/mediadown/venv/bin/celery -A workers.celery_app worker --loglevel=info -Q downloads,transfers
directory=/path/to/mediadown
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadownloader/celery.log

[program:celery_beat]
command=/path/to/mediadown/venv/bin/celery -A workers.celery_app beat --loglevel=info
directory=/path/to/mediadown
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/mediadownloader/celery_beat.log
```

```bash
# Recarregar supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start mediadownloader celery_worker celery_beat
```

## 📁 Estrutura de Diretórios

```
mediadown/
├── app/
│   ├── models/          # Modelos do banco de dados
│   ├── routes/          # Rotas da aplicação
│   ├── services/        # Lógica de negócio
│   ├── templates/       # Templates HTML
│   └── static/          # Arquivos estáticos
├── workers/             # Workers Celery
├── logs/               # Logs do sistema
├── temp_downloads/     # Downloads temporários
├── uploads/            # Uploads M3U
├── config.py           # Configurações
├── app.py              # Aplicação principal
├── wsgi.py             # WSGI para produção
└── requirements.txt    # Dependências Python
```

## 🔧 Configuração de Servidores

### Servidor de Filmes
- **Host**: 192.168.1.10
- **Protocolo**: SFTP
- **Diretórios**: Acao, Animacao_Infantil, Animes, Cinema, Comedia, Documentarios, Drama, Faroeste, Ficcao_Fantasia, Filmes_Legendados, Guerra, Lancamentos, Marvel, Romance, Suspense, Terror

### Servidor de Séries
- **Host**: 192.168.1.11
- **Protocolo**: SFTP
- **Diretórios**: Amazon, Animes_(Dub), Animes_(Leg), Apple_Tv, Desenhos_Animados, DiscoveryPlus, DisneyPlus, Drama, Globo_Play, HBOMax, Lionsgate, Looke, Natgeo, Netflix, ParamountPlus, Star_Plus

### Servidor de Novelas
- **Host**: 192.168.1.12
- **Protocolo**: SFTP
- **Diretório**: Novelas/{Nome_da_Novela}

## 👥 Sistema de Usuários

### Roles e Permissões

#### Admin
- Gerenciar usuários
- Configurar servidores
- Acessar todos os logs
- Controlar filas globalmente
- Configurar sistema

#### Operator
- Upload de listas M3U
- Gerenciar fila de downloads
- Selecionar servidor de destino
- Pausar/resumir downloads
- Ver progresso e estatísticas

#### Viewer
- Visualizar progresso de downloads
- Ver biblioteca organizada
- Buscar conteúdo
- Estatísticas básicas

## 📊 Monitoramento e Logs

### Tipos de Log
- **System Logs**: Inicialização, erros críticos, performance
- **User Activity Logs**: Login, ações dos usuários
- **Download Logs**: Progresso, falhas, retries
- **TMDB Integration Logs**: Buscas, matches, cache
- **Server Management Logs**: Status, conectividade
- **File Transfer Logs**: Transferências, integridade

### Acessar Logs
```bash
# Logs da aplicação
tail -f logs/app.log

# Logs do Celery
tail -f logs/celery.log

# Logs do Nginx
tail -f /var/log/nginx/hubservices.host.log
```

## 🔍 Uso do Sistema

### 1. Login
- Acesse: https://hubservices.host
- Credenciais padrão: admin/admin123

### 2. Upload de Lista M3U
1. Vá para "Upload M3U"
2. Faça upload da lista principal (base de referência)
3. Faça upload da nova lista para comparação
4. Sistema identifica itens não presentes na lista principal
5. Selecione itens para download

### 3. Gerenciar Downloads
1. Visualize a fila de downloads
2. Ajuste prioridades se necessário
3. Selecione servidor de destino
4. Monitore progresso em tempo real

### 4. Configurar Servidores
1. Acesse "Servidores" (apenas Admin)
2. Adicione novos servidores
3. Configure protocolo e credenciais
4. Teste conectividade

## 🛡️ Segurança

### Configurações de Segurança
- Senhas hash com bcrypt
- Sessões com timeout configurável
- Rate limiting para APIs
- Validação de uploads
- Logs de auditoria

### Firewall
```bash
# Liberar portas necessárias
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 5000
sudo ufw allow 22
```

## 🔧 Manutenção

### Backup do Banco de Dados
```bash
# Backup
pg_dump -U media_user -h localhost mediadownloader > backup_$(date +%Y%m%d).sql

# Restore
psql -U media_user -h localhost mediadownloader < backup_20250101.sql
```

### Limpeza de Logs
```bash
# Limpar logs antigos (via interface web ou CLI)
flask cleanup-logs --days 30
```

### Monitoramento de Disco
```bash
# Verificar espaço em disco
df -h

# Limpar downloads temporários
find temp_downloads/ -type f -mtime +7 -delete
```

## 🐛 Troubleshooting

### Problemas Comuns

#### Erro de Conexão com Banco
```bash
# Verificar se PostgreSQL está rodando
sudo systemctl status postgresql

# Verificar conexão
psql -U media_user -h localhost -d mediadownloader
```

#### Erro de Conexão com Redis
```bash
# Verificar se Redis está rodando
sudo systemctl status redis

# Testar conexão
redis-cli ping
```

#### Downloads Falhando
```bash
# Verificar logs do Celery
tail -f logs/celery.log

# Verificar espaço em disco
df -h temp_downloads/

# Verificar conectividade com servidores
flask test-servers
```

#### Interface Web Não Carrega
```bash
# Verificar se Flask está rodando
ps aux | grep gunicorn

# Verificar logs da aplicação
tail -f logs/app.log

# Verificar Nginx
sudo systemctl status nginx
```

## 📞 Suporte

Para suporte técnico ou dúvidas:
- Email: suporte@hubservices.host
- Documentação: https://docs.hubservices.host
- Issues: GitHub Issues

## 📄 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🤝 Contribuição

Contribuições são bem-vindas! Por favor, leia o [CONTRIBUTING.md](CONTRIBUTING.md) para detalhes sobre como contribuir.

---

**Desenvolvido com ❤️ para automatizar downloads de conteúdo audiovisual**




