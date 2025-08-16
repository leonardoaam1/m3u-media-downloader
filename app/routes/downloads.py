from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models.downloads import Download, DownloadStatus, DownloadPriority
from app.models.servers import Server
from app.services.download_service import DownloadService
from app.services.m3u_parser import M3UParser
from app.services.logging_service import LoggingService
from app.utils.advanced_rate_limiter import normal_rate_limit, strict_rate_limit, relaxed_rate_limit
from app import db
import os
import tempfile

downloads_bp = Blueprint('downloads', __name__)
logger = LoggingService()
m3u_parser = M3UParser()

@downloads_bp.route('/downloads')
@login_required
@relaxed_rate_limit(requests_per_minute=100)
def downloads_list():
    """List all downloads"""
    # Get downloads with pagination
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    content_type_filter = request.args.get('content_type', '')
    
    query = Download.query
    
    # Apply filters
    if status_filter:
        query = query.filter_by(status=DownloadStatus(status_filter))
    if content_type_filter:
        query = query.filter_by(content_type=content_type_filter)
    
    # Add user filter for non-admin users
    if not current_user.is_admin():
        query = query.filter_by(user_id=current_user.id)
    
    downloads = query.order_by(Download.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('downloads/list.html', downloads=downloads)

@downloads_bp.route('/downloads/upload_m3u', methods=['GET', 'POST'])
@login_required
def upload_m3u():
    """Upload and process M3U file"""
    if not current_user.has_permission('upload_m3u'):
        flash('Você não tem permissão para fazer upload de listas M3U.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('downloads/upload_m3u.html')

@downloads_bp.route('/api/upload_m3u', methods=['POST'])
@login_required
@strict_rate_limit(requests_per_minute=15)
def api_upload_m3u():
    """API endpoint for M3U file upload and processing"""
    if not current_user.has_permission('upload_m3u'):
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
    
    try:
        # Check if file was uploaded
        if 'm3u_file' not in request.files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['m3u_file']
        upload_type = request.form.get('upload_type', 'new')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'}), 400
        
        # Validate file extension
        if not file.filename.lower().endswith(('.m3u', '.m3u8')):
            return jsonify({'success': False, 'error': 'Formato de arquivo inválido. Use .m3u ou .m3u8'}), 400
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"upload_{current_user.id}_{filename}")
        file.save(temp_path)
        
        logger.log_user_activity(
            current_user.id,
            'm3u_upload',
            {'filename': filename, 'upload_type': upload_type}
        )
        
        # Parse the uploaded M3U file
        content_items = m3u_parser.parse_m3u_file(temp_path)
        
        if upload_type == 'main':
            # Handle main list upload (replace existing)
            results = process_main_list(content_items, temp_path)
        else:
            # Handle new list upload (compare with main)
            results = process_new_list(content_items, temp_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.log_system('error', f'Error processing M3U upload: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

def process_main_list(content_items, file_path):
    """Process main list upload"""
    # Store main list reference (implementation depends on requirements)
    main_list_path = os.path.join(current_app.config['UPLOAD_DIR'], 'main_list.m3u')
    
    # Copy uploaded file as main list
    import shutil
    shutil.copy2(file_path, main_list_path)
    
    # Filter items by quality
    accepted_items = [item for item in content_items if is_quality_accepted(item['quality'])]
    filtered_count = len(content_items) - len(accepted_items)
    
    return {
        'total': len(content_items),
        'accepted': len(accepted_items),
        'filtered': filtered_count,
        'type': 'main_list'
    }

def process_new_list(content_items, file_path):
    """Process new list upload and compare with main"""
    main_list_path = os.path.join(current_app.config['UPLOAD_DIR'], 'main_list.m3u')
    
    if not os.path.exists(main_list_path):
        return {
            'success': False,
            'error': 'Lista principal não encontrada. Faça upload da lista principal primeiro.'
        }
    
    # Compare with main list
    new_items = m3u_parser.compare_m3u_lists(main_list_path, file_path)
    
    # Filter by quality
    accepted_items = [item for item in new_items if is_quality_accepted(item['quality'])]
    filtered_count = len(new_items) - len(accepted_items)
    
    # Store new items in session for next step
    from flask import session
    session['pending_downloads'] = accepted_items
    
    return {
        'total': len(content_items),
        'new_items': len(new_items),
        'accepted': len(accepted_items),
        'filtered': filtered_count,
        'type': 'comparison',
        'items': accepted_items[:10]  # Send first 10 items for preview
    }

def is_quality_accepted(quality):
    """Check if quality is accepted"""
    accepted_qualities = current_app.config['ACCEPTED_QUALITIES']
    return quality.lower() in [q.lower() for q in accepted_qualities]

@downloads_bp.route('/api/create_downloads', methods=['POST'])
@login_required
@strict_rate_limit(requests_per_minute=20)
def api_create_downloads():
    """Create downloads from selected items"""
    if not current_user.has_permission('upload_m3u'):
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
    
    try:
        data = request.get_json()
        selected_items = data.get('selected_items', [])
        server_configs = data.get('server_configs', {})
        
        if not selected_items:
            return jsonify({'success': False, 'error': 'Nenhum item selecionado'}), 400
        
        # Get pending downloads from session
        from flask import session
        pending_downloads = session.get('pending_downloads', [])
        
        if not pending_downloads:
            return jsonify({'success': False, 'error': 'Dados de sessão expirados'}), 400
        
        created_downloads = []
        
        for item_index in selected_items:
            if item_index < len(pending_downloads):
                item = pending_downloads[item_index]
                server_config = server_configs.get(str(item_index), {})
                
                # Get server
                server_id = server_config.get('server_id')
                if not server_id:
                    # Use auto-suggestion
                    servers = Server.query.all()
                    suggestion = m3u_parser.suggest_server_and_directory(item, servers)
                    if suggestion['server']:
                        server_id = suggestion['server'].id
                        destination_path = suggestion['directory']
                    else:
                        continue
                else:
                    server = Server.query.get(server_id)
                    if not server:
                        continue
                    destination_path = server_config.get('destination_path', server.base_path)
                
                # Create download record
                download = Download(
                    title=item['title'],
                    content_type=item['content_type'],
                    quality=item['quality'],
                    url=item['url'],
                    server_id=server_id,
                    destination_path=destination_path,
                    user_id=current_user.id,
                    season=item.get('season'),
                    episode=item.get('episode'),
                    episode_title=item.get('episode_title'),
                    year=item.get('year'),
                    priority=determine_priority(item)
                )
                
                db.session.add(download)
                created_downloads.append(download)
        
        db.session.commit()
        
        # Clear session data
        session.pop('pending_downloads', None)
        
        # Log activity
        logger.log_user_activity(
            current_user.id,
            'downloads_created',
            {'count': len(created_downloads)}
        )
        
        # Trigger download processing
        from workers.download_worker import process_download_queue
        process_download_queue.delay()
        
        return jsonify({
            'success': True,
            'created_count': len(created_downloads),
            'downloads': [{'id': d.id, 'title': d.title} for d in created_downloads]
        })
        
    except Exception as e:
        db.session.rollback()
        logger.log_system('error', f'Error creating downloads: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

def determine_priority(item):
    """Determine download priority based on content"""
    from datetime import datetime
    current_year = datetime.now().year
    
    # High priority: Recent movies (last 2 years)
    if item['content_type'] == 'movie' and item.get('year'):
        if current_year - item['year'] <= 2:
            return DownloadPriority.HIGH
    
    # Medium priority: Series and newer content
    if item['content_type'] in ['series', 'novela']:
        return DownloadPriority.MEDIUM
    
    # Low priority: Old content
    if item.get('year') and current_year - item['year'] > 5:
        return DownloadPriority.LOW
    
    return DownloadPriority.MEDIUM

@downloads_bp.route('/downloads/<int:download_id>')
@login_required
def download_detail(download_id):
    """Show download details"""
    download = Download.query.get_or_404(download_id)
    
    # Check permissions
    if not current_user.is_admin() and download.user_id != current_user.id:
        flash('Acesso negado.', 'error')
        return redirect(url_for('downloads.downloads_list'))
    
    return render_template('downloads/detail.html', download=download)

@downloads_bp.route('/api/downloads/<int:download_id>/control', methods=['POST'])
@login_required
@strict_rate_limit(requests_per_minute=30)
def control_download(download_id):
    """Control download (pause, resume, cancel, retry)"""
    download = Download.query.get_or_404(download_id)
    
    # Check permissions
    if not current_user.has_permission('manage_downloads') and download.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
    
    action = request.json.get('action')
    
    try:
        if action == 'pause':
            download.pause()
        elif action == 'resume':
            download.resume()
        elif action == 'cancel':
            download.cancel()
        elif action == 'retry':
            download.retry()
        else:
            return jsonify({'success': False, 'error': 'Ação inválida'}), 400
        
        db.session.commit()
        
        logger.log_user_activity(
            current_user.id,
            f'download_{action}',
            {'download_id': download_id, 'title': download.title}
        )
        
        return jsonify({'success': True, 'status': download.status.value})
        
    except Exception as e:
        db.session.rollback()
        logger.log_system('error', f'Error controlling download {download_id}: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@downloads_bp.route('/api/downloads/<int:download_id>/status')
@login_required
@normal_rate_limit(requests_per_minute=60)
def get_download_status(download_id):
    """Get current download status"""
    download = Download.query.get_or_404(download_id)
    
    # Check permissions
    if not current_user.is_admin() and download.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
    
    return jsonify({
        'success': True,
        'download': {
            'id': download.id,
            'status': download.status.value,
            'progress': download.progress_percentage or 0,
            'speed': download.download_speed,
            'eta': download.estimated_time,
            'error': download.error_message
        }
    })

@downloads_bp.route('/api/downloads/<int:download_id>/logs')
@login_required
@normal_rate_limit(requests_per_minute=40)
def get_download_logs(download_id):
    """Get download logs"""
    download = Download.query.get_or_404(download_id)
    
    # Check permissions
    if not current_user.is_admin() and download.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
    
    try:
        from app.models.logs import DownloadLog
        
        logs = DownloadLog.query.filter_by(download_id=download_id).order_by(
            DownloadLog.timestamp.desc()
        ).limit(50).all()
        
        logs_data = []
        for log in logs:
            logs_data.append({
                'timestamp': log.timestamp.isoformat(),
                'level': log.level.value,
                'message': log.message,
                'progress_percentage': log.progress_percentage,
                'download_speed': log.download_speed,
                'estimated_time': log.estimated_time
            })
        
        return jsonify({
            'success': True,
            'logs': logs_data
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting download logs: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

