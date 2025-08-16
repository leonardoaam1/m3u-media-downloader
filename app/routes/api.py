from flask import Blueprint, request, jsonify, current_app, g
from flask_login import login_required, current_user
from functools import wraps
from app.models.users import User, UserRole
from app.models.downloads import Download, DownloadStatus, DownloadPriority
from app.models.servers import Server, ServerStatus
from app.models.logs import SystemLog, UserActivityLog
from app.services.logging_service import LoggingService
from app.services.download_service import DownloadService
from app.services.m3u_parser import M3UParser
from app.utils.advanced_rate_limiter import (
    rate_limit, strict_rate_limit, normal_rate_limit, relaxed_rate_limit, 
    adaptive_rate_limit, LimitStrategy, LimitTier
)
from app import db
import hashlib
import hmac
import time
import jwt
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
logger = LoggingService()
download_service = DownloadService()
m3u_parser = M3UParser()

def require_api_key(f):
    """Decorator to require API key for external access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # Validate API key (simplified - would use proper API key management in production)
        expected_key = current_app.config.get('API_KEY', 'mediadown-api-key-2025')
        if api_key != expected_key:
            return jsonify({'error': 'Invalid API key'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_webhook_signature(f):
    """Decorator to validate webhook signatures"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get('X-Webhook-Signature')
        if not signature:
            return jsonify({'error': 'Webhook signature required'}), 401
        
        # Validate signature (simplified)
        webhook_secret = current_app.config.get('WEBHOOK_SECRET', 'webhook-secret-2025')
        payload = request.get_data()
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, f'sha256={expected_signature}'):
            return jsonify({'error': 'Invalid webhook signature'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# System Information Endpoints
@api_bp.route('/status')
@require_api_key
@relaxed_rate_limit(requests_per_minute=30)
def system_status():
    """Get system status and health"""
    try:
        # Get basic system stats
        total_downloads = Download.query.count()
        active_downloads = Download.query.filter(
            Download.status.in_([DownloadStatus.DOWNLOADING, DownloadStatus.TRANSFERRING])
        ).count()
        completed_downloads = Download.query.filter_by(status=DownloadStatus.COMPLETED).count()
        failed_downloads = Download.query.filter_by(status=DownloadStatus.FAILED).count()
        
        # Get server stats
        total_servers = Server.query.count()
        online_servers = Server.query.filter_by(status=ServerStatus.ONLINE).count()
        
        # Get user stats
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0',
            'stats': {
                'downloads': {
                    'total': total_downloads,
                    'active': active_downloads,
                    'completed': completed_downloads,
                    'failed': failed_downloads
                },
                'servers': {
                    'total': total_servers,
                    'online': online_servers,
                    'offline': total_servers - online_servers
                },
                'users': {
                    'total': total_users,
                    'active': active_users
                }
            }
        })
        
    except Exception as e:
        logger.log_system('error', f'API status error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

# Downloads Management Endpoints
@api_bp.route('/downloads')
@require_api_key
@normal_rate_limit(requests_per_minute=30)
def list_downloads():
    """List downloads with filtering and pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status')
        content_type = request.args.get('content_type')
        server_id = request.args.get('server_id', type=int)
        
        query = Download.query
        
        # Apply filters
        if status:
            try:
                query = query.filter_by(status=DownloadStatus(status))
            except ValueError:
                return jsonify({'error': f'Invalid status: {status}'}), 400
        
        if content_type:
            query = query.filter_by(content_type=content_type)
        
        if server_id:
            query = query.filter_by(server_id=server_id)
        
        # Get paginated results
        downloads_paginated = query.order_by(Download.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        downloads_data = []
        for download in downloads_paginated.items:
            downloads_data.append({
                'id': download.id,
                'title': download.title,
                'content_type': download.content_type,
                'quality': download.quality,
                'status': download.status.value,
                'progress_percentage': download.progress_percentage,
                'url': download.url,
                'server': {
                    'id': download.server.id,
                    'name': download.server.name
                } if download.server else None,
                'destination_path': download.destination_path,
                'file_size': download.file_size,
                'download_speed': download.download_speed,
                'estimated_time': download.estimated_time,
                'created_at': download.created_at.isoformat(),
                'started_at': download.started_at.isoformat() if download.started_at else None,
                'completed_at': download.completed_at.isoformat() if download.completed_at else None,
                'tmdb_id': download.tmdb_id,
                'tmdb_title': download.tmdb_title,
                'season': download.season,
                'episode': download.episode
            })
        
        return jsonify({
            'downloads': downloads_data,
            'pagination': {
                'page': downloads_paginated.page,
                'per_page': downloads_paginated.per_page,
                'total': downloads_paginated.total,
                'pages': downloads_paginated.pages,
                'has_prev': downloads_paginated.has_prev,
                'has_next': downloads_paginated.has_next
            }
        })
        
    except Exception as e:
        logger.log_system('error', f'API list downloads error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/downloads/<int:download_id>')
@require_api_key
@normal_rate_limit(requests_per_minute=60)
def get_download(download_id):
    """Get detailed information about a specific download"""
    try:
        download = Download.query.get_or_404(download_id)
        
        return jsonify({
            'id': download.id,
            'title': download.title,
            'content_type': download.content_type,
            'quality': download.quality,
            'status': download.status.value,
            'priority': download.priority.value,
            'progress_percentage': download.progress_percentage,
            'url': download.url,
            'server': {
                'id': download.server.id,
                'name': download.server.name,
                'host': download.server.host,
                'protocol': download.server.protocol.value
            } if download.server else None,
            'destination_path': download.destination_path,
            'file_size': download.file_size,
            'downloaded_size': download.downloaded_size,
            'download_speed': download.download_speed,
            'estimated_time': download.estimated_time,
            'retry_count': download.retry_count,
            'max_retries': download.max_retries,
            'error_message': download.error_message,
            'created_at': download.created_at.isoformat(),
            'started_at': download.started_at.isoformat() if download.started_at else None,
            'completed_at': download.completed_at.isoformat() if download.completed_at else None,
            'tmdb_id': download.tmdb_id,
            'tmdb_title': download.tmdb_title,
            'tmdb_genre': download.tmdb_genre,
            'tmdb_platform': download.tmdb_platform,
            'tmdb_poster': download.tmdb_poster,
            'season': download.season,
            'episode': download.episode,
            'episode_title': download.episode_title,
            'year': download.year
        })
        
    except Exception as e:
        logger.log_system('error', f'API get download error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/downloads', methods=['POST'])
@require_api_key
@strict_rate_limit(requests_per_minute=10)
def create_download():
    """Create a new download"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'url', 'content_type', 'quality']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate content type
        valid_content_types = ['movie', 'series', 'novela']
        if data['content_type'] not in valid_content_types:
            return jsonify({'error': f'Invalid content_type. Must be one of: {valid_content_types}'}), 400
        
        # Validate quality
        accepted_qualities = current_app.config.get('ACCEPTED_QUALITIES', ['480p', '720p', '1080p'])
        if data['quality'] not in accepted_qualities:
            return jsonify({'error': f'Invalid quality. Must be one of: {accepted_qualities}'}), 400
        
        # Get server (optional)
        server = None
        if 'server_id' in data:
            server = Server.query.get(data['server_id'])
            if not server:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # Auto-select server based on content type
            servers = Server.query.filter_by(status=ServerStatus.ONLINE).all()
            suggestion = m3u_parser.suggest_server_and_directory(data, servers)
            server = suggestion.get('server')
            
        if not server:
            return jsonify({'error': 'No suitable server found'}), 400
        
        # Create download
        download = Download(
            title=data['title'],
            content_type=data['content_type'],
            quality=data['quality'],
            url=data['url'],
            server_id=server.id,
            destination_path=data.get('destination_path', server.base_path),
            priority=DownloadPriority(data.get('priority', 'medium')),
            season=data.get('season'),
            episode=data.get('episode'),
            episode_title=data.get('episode_title'),
            year=data.get('year'),
            tmdb_id=data.get('tmdb_id'),
            user_id=1  # API user (would be configurable)
        )
        
        db.session.add(download)
        db.session.commit()
        
        logger.log_system('info', f'Download created via API: {download.title}')
        
        # Trigger download processing
        from workers.download_worker import process_download_queue
        process_download_queue.delay()
        
        return jsonify({
            'id': download.id,
            'message': 'Download created successfully',
            'status': download.status.value
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.log_system('error', f'API create download error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/downloads/<int:download_id>/control', methods=['POST'])
@require_api_key
@strict_rate_limit(requests_per_minute=20)
def control_download(download_id):
    """Control download (pause, resume, cancel, retry)"""
    try:
        download = Download.query.get_or_404(download_id)
        data = request.get_json()
        action = data.get('action')
        
        if not action:
            return jsonify({'error': 'Action is required'}), 400
        
        valid_actions = ['pause', 'resume', 'cancel', 'retry']
        if action not in valid_actions:
            return jsonify({'error': f'Invalid action. Must be one of: {valid_actions}'}), 400
        
        # Perform action
        if action == 'pause':
            download.pause()
        elif action == 'resume':
            download.resume()
        elif action == 'cancel':
            download.cancel()
        elif action == 'retry':
            download.retry()
        
        db.session.commit()
        
        logger.log_system('info', f'Download {action} via API: {download.title}')
        
        return jsonify({
            'message': f'Download {action} successful',
            'status': download.status.value
        })
        
    except Exception as e:
        db.session.rollback()
        logger.log_system('error', f'API control download error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

# Servers Management Endpoints
@api_bp.route('/servers')
@require_api_key
@normal_rate_limit(requests_per_minute=40)
def list_servers():
    """List all servers"""
    try:
        servers = Server.query.all()
        
        servers_data = []
        for server in servers:
            servers_data.append({
                'id': server.id,
                'name': server.name,
                'description': server.description,
                'host': server.host,
                'port': server.port,
                'protocol': server.protocol.value,
                'base_path': server.base_path,
                'status': server.status.value,
                'content_types': server.content_types_list,
                'disk_usage': server.disk_usage_dict,
                'last_check': server.last_check.isoformat() if server.last_check else None,
                'created_at': server.created_at.isoformat() if server.created_at else None
            })
        
        return jsonify({'servers': servers_data})
        
    except Exception as e:
        logger.log_system('error', f'API list servers error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/servers/<int:server_id>/test')
@require_api_key
@strict_rate_limit(requests_per_minute=15)
def test_server(server_id):
    """Test server connectivity"""
    try:
        server = Server.query.get_or_404(server_id)
        
        from app.services.file_transfer_service import FileTransferService
        transfer_service = FileTransferService()
        
        is_connected = transfer_service.test_connection(server)
        
        # Update server status
        if is_connected:
            server.update_status(ServerStatus.ONLINE)
        else:
            server.update_status(ServerStatus.OFFLINE)
        
        db.session.commit()
        
        return jsonify({
            'server_id': server.id,
            'connected': is_connected,
            'status': server.status.value,
            'tested_at': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.log_system('error', f'API test server error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

# M3U Processing Endpoints
@api_bp.route('/m3u/parse', methods=['POST'])
@require_api_key
@strict_rate_limit(requests_per_minute=15)
def parse_m3u():
    """Parse M3U content and return structured data"""
    try:
        data = request.get_json()
        m3u_content = data.get('content')
        
        if not m3u_content:
            return jsonify({'error': 'M3U content is required'}), 400
        
        # Parse M3U content
        import tempfile
        import os
        
        # Save content to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u', delete=False) as temp_file:
            temp_file.write(m3u_content)
            temp_file_path = temp_file.name
        
        try:
            content_items = m3u_parser.parse_m3u_file(temp_file_path)
            
            # Filter by quality
            accepted_qualities = current_app.config.get('ACCEPTED_QUALITIES', ['480p', '720p', '1080p'])
            filtered_items = [
                item for item in content_items 
                if item['quality'] in accepted_qualities
            ]
            
            return jsonify({
                'total_items': len(content_items),
                'filtered_items': len(filtered_items),
                'accepted_qualities': accepted_qualities,
                'items': filtered_items[:50]  # Return first 50 items
            })
            
        finally:
            os.unlink(temp_file_path)
        
    except Exception as e:
        logger.log_system('error', f'API parse M3U error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

# Webhook Endpoints
@api_bp.route('/webhooks/download/progress', methods=['POST'])
@require_webhook_signature
def webhook_download_progress():
    """Receive download progress updates from external systems"""
    try:
        data = request.get_json()
        download_id = data.get('download_id')
        progress = data.get('progress', 0)
        speed = data.get('speed')
        eta = data.get('eta')
        
        if not download_id:
            return jsonify({'error': 'download_id is required'}), 400
        
        download = Download.query.get(download_id)
        if not download:
            return jsonify({'error': 'Download not found'}), 404
        
        # Update progress
        download.progress_percentage = min(max(progress, 0), 100)
        if speed:
            download.download_speed = speed
        if eta:
            download.estimated_time = eta
        
        db.session.commit()
        
        return jsonify({'message': 'Progress updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        logger.log_system('error', f'Webhook progress error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/webhooks/download/completed', methods=['POST'])
@require_webhook_signature
def webhook_download_completed():
    """Receive download completion notifications"""
    try:
        data = request.get_json()
        download_id = data.get('download_id')
        file_path = data.get('file_path')
        file_size = data.get('file_size')
        
        if not download_id:
            return jsonify({'error': 'download_id is required'}), 400
        
        download = Download.query.get(download_id)
        if not download:
            return jsonify({'error': 'Download not found'}), 404
        
        # Mark as completed
        download.mark_completed()
        if file_path:
            download.local_file_path = file_path
        if file_size:
            download.file_size = file_size
        
        db.session.commit()
        
        # Trigger transfer if server is configured
        if download.server:
            from workers.transfer_worker import transfer_task
            transfer_task.delay(download.id)
        
        return jsonify({'message': 'Download completion processed'})
        
    except Exception as e:
        db.session.rollback()
        logger.log_system('error', f'Webhook completion error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

# Search and Statistics Endpoints
@api_bp.route('/search')
@require_api_key
@adaptive_rate_limit()
def search_content():
    """Search content in the library"""
    try:
        query = request.args.get('q', '')
        content_type = request.args.get('content_type')
        server_id = request.args.get('server_id', type=int)
        limit = min(request.args.get('limit', 20, type=int), 100)
        
        search_query = Download.query.filter_by(status=DownloadStatus.COMPLETED)
        
        if query:
            search_query = search_query.filter(Download.title.ilike(f'%{query}%'))
        
        if content_type:
            search_query = search_query.filter_by(content_type=content_type)
        
        if server_id:
            search_query = search_query.filter_by(server_id=server_id)
        
        results = search_query.order_by(Download.completed_at.desc()).limit(limit).all()
        
        results_data = []
        for result in results:
            results_data.append({
                'id': result.id,
                'title': result.title,
                'content_type': result.content_type,
                'quality': result.quality,
                'year': result.year,
                'season': result.season,
                'episode': result.episode,
                'server': result.server.name if result.server else None,
                'file_size': result.file_size,
                'completed_at': result.completed_at.isoformat() if result.completed_at else None,
                'tmdb_id': result.tmdb_id,
                'tmdb_poster': result.tmdb_poster
            })
        
        return jsonify({
            'query': query,
            'total_results': len(results_data),
            'results': results_data
        })
        
    except Exception as e:
        logger.log_system('error', f'API search error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@api_bp.route('/stats/summary')
@require_api_key
@relaxed_rate_limit(requests_per_minute=20)
def stats_summary():
    """Get comprehensive system statistics"""
    try:
        # Downloads stats
        download_stats = {
            'total': Download.query.count(),
            'by_status': {},
            'by_content_type': {},
            'by_quality': {}
        }
        
        # Count by status
        for status in DownloadStatus:
            count = Download.query.filter_by(status=status).count()
            download_stats['by_status'][status.value] = count
        
        # Count by content type
        for content_type in ['movie', 'series', 'novela']:
            count = Download.query.filter_by(content_type=content_type).count()
            download_stats['by_content_type'][content_type] = count
        
        # Count by quality
        for quality in ['480p', '720p', '1080p']:
            count = Download.query.filter_by(quality=quality).count()
            download_stats['by_quality'][quality] = count
        
        # Server stats
        server_stats = {
            'total': Server.query.count(),
            'online': Server.query.filter_by(status=ServerStatus.ONLINE).count(),
            'by_protocol': {}
        }
        
        # Recent activity
        recent_activity = UserActivityLog.query.order_by(
            UserActivityLog.timestamp.desc()
        ).limit(10).all()
        
        activity_data = [
            {
                'action': activity.action,
                'timestamp': activity.timestamp.isoformat(),
                'user_id': activity.user_id
            }
            for activity in recent_activity
        ]
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'downloads': download_stats,
            'servers': server_stats,
            'recent_activity': activity_data
        })
        
    except Exception as e:
        logger.log_system('error', f'API stats summary error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

# Error handlers
@api_bp.errorhandler(404)
def api_not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@api_bp.errorhandler(405)
def api_method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@api_bp.errorhandler(500)
def api_internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500
