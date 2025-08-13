from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models.downloads import Download, DownloadStatus
from app.models.servers import Server, ServerStatus
from app.models.users import User
from app.services.logging_service import LoggingService
from app.services.server_monitor_service import ServerMonitorService
from app import db
from datetime import datetime, timedelta
import json

main_bp = Blueprint('main', __name__)
logger = LoggingService()
server_monitor = ServerMonitorService()

@main_bp.route('/')
@login_required
def dashboard():
    """Main dashboard with system statistics"""
    try:
        # Get basic statistics
        total_downloads = Download.query.count()
        active_downloads = Download.query.filter_by(status=DownloadStatus.DOWNLOADING).count()
        completed_downloads = Download.query.filter_by(status=DownloadStatus.COMPLETED).count()
        failed_downloads = Download.query.filter_by(status=DownloadStatus.FAILED).count()
        
        # Get server statistics
        total_servers = Server.query.count()
        online_servers = Server.query.filter_by(status=ServerStatus.ONLINE).count()
        
        # Get recent downloads
        recent_downloads = Download.query.order_by(
            Download.created_at.desc()
        ).limit(10).all()
        
        # Get system statistics
        system_stats = get_system_statistics()
        
        # Get user activity
        user_activity = get_user_activity()
        
        return render_template('main/dashboard.html',
                             total_downloads=total_downloads,
                             active_downloads=active_downloads,
                             completed_downloads=completed_downloads,
                             failed_downloads=failed_downloads,
                             total_servers=total_servers,
                             online_servers=online_servers,
                             recent_downloads=recent_downloads,
                             system_stats=system_stats,
                             user_activity=user_activity)
    
    except Exception as e:
        logger.log_system('error', f'Error loading dashboard: {str(e)}')
        flash('Erro ao carregar o dashboard.', 'error')
        return render_template('main/dashboard.html')

@main_bp.route('/library')
@login_required
def library():
    """View organized content library"""
    try:
        # Get completed downloads organized by server
        servers = Server.query.all()
        library_data = {}
        
        for server in servers:
            completed_downloads = Download.query.filter_by(
                server_id=server.id,
                status=DownloadStatus.COMPLETED
            ).order_by(Download.completed_at.desc()).all()
            
            library_data[server.name] = {
                'server': server,
                'downloads': completed_downloads,
                'count': len(completed_downloads)
            }
        
        return render_template('main/library.html', library_data=library_data)
    
    except Exception as e:
        logger.log_system('error', f'Error loading library: {str(e)}')
        flash('Erro ao carregar a biblioteca.', 'error')
        return render_template('main/library.html')

@main_bp.route('/search')
@login_required
def search():
    """Search content in library"""
    query = request.args.get('q', '')
    content_type = request.args.get('type', '')
    server_id = request.args.get('server', '')
    
    try:
        # Build search query
        search_query = Download.query.filter_by(status=DownloadStatus.COMPLETED)
        
        if query:
            search_query = search_query.filter(Download.title.ilike(f'%{query}%'))
        
        if content_type:
            search_query = search_query.filter_by(content_type=content_type)
        
        if server_id:
            search_query = search_query.filter_by(server_id=server_id)
        
        results = search_query.order_by(Download.completed_at.desc()).all()
        
        # Get available servers for filter
        servers = Server.query.all()
        
        return render_template('main/search.html',
                             results=results,
                             query=query,
                             content_type=content_type,
                             server_id=server_id,
                             servers=servers)
    
    except Exception as e:
        logger.log_system('error', f'Error searching content: {str(e)}')
        flash('Erro ao pesquisar conteúdo.', 'error')
        return render_template('main/search.html')

@main_bp.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for real-time statistics"""
    try:
        # Get current statistics
        stats = {
            'downloads': {
                'total': Download.query.count(),
                'active': Download.query.filter_by(status=DownloadStatus.DOWNLOADING).count(),
                'completed': Download.query.filter_by(status=DownloadStatus.COMPLETED).count(),
                'failed': Download.query.filter_by(status=DownloadStatus.FAILED).count(),
                'pending': Download.query.filter_by(status=DownloadStatus.PENDING).count(),
                'transferring': Download.query.filter_by(status=DownloadStatus.TRANSFERRING).count()
            },
            'servers': {
                'total': Server.query.count(),
                'online': Server.query.filter_by(status=ServerStatus.ONLINE).count(),
                'offline': Server.query.filter_by(status=ServerStatus.OFFLINE).count()
            },
            'users': {
                'total': User.query.count(),
                'active': User.query.filter_by(is_active=True).count()
            }
        }
        
        return jsonify(stats)
    
    except Exception as e:
        logger.log_system('error', f'Error getting API stats: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@main_bp.route('/api/downloads/active')
@login_required
def api_active_downloads():
    """API endpoint for active downloads"""
    try:
        active_downloads = Download.query.filter(
            Download.status.in_([DownloadStatus.DOWNLOADING, DownloadStatus.TRANSFERRING])
        ).all()
        
        downloads_data = []
        for download in active_downloads:
            downloads_data.append({
                'id': download.id,
                'title': download.title,
                'status': download.status.value,
                'progress': download.progress_percentage,
                'speed': download.download_speed,
                'eta': download.estimated_time,
                'server': download.server.name if download.server else None
            })
        
        return jsonify(downloads_data)
    
    except Exception as e:
        logger.log_system('error', f'Error getting active downloads: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@main_bp.route('/api/servers/status')
@login_required
def api_servers_status():
    """API endpoint for server status"""
    try:
        servers = Server.query.all()
        servers_data = []
        
        for server in servers:
            servers_data.append({
                'id': server.id,
                'name': server.name,
                'status': server.status.value,
                'protocol': server.protocol.value,
                'last_check': server.last_check.isoformat() if server.last_check else None,
                'disk_usage': server.disk_usage_dict
            })
        
        return jsonify(servers_data)
    
    except Exception as e:
        logger.log_system('error', f'Error getting server status: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

def get_system_statistics():
    """Get system statistics for dashboard"""
    try:
        # Downloads by day (last 7 days)
        downloads_by_day = []
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            count = Download.query.filter(
                db.func.date(Download.created_at) == date.date()
            ).count()
            downloads_by_day.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        
        # Downloads by content type
        content_types = db.session.query(
            Download.content_type,
            db.func.count(Download.id)
        ).group_by(Download.content_type).all()
        
        # Downloads by quality
        qualities = db.session.query(
            Download.quality,
            db.func.count(Download.id)
        ).group_by(Download.quality).all()
        
        return {
            'downloads_by_day': downloads_by_day,
            'content_types': dict(content_types),
            'qualities': dict(qualities)
        }
    
    except Exception as e:
        logger.log_system('error', f'Error getting system statistics: {str(e)}')
        return {}

def get_user_activity():
    """Get recent user activity"""
    try:
        from app.models.logs import UserActivityLog
        
        recent_activity = UserActivityLog.query.order_by(
            UserActivityLog.timestamp.desc()
        ).limit(20).all()
        
        return recent_activity
    
    except Exception as e:
        logger.log_system('error', f'Error getting user activity: {str(e)}')
        return []


