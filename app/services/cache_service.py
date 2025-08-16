#!/usr/bin/env python3
"""
Serviço de cache especializado para o MediaDown
"""

import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from app.utils.cache_manager import cache_manager, CacheKey, cached, invalidate_cache_pattern

logger = logging.getLogger(__name__)

class CacheService:
    """Serviço centralizado de cache para diferentes módulos"""
    
    def __init__(self):
        self.default_ttl = 3600  # 1 hora
        self.short_ttl = 300     # 5 minutos
        self.long_ttl = 86400    # 24 horas
    
    # ================================
    # CACHE DE DOWNLOADS
    # ================================
    
    def cache_download_info(self, url: str, info: Dict, ttl: Optional[int] = None) -> bool:
        """Cache informações de download"""
        cache_key = CacheKey.download_key(url)
        return cache_manager.set(cache_key, info, l2_ttl=ttl or self.default_ttl)
    
    def get_download_info(self, url: str) -> Optional[Dict]:
        """Obter informações de download do cache"""
        cache_key = CacheKey.download_key(url)
        return cache_manager.get(cache_key)
    
    def cache_download_status(self, download_id: int, status: Dict, ttl: Optional[int] = None) -> bool:
        """Cache status de download"""
        cache_key = CacheKey.generate("download_status", download_id)
        return cache_manager.set(cache_key, status, l2_ttl=ttl or self.short_ttl)
    
    def get_download_status(self, download_id: int) -> Optional[Dict]:
        """Obter status de download do cache"""
        cache_key = CacheKey.generate("download_status", download_id)
        return cache_manager.get(cache_key)
    
    def cache_download_progress(self, download_id: int, progress: Dict) -> bool:
        """Cache progresso de download (TTL curto)"""
        cache_key = CacheKey.generate("download_progress", download_id)
        return cache_manager.set(cache_key, progress, l1_ttl=30, l2_ttl=60)  # Cache muito curto
    
    def get_download_progress(self, download_id: int) -> Optional[Dict]:
        """Obter progresso de download do cache"""
        cache_key = CacheKey.generate("download_progress", download_id)
        return cache_manager.get(cache_key)
    
    def invalidate_download_cache(self, download_id: Optional[int] = None) -> int:
        """Invalidar cache de downloads"""
        if download_id:
            patterns = [
                f"download_status:{download_id}",
                f"download_progress:{download_id}"
            ]
        else:
            patterns = [
                "download_status:*",
                "download_progress:*"
            ]
        
        total_cleared = 0
        for pattern in patterns:
            total_cleared += invalidate_cache_pattern(pattern)
        
        return total_cleared
    
    # ================================
    # CACHE DE USUÁRIOS E SESSÕES
    # ================================
    
    def cache_user_data(self, user_id: int, data: Dict, ttl: Optional[int] = None) -> bool:
        """Cache dados do usuário"""
        cache_key = CacheKey.user_key(user_id, "profile")
        return cache_manager.set(cache_key, data, l2_ttl=ttl or self.default_ttl)
    
    def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Obter dados do usuário do cache"""
        cache_key = CacheKey.user_key(user_id, "profile")
        return cache_manager.get(cache_key)
    
    def cache_user_permissions(self, user_id: int, permissions: List[str], ttl: Optional[int] = None) -> bool:
        """Cache permissões do usuário"""
        cache_key = CacheKey.user_key(user_id, "permissions")
        return cache_manager.set(cache_key, permissions, l2_ttl=ttl or self.default_ttl)
    
    def get_user_permissions(self, user_id: int) -> Optional[List[str]]:
        """Obter permissões do usuário do cache"""
        cache_key = CacheKey.user_key(user_id, "permissions")
        return cache_manager.get(cache_key)
    
    def cache_session_data(self, session_id: str, data: Dict, ttl: Optional[int] = None) -> bool:
        """Cache dados da sessão"""
        cache_key = CacheKey.session_key(session_id)
        return cache_manager.set(cache_key, data, l2_ttl=ttl or self.short_ttl)
    
    def get_session_data(self, session_id: str) -> Optional[Dict]:
        """Obter dados da sessão do cache"""
        cache_key = CacheKey.session_key(session_id)
        return cache_manager.get(cache_key)
    
    def invalidate_user_cache(self, user_id: int) -> int:
        """Invalidar cache do usuário"""
        patterns = [
            f"user:{user_id}:*"
        ]
        
        total_cleared = 0
        for pattern in patterns:
            total_cleared += invalidate_cache_pattern(pattern)
        
        return total_cleared
    
    # ================================
    # CACHE DE SERVIDORES
    # ================================
    
    def cache_server_status(self, server_id: int, status: Dict, ttl: Optional[int] = None) -> bool:
        """Cache status do servidor"""
        cache_key = CacheKey.generate("server_status", server_id)
        return cache_manager.set(cache_key, status, l2_ttl=ttl or self.short_ttl)
    
    def get_server_status(self, server_id: int) -> Optional[Dict]:
        """Obter status do servidor do cache"""
        cache_key = CacheKey.generate("server_status", server_id)
        return cache_manager.get(cache_key)
    
    def cache_server_stats(self, server_id: int, stats: Dict, ttl: Optional[int] = None) -> bool:
        """Cache estatísticas do servidor"""
        cache_key = CacheKey.generate("server_stats", server_id)
        return cache_manager.set(cache_key, stats, l2_ttl=ttl or self.default_ttl)
    
    def get_server_stats(self, server_id: int) -> Optional[Dict]:
        """Obter estatísticas do servidor do cache"""
        cache_key = CacheKey.generate("server_stats", server_id)
        return cache_manager.get(cache_key)
    
    def cache_all_servers_status(self, servers_status: Dict, ttl: Optional[int] = None) -> bool:
        """Cache status de todos os servidores"""
        cache_key = CacheKey.generate("all_servers_status")
        return cache_manager.set(cache_key, servers_status, l2_ttl=ttl or self.short_ttl)
    
    def get_all_servers_status(self) -> Optional[Dict]:
        """Obter status de todos os servidores do cache"""
        cache_key = CacheKey.generate("all_servers_status")
        return cache_manager.get(cache_key)
    
    def invalidate_server_cache(self, server_id: Optional[int] = None) -> int:
        """Invalidar cache de servidores"""
        if server_id:
            patterns = [
                f"server_status:{server_id}",
                f"server_stats:{server_id}"
            ]
        else:
            patterns = [
                "server_status:*",
                "server_stats:*",
                "all_servers_status"
            ]
        
        total_cleared = 0
        for pattern in patterns:
            total_cleared += invalidate_cache_pattern(pattern)
        
        return total_cleared
    
    # ================================
    # CACHE DE SISTEMA E ESTATÍSTICAS
    # ================================
    
    def cache_system_stats(self, stats: Dict, ttl: Optional[int] = None) -> bool:
        """Cache estatísticas do sistema"""
        cache_key = CacheKey.generate("system_stats")
        return cache_manager.set(cache_key, stats, l2_ttl=ttl or self.short_ttl)
    
    def get_system_stats(self) -> Optional[Dict]:
        """Obter estatísticas do sistema do cache"""
        cache_key = CacheKey.generate("system_stats")
        return cache_manager.get(cache_key)
    
    def cache_dashboard_data(self, data: Dict, ttl: Optional[int] = None) -> bool:
        """Cache dados do dashboard"""
        cache_key = CacheKey.generate("dashboard_data")
        return cache_manager.set(cache_key, data, l2_ttl=ttl or self.short_ttl)
    
    def get_dashboard_data(self) -> Optional[Dict]:
        """Obter dados do dashboard do cache"""
        cache_key = CacheKey.generate("dashboard_data")
        return cache_manager.get(cache_key)
    
    def cache_library_content(self, content: List[Dict], filters: Dict = None, ttl: Optional[int] = None) -> bool:
        """Cache conteúdo da biblioteca"""
        cache_key = CacheKey.generate("library_content", filters=filters or {})
        return cache_manager.set(cache_key, content, l2_ttl=ttl or self.default_ttl)
    
    def get_library_content(self, filters: Dict = None) -> Optional[List[Dict]]:
        """Obter conteúdo da biblioteca do cache"""
        cache_key = CacheKey.generate("library_content", filters=filters or {})
        return cache_manager.get(cache_key)
    
    # ================================
    # CACHE DE LOGS E AUDITORIA
    # ================================
    
    def cache_recent_logs(self, logs: List[Dict], log_type: str = "all", ttl: Optional[int] = None) -> bool:
        """Cache logs recentes"""
        cache_key = CacheKey.generate("recent_logs", log_type)
        return cache_manager.set(cache_key, logs, l2_ttl=ttl or self.short_ttl)
    
    def get_recent_logs(self, log_type: str = "all") -> Optional[List[Dict]]:
        """Obter logs recentes do cache"""
        cache_key = CacheKey.generate("recent_logs", log_type)
        return cache_manager.get(cache_key)
    
    def cache_user_activity(self, user_id: int, activity: List[Dict], ttl: Optional[int] = None) -> bool:
        """Cache atividade do usuário"""
        cache_key = CacheKey.user_key(user_id, "activity")
        return cache_manager.set(cache_key, activity, l2_ttl=ttl or self.default_ttl)
    
    def get_user_activity(self, user_id: int) -> Optional[List[Dict]]:
        """Obter atividade do usuário do cache"""
        cache_key = CacheKey.user_key(user_id, "activity")
        return cache_manager.get(cache_key)
    
    # ================================
    # MÉTODOS UTILITÁRIOS
    # ================================
    
    def warm_critical_cache(self) -> Dict[str, int]:
        """Pré-aquecer cache com dados críticos"""
        logger.info("Iniciando aquecimento de cache crítico...")
        
        results = {
            'system_stats': 0,
            'servers_status': 0,
            'user_sessions': 0
        }
        
        try:
            # Aqui você pode adicionar lógica para pré-carregar dados críticos
            # Por exemplo, carregar status de servidores ativos
            
            logger.info("Aquecimento de cache crítico concluído")
            
        except Exception as e:
            logger.error(f"Erro no aquecimento de cache: {e}")
        
        return results
    
    def cleanup_expired_cache(self) -> Dict[str, int]:
        """Limpar cache expirado"""
        logger.info("Iniciando limpeza de cache expirado...")
        
        # Padrões de cache temporário para limpar
        temp_patterns = [
            "download_progress:*",    # Progresso de downloads
            "temp:*",                 # Dados temporários
            "session:expired:*",      # Sessões expiradas
            "recent_logs:*",          # Logs recentes (podem ser recarregados)
        ]
        
        results = {}
        total_cleared = 0
        
        for pattern in temp_patterns:
            cleared = invalidate_cache_pattern(pattern)
            results[pattern] = cleared
            total_cleared += cleared
        
        logger.info(f"Limpeza de cache concluída: {total_cleared} chaves removidas")
        return results
    
    def get_cache_health(self) -> Dict[str, Any]:
        """Obter saúde geral do cache"""
        try:
            from app.utils.cache_manager import get_cache_stats
            
            stats = get_cache_stats()
            
            # Calcular métricas de saúde
            hit_rate = stats.get('combined', {}).get('hit_rate', 0)
            total_requests = stats.get('combined', {}).get('total_requests', 0)
            
            health_status = "healthy"
            if hit_rate < 50:
                health_status = "poor"
            elif hit_rate < 75:
                health_status = "fair"
            
            return {
                'status': health_status,
                'hit_rate': hit_rate,
                'total_requests': total_requests,
                'stats': stats,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Erro obtendo saúde do cache: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': time.time()
            }
    
    def bulk_invalidate(self, patterns: List[str]) -> Dict[str, int]:
        """Invalidar múltiplos padrões de cache"""
        results = {}
        total_cleared = 0
        
        for pattern in patterns:
            cleared = invalidate_cache_pattern(pattern)
            results[pattern] = cleared
            total_cleared += cleared
        
        logger.info(f"Invalidação em lote concluída: {total_cleared} chaves removidas")
        return results

# Instância global do serviço de cache
cache_service = CacheService()
