# MediaDown - M3U Video Download System

Complete Python system for automating video, movie, and series downloads based on M3U lists, with web interface, user system, and detailed logs.

## 🚀 Main Features

### Core Functionalities
- **M3U List Management**: Upload and intelligent comparison of lists
- **Download Queue System**: Intelligent queue with priorities and parallel downloads
- **TMDB Integration**: Automatic metadata search and content information
- **Renaming and Organization System**: Specific patterns for movies, series, and soap operas
- **Server Management**: Support for multiple protocols (SFTP, NFS, SMB, Rsync)
- **Authentication System**: Roles and permissions (Admin, Operator, Viewer)
- **Detailed Logs**: Complete audit and monitoring system

### Technology Stack
- **Backend**: Flask 3.0.0, SQLAlchemy 2.0.25, Celery 5.3.4
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis 7.2.10
- **Download**: yt-dlp 2025.7.21
- **Transfer**: Paramiko (SFTP), pysmb (SMB), rsync
- **Frontend**: Bootstrap 5, Chart.js, Alpine.js

## 📋 Prerequisites

### Operating System
- Ubuntu 24.04.2 LTS (recommended)
- Python 3.12.3
- PostgreSQL 16
- Redis 7.2.10

### System Dependencies
```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y redis-server
sudo apt install -y nginx
sudo apt install -y ffmpeg
sudo apt install -y rsync
sudo apt install -y openssh-client
```

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd mediadown
```

### 2. Set up Virtual Environment
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Database
```bash
# Create database and user
sudo -u postgres psql
CREATE DATABASE mediadownloader;
CREATE USER media_user WITH PASSWORD 'yZyERmabaBeJ';
GRANT ALL PRIVILEGES ON DATABASE mediadownloader TO media_user;
\q
```

### 4. Configure Environment Variables
```bash
# Copy example file
cp .env.example .env

# Edit configurations
nano .env
```

### 5. Initialize System
```bash
# Activate virtual environment
source venv/bin/activate

# Initialize database
flask init-db

# Configure default servers
flask setup-servers

# Create additional user (optional)
flask create-user
```

## 🚀 Execution

### Development
```bash
source venv/bin/activate
python app.py
```

### Production
```bash
# Using Gunicorn
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 --workers 2 wsgi:app

# Start Celery workers
celery -A workers.celery_app worker --loglevel=info -Q downloads,transfers
celery -A workers.celery_app beat --loglevel=info
```

## 📁 Directory Structure

```
mediadown/
├── app/
│   ├── models/          # Database models
│   ├── routes/          # Application routes
│   ├── services/        # Business logic
│   ├── templates/       # HTML templates
│   └── static/          # Static files
├── workers/             # Celery workers
├── logs/               # System logs
├── temp_downloads/     # Temporary downloads
├── uploads/            # M3U uploads
├── config.py           # Configurations
├── app.py              # Main application
├── wsgi.py             # WSGI for production
└── requirements.txt    # Python dependencies
```

## 👥 User System

### Roles and Permissions

#### Admin
- Manage users
- Configure servers
- Access all logs
- Control queues globally
- Configure system

#### Operator
- Upload M3U lists
- Manage download queue
- Select destination server
- Pause/resume downloads
- View progress and statistics

#### Viewer
- View download progress
- See organized library
- Search content
- Basic statistics

## 🔧 Server Configuration

### Movie Server
- **Host**: 192.168.1.10
- **Protocol**: SFTP
- **Directories**: Action, Animation_Children, Anime, Cinema, Comedy, Documentaries, Drama, Western, Fantasy_SciFi, Subtitled_Movies, War, New_Releases, Marvel, Romance, Thriller, Horror

### Series Server
- **Host**: 192.168.1.11
- **Protocol**: SFTP
- **Directories**: Amazon, Anime_(Dub), Anime_(Sub), Apple_Tv, Cartoons, DiscoveryPlus, DisneyPlus, Drama, Globo_Play, HBOMax, Lionsgate, Looke, Natgeo, Netflix, ParamountPlus, Star_Plus

### Soap Opera Server
- **Host**: 192.168.1.12
- **Protocol**: SFTP
- **Directory**: Soap_Operas/{Soap_Opera_Name}

## 🔍 System Usage

### 1. Login
- Access: https://hubservices.host
- Default credentials: admin/admin123

### 2. Upload M3U List
1. Go to "Upload M3U"
2. Upload the main list (reference base)
3. Upload the new list for comparison
4. System identifies items not present in the main list
5. Select items for download

### 3. Manage Downloads
1. View download queue
2. Adjust priorities if necessary
3. Select destination server
4. Monitor progress in real time

## 🛡️ Security

### Security Settings
- Passwords hashed with bcrypt
- Sessions with configurable timeout
- Rate limiting for APIs
- Upload validation
- Audit logs

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute.

---

**Developed with ❤️ to automate audiovisual content downloads**
