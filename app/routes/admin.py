from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.users import User, UserRole
from app.models.downloads import Download
from app.models.servers import Server
from app.models.logs import SystemLog, UserActivityLog
from app.services.logging_service import LoggingService
from app.services.cache_service import cache_service
from app.utils.cache_manager import get_cache_stats, cache_manager, cleanup_expired_cache, warm_cache
from app import db
import os
import psutil

admin_bp = Blueprint('admin', __name__)
logger = LoggingService()

@admin_bp.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard"""
    if not current_user.is_admin():
        flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Get system data
        users = User.query.all()
        downloads = Download.query.all()
        servers = Server.query.all()
        
        # Get system configuration
        config = current_app.config
        
        return render_template('admin/dashboard.html',
                             users=users,
                             downloads=downloads,
                             servers=servers,
                             config=config)
    except Exception as e:
        logger.log_system('error', f'Error loading admin dashboard: {str(e)}')
        flash('Erro ao carregar painel administrativo.', 'error')
        return render_template('admin/dashboard.html')

@admin_bp.route('/admin/users')
@login_required
def admin_users():
    """User management"""
    if not current_user.is_admin():
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.dashboard'))
    
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/api/admin/system_status')
@login_required
def api_system_status():
    """Get system status information"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        # Get CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # Get memory usage
        memory = psutil.virtual_memory()
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_usage = {
            'total': round(disk.total / (1024**3), 1),  # GB
            'used': round(disk.used / (1024**3), 1),   # GB
            'free': round(disk.free / (1024**3), 1),   # GB
            'percentage': round((disk.used / disk.total) * 100, 1)
        }
        
        # Check service statuses
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            db_status = 'online'
        except:
            db_status = 'offline'
        
        try:
            # Test Redis connection (simplified)
            redis_status = 'online'
        except:
            redis_status = 'offline'
        
        # Check Celery workers (simplified)
        celery_status = 'online'
        
        return jsonify({
            'success': True,
            'status': {
                'cpu_usage': cpu_usage,
                'memory_usage': memory.percent,
                'disk_usage': disk_usage,
                'db_status': db_status,
                'redis_status': redis_status,
                'celery_status': celery_status
            }
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting system status: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/recent_activity')
@login_required
def api_recent_activity():
    """Get recent user activity"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        activities = UserActivityLog.query.join(User).order_by(
            UserActivityLog.timestamp.desc()
        ).limit(10).all()
        
        activity_data = []
        for activity in activities:
            activity_data.append({
                'action': activity.action,
                'username': activity.user.username,
                'timestamp': activity.timestamp.isoformat(),
                'ip_address': activity.ip_address
            })
        
        return jsonify({
            'success': True,
            'activities': activity_data
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting recent activity: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/cleanup_logs', methods=['POST'])
@login_required
def api_cleanup_logs():
    """Clean up old logs"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        deleted_count = logger.cleanup_old_logs()
        
        logger.log_user_activity(
            current_user.id,
            'logs_cleanup',
            {'deleted_count': deleted_count}
        )
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.log_system('error', f'Error cleaning up logs: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/admin/logs')
@login_required
def admin_logs():
    """Logs viewer page"""
    if not current_user.is_admin():
        flash('Acesso negado.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('admin/logs.html')

@admin_bp.route('/api/admin/log_statistics')
@login_required
def api_log_statistics():
    """Get log statistics by level"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        stats = logger.get_log_statistics()
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting log statistics: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/logs')
@login_required
def api_logs():
    """Get paginated logs with filters"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        log_type = request.args.get('log_type', '')
        level = request.args.get('level', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        search = request.args.get('search', '')
        
        # Build query (simplified to system logs for now)
        query = SystemLog.query
        
        # Apply filters
        if level:
            from app.models.logs import LogLevel
            query = query.filter_by(level=LogLevel(level))
        
        if date_from:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(SystemLog.timestamp >= date_from_obj)
        
        if date_to:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(SystemLog.timestamp <= date_to_obj)
        
        if search:
            query = query.filter(SystemLog.message.ilike(f'%{search}%'))
        
        # Get paginated results
        logs_paginated = query.order_by(SystemLog.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Format logs
        logs_data = []
        for log in logs_paginated.items:
            log_data = {
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'level': log.level.value,
                'message': log.message,
                'type': log_type or 'system',
                'source': getattr(log, 'source', None)
            }
            logs_data.append(log_data)
        
        return jsonify({
            'success': True,
            'logs': logs_data,
            'pagination': {
                'page': logs_paginated.page,
                'per_page': logs_paginated.per_page,
                'total': logs_paginated.total,
                'pages': logs_paginated.pages,
                'has_prev': logs_paginated.has_prev,
                'has_next': logs_paginated.has_next,
                'prev_num': logs_paginated.prev_num,
                'next_num': logs_paginated.next_num
            }
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting logs: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# ================================
# ROTAS DE GERENCIAMENTO DE CACHE
# ================================

@admin_bp.route('/admin/cache')
@login_required
def admin_cache():
    """Página de gerenciamento de cache"""
    if not current_user.is_admin():
        flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('admin/cache.html')

@admin_bp.route('/api/admin/cache/stats')
@login_required
def api_cache_stats():
    """Get cache statistics"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        # Obter estatísticas gerais do cache
        cache_stats = get_cache_stats()
        
        # Obter saúde do cache
        cache_health = cache_service.get_cache_health()
        
        # Estatísticas de memória Redis
        memory_info = {}
        try:
            redis_client = cache_manager.l2_cache.redis_client
            if redis_client:
                info = redis_client.info('memory')
                memory_info = {
                    'used_memory': info.get('used_memory', 0),
                    'used_memory_human': info.get('used_memory_human', '0B'),
                    'used_memory_peak': info.get('used_memory_peak', 0),
                    'used_memory_peak_human': info.get('used_memory_peak_human', '0B'),
                    'maxmemory': info.get('maxmemory', 0),
                    'maxmemory_human': info.get('maxmemory_human', 'unlimited')
                }
        except Exception as e:
            logger.log_system('warning', f'Erro obtendo info Redis: {str(e)}')
        
        return jsonify({
            'success': True,
            'cache_stats': cache_stats,
            'cache_health': cache_health,
            'memory_info': memory_info,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting cache stats: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/cache/warm', methods=['POST'])
@login_required
def api_cache_warm():
    """Warm up cache"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        # Aquecimento global
        warm_cache()
        
        # Aquecimento crítico
        critical_results = cache_service.warm_critical_cache()
        
        logger.log_system('info', f'Cache warmed by admin user {current_user.username}')
        
        return jsonify({
            'success': True,
            'message': 'Cache aquecido com sucesso',
            'results': critical_results
        })
        
    except Exception as e:
        logger.log_system('error', f'Error warming cache: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/cache/cleanup', methods=['POST'])
@login_required
def api_cache_cleanup():
    """Clean up expired cache"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        # Limpeza global
        global_cleaned = cleanup_expired_cache()
        
        # Limpeza específica
        service_results = cache_service.cleanup_expired_cache()
        
        total_cleaned = global_cleaned + sum(service_results.values())
        
        logger.log_system('info', f'Cache cleaned by admin user {current_user.username}: {total_cleaned} keys removed')
        
        return jsonify({
            'success': True,
            'message': f'{total_cleaned} chaves removidas do cache',
            'global_cleaned': global_cleaned,
            'service_results': service_results,
            'total_cleaned': total_cleaned
        })
        
    except Exception as e:
        logger.log_system('error', f'Error cleaning cache: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/cache/invalidate', methods=['POST'])
@login_required
def api_cache_invalidate():
    """Invalidate specific cache patterns"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        data = request.get_json() or {}
        
        # Padrões específicos ou categoria
        patterns = data.get('patterns', [])
        category = data.get('category', '')
        
        if category:
            # Invalidar por categoria
            category_patterns = {
                'downloads': ['download_status:*', 'download_progress:*', 'download:*'],
                'users': ['user:*', 'session:*'],
                'servers': ['server_status:*', 'server_stats:*', 'all_servers_status'],
                'tmdb': ['tmdb:*', 'tmdb_genres:*', 'tmdb_details:*'],
                'system': ['system_stats', 'dashboard_data', 'recent_logs:*'],
                'all': ['*']
            }
            
            patterns = category_patterns.get(category, [])
        
        if not patterns:
            return jsonify({'success': False, 'error': 'Nenhum padrão especificado'}), 400
        
        # Invalidar padrões
        results = cache_service.bulk_invalidate(patterns)
        total_invalidated = sum(results.values())
        
        logger.log_system('info', f'Cache patterns invalidated by admin user {current_user.username}: {patterns}')
        
        return jsonify({
            'success': True,
            'message': f'{total_invalidated} chaves invalidadas',
            'patterns': patterns,
            'results': results,
            'total_invalidated': total_invalidated
        })
        
    except Exception as e:
        logger.log_system('error', f'Error invalidating cache: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/cache/keys')
@login_required
def api_cache_keys():
    """List cache keys with patterns"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        pattern = request.args.get('pattern', '*')
        limit = min(int(request.args.get('limit', 100)), 1000)  # Max 1000 keys
        
        keys_info = []
        
        try:
            redis_client = cache_manager.l2_cache.redis_client
            if redis_client:
                # Obter chaves Redis
                redis_pattern = f"mediadown:cache:{pattern}"
                redis_keys = redis_client.keys(redis_pattern)[:limit]
                
                for key in redis_keys:
                    try:
                        ttl = redis_client.ttl(key)
                        key_type = redis_client.type(key)
                        size = len(str(redis_client.get(key) or ''))
                        
                        # Limpar prefixo para exibição
                        display_key = key.replace('mediadown:cache:', '')
                        
                        keys_info.append({
                            'key': display_key,
                            'ttl': ttl,
                            'type': key_type,
                            'size': size
                        })
                    except:
                        continue
                        
        except Exception as e:
            logger.log_system('warning', f'Erro listando chaves Redis: {str(e)}')
        
        # Ordenar por TTL (chaves que expiram primeiro)
        keys_info.sort(key=lambda x: x['ttl'] if x['ttl'] > 0 else float('inf'))
        
        return jsonify({
            'success': True,
            'keys': keys_info,
            'total': len(keys_info),
            'pattern': pattern,
            'limit': limit
        })
        
    except Exception as e:
        logger.log_system('error', f'Error listing cache keys: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# ================================
# ROTAS DE GERENCIAMENTO DE RATE LIMITING
# ================================

@admin_bp.route('/admin/rate-limits')
@login_required
def admin_rate_limits():
    """Página de gerenciamento de rate limiting"""
    if not current_user.is_admin():
        flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('admin/rate_limits.html')

@admin_bp.route('/api/admin/rate-limits/stats')
@login_required
def api_rate_limits_stats():
    """Get rate limiting statistics"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        from app.utils.advanced_rate_limiter import rate_limiter
        
        # Obter estatísticas globais
        global_stats = rate_limiter.get_global_stats()
        
        # Estatísticas do Redis para rate limiting
        redis_stats = {}
        try:
            redis_client = rate_limiter.redis_client
            if redis_client:
                # Contar chaves de rate limiting
                rate_limit_keys = redis_client.keys(f"{rate_limiter.key_prefix}:*")
                
                redis_stats = {
                    'total_keys': len(rate_limit_keys),
                    'sliding_window_keys': len([k for k in rate_limit_keys if 'sliding' in k]),
                    'token_bucket_keys': len([k for k in rate_limit_keys if 'token_bucket' in k]),
                    'blacklist_keys': len([k for k in rate_limit_keys if 'blacklist' in k]),
                    'whitelist_keys': len([k for k in rate_limit_keys if 'whitelist' in k])
                }
        except Exception as e:
            logger.log_system('warning', f'Erro obtendo stats Redis rate limiting: {str(e)}')
        
        return jsonify({
            'success': True,
            'global_stats': global_stats,
            'redis_stats': redis_stats,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting rate limit stats: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/rate-limits/clients')
@login_required
def api_rate_limits_clients():
    """List clients with rate limit data"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        from app.utils.advanced_rate_limiter import rate_limiter
        import json
        
        limit = min(int(request.args.get('limit', 50)), 200)
        pattern = request.args.get('pattern', '*')
        
        clients_data = []
        
        if rate_limiter.redis_client:
            # Buscar todas as chaves de rate limiting
            search_pattern = f"{rate_limiter.key_prefix}:{pattern}:*"
            keys = rate_limiter.redis_client.keys(search_pattern)
            
            # Agrupar por cliente
            clients = {}
            for key in keys[:limit * 10]:  # Pegar mais chaves para agrupar
                try:
                    # Extrair client_id da chave
                    parts = key.split(':')
                    if len(parts) >= 3:
                        client_id = parts[2]
                        
                        if client_id not in clients:
                            clients[client_id] = {
                                'client_id': client_id,
                                'endpoints': {},
                                'total_requests': 0,
                                'last_activity': None
                            }
                        
                        # Obter informações específicas do endpoint
                        if len(parts) >= 4:
                            endpoint = parts[3]
                            
                            if 'sliding' in key:
                                count = rate_limiter.redis_client.zcard(key)
                                # Obter timestamp mais recente
                                recent = rate_limiter.redis_client.zrevrange(key, 0, 0, withscores=True)
                                last_time = recent[0][1] if recent else None
                                
                                clients[client_id]['endpoints'][endpoint] = {
                                    'type': 'sliding_window',
                                    'current_count': count,
                                    'last_request': last_time
                                }
                                clients[client_id]['total_requests'] += count
                                
                                if last_time and (not clients[client_id]['last_activity'] or last_time > clients[client_id]['last_activity']):
                                    clients[client_id]['last_activity'] = last_time
                            
                            elif 'token_bucket' in key:
                                bucket_data = rate_limiter.redis_client.get(key)
                                if bucket_data:
                                    bucket = json.loads(bucket_data)
                                    clients[client_id]['endpoints'][endpoint] = {
                                        'type': 'token_bucket',
                                        'tokens_remaining': bucket.get('tokens', 0),
                                        'capacity': bucket.get('capacity', 0),
                                        'last_refill': bucket.get('last_refill', 0)
                                    }
                except Exception:
                    continue
            
            # Converter para lista e ordenar por atividade
            clients_data = list(clients.values())
            clients_data.sort(key=lambda x: x['last_activity'] or 0, reverse=True)
        
        return jsonify({
            'success': True,
            'clients': clients_data[:limit],
            'total_found': len(clients_data),
            'limit': limit
        })
        
    except Exception as e:
        logger.log_system('error', f'Error getting rate limit clients: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/rate-limits/blacklist', methods=['POST'])
@login_required
def api_rate_limits_add_blacklist():
    """Add client to blacklist"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        from app.utils.advanced_rate_limiter import rate_limiter
        
        data = request.get_json() or {}
        client_id = data.get('client_id', '').strip()
        duration = data.get('duration', 3600)  # 1 hora por padrão
        reason = data.get('reason', 'Added by admin')
        
        if not client_id:
            return jsonify({'success': False, 'error': 'Client ID obrigatório'}), 400
        
        # Adicionar à blacklist
        rate_limiter.add_to_blacklist(client_id, duration)
        
        # Log da ação
        logger.log_system('warning', f'Client {client_id} added to blacklist by {current_user.username} for {duration}s. Reason: {reason}')
        
        return jsonify({
            'success': True,
            'message': f'Cliente {client_id} adicionado à blacklist por {duration} segundos',
            'client_id': client_id,
            'duration': duration,
            'reason': reason
        })
        
    except Exception as e:
        logger.log_system('error', f'Error adding to blacklist: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/rate-limits/reset/<client_id>', methods=['POST'])
@login_required
def api_rate_limits_reset_client(client_id):
    """Reset rate limits for a specific client"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Acesso negado'}), 403
    
    try:
        from app.utils.advanced_rate_limiter import rate_limiter
        
        # Resetar limites do cliente
        rate_limiter.reset_client_limits(client_id)
        
        # Log da ação
        logger.log_system('info', f'Rate limits reset for client {client_id} by {current_user.username}')
        
        return jsonify({
            'success': True,
            'message': f'Limites resetados para cliente {client_id}',
            'client_id': client_id
        })
        
    except Exception as e:
        logger.log_system('error', f'Error resetting client limits: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

