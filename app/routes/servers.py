from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.servers import Server, ServerStatus, ServerProtocol
from app.services.file_transfer_service import FileTransferService
from app.services.server_monitor_service import ServerMonitorService
from app.services.logging_service import LoggingService
from app import db
import json

servers_bp = Blueprint('servers', __name__)
transfer_service = FileTransferService()
monitor_service = ServerMonitorService()
logger = LoggingService()

@servers_bp.route('/servers')
@login_required
def servers_list():
    """List all servers"""
    if not current_user.has_permission('view_servers'):
        flash('Você não tem permissão para ver servidores.', 'error')
        return redirect(url_for('main.dashboard'))
    
    servers = Server.query.all()
    
    # Get server statistics
    total_servers = len(servers)
    online_servers = len([s for s in servers if s.status == ServerStatus.ONLINE])
    
    # Get disk usage summary
    total_space = 0
    used_space = 0
    
    for server in servers:
        disk_usage = server.disk_usage_dict
        if disk_usage and 'total' in disk_usage:
            try:
                # Convert GB to bytes for calculation
                total_gb = float(disk_usage['total'].replace('GB', ''))
                used_gb = float(disk_usage['used'].replace('GB', ''))
                total_space += total_gb
                used_space += used_gb
            except:
                pass
    
    return render_template('servers/list.html', 
                         servers=servers,
                         total_servers=total_servers,
                         online_servers=online_servers,
                         total_space=total_space,
                         used_space=used_space)

@servers_bp.route('/servers/new', methods=['GET', 'POST'])
@login_required
def new_server():
    """Create new server"""
    if not current_user.has_permission('manage_servers'):
        flash('Você não tem permissão para gerenciar servidores.', 'error')
        return redirect(url_for('servers.servers_list'))
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            description = request.form.get('description', '')
            host = request.form.get('host')
            protocol = request.form.get('protocol')
            port = int(request.form.get('port', 22))
            username = request.form.get('username')
            password = request.form.get('password')
            base_path = request.form.get('base_path')
            content_types = request.form.getlist('content_types')
            
            # Validate required fields
            if not all([name, host, protocol, username, base_path]):
                flash('Por favor, preencha todos os campos obrigatórios.', 'error')
                return render_template('servers/new.html')
            
            # Create directory structure based on content types
            directory_structure = {}
            if 'movie' in content_types:
                directory_structure['movie'] = [
                    'Acao', 'Animacao_Infantil', 'Animes', 'Cinema', 
                    'Comedia', 'Documentarios', 'Drama', 'Faroeste',
                    'Ficcao_Fantasia', 'Filmes_Legendados', 'Guerra',
                    'Lancamentos', 'Marvel', 'Romance', 'Suspense', 'Terror'
                ]
            if 'series' in content_types:
                directory_structure['series'] = [
                    'Amazon', 'Animes_(Dub)', 'Animes_(Leg)', 'Apple_Tv',
                    'Desenhos_Animados', 'DiscoveryPlus', 'DisneyPlus',
                    'Drama', 'Globo_Play', 'HBOMax', 'Lionsgate', 'Looke',
                    'Natgeo', 'Netflix', 'ParamountPlus', 'Star_Plus'
                ]
            if 'novela' in content_types:
                directory_structure['novela'] = ['Novelas']
            
            # Create server
            server = Server(
                name=name,
                description=description,
                host=host,
                protocol=ServerProtocol(protocol),
                port=port,
                username=username,
                base_path=base_path,
                content_types=content_types,
                directory_structure=directory_structure
            )
            
            if password:
                server.set_password(password)
            
            db.session.add(server)
            db.session.commit()
            
            logger.log_user_activity(
                current_user.id,
                'server_created',
                {'server_id': server.id, 'server_name': server.name}
            )
            
            flash(f'Servidor {server.name} criado com sucesso!', 'success')
            return redirect(url_for('servers.server_detail', server_id=server.id))
            
        except Exception as e:
            db.session.rollback()
            logger.log_system('error', f'Error creating server: {str(e)}')
            flash(f'Erro ao criar servidor: {str(e)}', 'error')
    
    return render_template('servers/new.html')

@servers_bp.route('/servers/<int:server_id>')
@login_required
def server_detail(server_id):
    """Show server details"""
    if not current_user.has_permission('view_servers'):
        flash('Você não tem permissão para ver servidores.', 'error')
        return redirect(url_for('main.dashboard'))
    
    server = Server.query.get_or_404(server_id)
    
    # Get server downloads
    from app.models.downloads import Download
    recent_downloads = Download.query.filter_by(server_id=server_id).order_by(
        Download.created_at.desc()
    ).limit(10).all()
    
    return render_template('servers/detail.html', 
                         server=server,
                         recent_downloads=recent_downloads)

@servers_bp.route('/servers/<int:server_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_server(server_id):
    """Edit server"""
    if not current_user.has_permission('manage_servers'):
        flash('Você não tem permissão para gerenciar servidores.', 'error')
        return redirect(url_for('servers.servers_list'))
    
    server = Server.query.get_or_404(server_id)
    
    if request.method == 'POST':
        try:
            # Update server fields
            server.name = request.form.get('name')
            server.description = request.form.get('description', '')
            server.host = request.form.get('host')
            server.protocol = ServerProtocol(request.form.get('protocol'))
            server.port = int(request.form.get('port', 22))
            server.username = request.form.get('username')
            server.base_path = request.form.get('base_path')
            server.content_types = json.dumps(request.form.getlist('content_types'))
            
            password = request.form.get('password')
            if password:
                server.set_password(password)
            
            db.session.commit()
            
            logger.log_user_activity(
                current_user.id,
                'server_updated',
                {'server_id': server.id, 'server_name': server.name}
            )
            
            flash(f'Servidor {server.name} atualizado com sucesso!', 'success')
            return redirect(url_for('servers.server_detail', server_id=server.id))
            
        except Exception as e:
            db.session.rollback()
            logger.log_system('error', f'Error updating server: {str(e)}')
            flash(f'Erro ao atualizar servidor: {str(e)}', 'error')
    
    return render_template('servers/edit.html', server=server)

@servers_bp.route('/api/servers/<int:server_id>/test')
@login_required
def test_server_connection(server_id):
    """Test server connection"""
    if not current_user.has_permission('manage_servers'):
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
    
    server = Server.query.get_or_404(server_id)
    
    try:
        # Test connection
        is_connected = transfer_service.test_connection(server)
        
        if is_connected:
            server.update_status(ServerStatus.ONLINE)
            # Try to update disk usage
            monitor_service.update_disk_usage(server)
        else:
            server.update_status(ServerStatus.OFFLINE)
        
        db.session.commit()
        
        logger.log_server(
            server.id,
            'info',
            f'Connection test: {"successful" if is_connected else "failed"}',
            action='test_connection',
            connection_status='success' if is_connected else 'failed'
        )
        
        return jsonify({
            'success': True,
            'connected': is_connected,
            'status': server.status.value,
            'message': 'Conexão bem-sucedida!' if is_connected else 'Falha na conexão'
        })
        
    except Exception as e:
        logger.log_system('error', f'Error testing server connection: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@servers_bp.route('/api/servers/test_all')
@login_required
def test_all_servers():
    """Test all servers connection"""
    if not current_user.has_permission('manage_servers'):
        return jsonify({'success': False, 'error': 'Permissão negada'}), 403
    
    try:
        servers = Server.query.all()
        results = []
        
        for server in servers:
            is_connected = transfer_service.test_connection(server)
            server.update_status(ServerStatus.ONLINE if is_connected else ServerStatus.OFFLINE)
            
            if is_connected:
                monitor_service.update_disk_usage(server)
            
            results.append({
                'id': server.id,
                'name': server.name,
                'connected': is_connected,
                'status': server.status.value
            })
        
        db.session.commit()
        
        online_count = len([r for r in results if r['connected']])
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total': len(results),
                'online': online_count,
                'offline': len(results) - online_count
            }
        })
        
    except Exception as e:
        logger.log_system('error', f'Error testing all servers: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

