#!/usr/bin/env python3
"""
Sistema otimizado de cache para MediaDown
"""

import json
import time
import hashlib
import pickle
import logging
from typing import Any, Optional, Union, List, Dict, Callable
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import redis
from flask import current_app, request, g

logger = logging.getLogger(__name__)

class CacheStrategy(Enum):
    """Estratégias de cache"""
    LRU = "lru"              # Least Recently Used
    LFU = "lfu"              # Least Frequently Used
    TTL = "ttl"              # Time To Live
    WRITE_THROUGH = "write_through"    # Escreve no cache e DB simultaneamente
    WRITE_BEHIND = "write_behind"      # Escreve no cache primeiro, DB depois
    READ_THROUGH = "read_through"      # Lê do cache, se não existe busca no DB

class CacheLevel(Enum):
    """Níveis de cache"""
    L1_MEMORY = "l1_memory"     # Cache em memória (mais rápido)
    L2_REDIS = "l2_redis"       # Cache Redis (compartilhado)
    L3_DISK = "l3_disk"         # Cache em disco (maior volume)

@dataclass
class CacheStats:
    """Estatísticas do cache"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    total_requests: int = 0
    avg_response_time: float = 0.0
    cache_size: int = 0
    memory_usage: int = 0
    
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100
    
    def to_dict(self) -> Dict:
        return asdict(self)

class CacheKey:
    """Gerador inteligente de chaves de cache"""
    
    @staticmethod
    def generate(prefix: str, *args, **kwargs) -> str:
        """Gerar chave de cache consistente"""
        key_parts = [prefix]
        
        # Adicionar argumentos posicionais
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(hashlib.md5(json.dumps(arg, sort_keys=True).encode()).hexdigest()[:8])
            else:
                key_parts.append(str(arg))
        
        # Adicionar argumentos nomeados
        for k, v in sorted(kwargs.items()):
            if isinstance(v, (dict, list)):
                key_parts.append(f"{k}:{hashlib.md5(json.dumps(v, sort_keys=True).encode()).hexdigest()[:8]}")
            else:
                key_parts.append(f"{k}:{v}")
        
        return ":".join(key_parts)
    
    @staticmethod
    def user_key(user_id: int, action: str) -> str:
        """Chave específica para usuário"""
        return f"user:{user_id}:{action}"
    
    @staticmethod
    def tmdb_key(title: str, content_type: str, year: Optional[int] = None) -> str:
        """Chave para cache TMDB"""
        key = f"tmdb:{content_type}:{hashlib.md5(title.encode()).hexdigest()[:12]}"
        if year:
            key += f":{year}"
        return key
    
    @staticmethod
    def download_key(url: str) -> str:
        """Chave para informações de download"""
        return f"download:{hashlib.md5(url.encode()).hexdigest()[:16]}"
    
    @staticmethod
    def session_key(session_id: str) -> str:
        """Chave para dados de sessão"""
        return f"session:{session_id}"

class MemoryCache:
    """Cache L1 em memória"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.data = {}
        self.access_times = {}
        self.access_counts = {}
        self.max_size = max_size
        self.default_ttl = ttl
        self.stats = CacheStats()
    
    def _is_expired(self, key: str) -> bool:
        """Verificar se entrada expirou"""
        if key not in self.data:
            return True
        
        entry = self.data[key]
        if 'expires_at' in entry and entry['expires_at'] < time.time():
            self._delete(key)
            return True
        
        return False
    
    def _evict_if_needed(self):
        """Remover entradas se necessário (LRU)"""
        if len(self.data) >= self.max_size:
            # Encontrar entrada menos recentemente usada
            oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            self._delete(oldest_key)
    
    def _delete(self, key: str):
        """Deletar entrada do cache"""
        if key in self.data:
            del self.data[key]
            del self.access_times[key]
            if key in self.access_counts:
                del self.access_counts[key]
            self.stats.deletes += 1
    
    def get(self, key: str) -> Optional[Any]:
        """Obter valor do cache"""
        start_time = time.time()
        
        try:
            if self._is_expired(key):
                self.stats.misses += 1
                return None
            
            entry = self.data[key]
            self.access_times[key] = time.time()
            self.access_counts[key] = self.access_counts.get(key, 0) + 1
            
            self.stats.hits += 1
            return entry['value']
            
        finally:
            self.stats.total_requests += 1
            response_time = time.time() - start_time
            self.stats.avg_response_time = (
                (self.stats.avg_response_time * (self.stats.total_requests - 1) + response_time) 
                / self.stats.total_requests
            )
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Definir valor no cache"""
        try:
            self._evict_if_needed()
            
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl if ttl > 0 else None
            
            self.data[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            
            self.access_times[key] = time.time()
            self.access_counts[key] = 1
            
            self.stats.sets += 1
            self.stats.cache_size = len(self.data)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro definindo cache L1: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Deletar chave do cache"""
        if key in self.data:
            self._delete(key)
            self.stats.cache_size = len(self.data)
            return True
        return False
    
    def clear(self):
        """Limpar todo o cache"""
        self.data.clear()
        self.access_times.clear()
        self.access_counts.clear()
        self.stats = CacheStats()
    
    def get_stats(self) -> CacheStats:
        """Obter estatísticas do cache"""
        self.stats.cache_size = len(self.data)
        self.stats.memory_usage = sum(len(str(v)) for v in self.data.values())
        return self.stats

class RedisCache:
    """Cache L2 usando Redis"""
    
    def __init__(self, redis_client=None, key_prefix: str = "mediadown"):
        self.redis_client = redis_client or self._get_redis_client()
        self.key_prefix = key_prefix
        self.stats = CacheStats()
        self.compression_enabled = True
        
    def _get_redis_client(self):
        """Obter cliente Redis"""
        try:
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            return redis.from_url(redis_url, decode_responses=False)
        except Exception as e:
            logger.error(f"Erro conectando Redis: {e}")
            return None
    
    def _make_key(self, key: str) -> str:
        """Criar chave Redis com prefixo"""
        return f"{self.key_prefix}:cache:{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serializar valor para armazenamento"""
        try:
            # Usar pickle para objetos complexos
            data = pickle.dumps(value)
            
            # Comprimir se habilitado e dados grandes
            if self.compression_enabled and len(data) > 1024:
                import gzip
                data = gzip.compress(data)
                return b'gzip:' + data
            
            return data
            
        except Exception as e:
            logger.error(f"Erro serializando valor: {e}")
            return json.dumps(value).encode()
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserializar valor do armazenamento"""
        try:
            # Verificar se está comprimido
            if data.startswith(b'gzip:'):
                import gzip
                data = gzip.decompress(data[5:])
            
            return pickle.loads(data)
            
        except Exception:
            try:
                return json.loads(data.decode())
            except Exception as e:
                logger.error(f"Erro deserializando valor: {e}")
                return None
    
    def get(self, key: str) -> Optional[Any]:
        """Obter valor do cache Redis"""
        if not self.redis_client:
            return None
        
        start_time = time.time()
        
        try:
            redis_key = self._make_key(key)
            data = self.redis_client.get(redis_key)
            
            if data is None:
                self.stats.misses += 1
                return None
            
            value = self._deserialize(data)
            self.stats.hits += 1
            
            return value
            
        except Exception as e:
            logger.error(f"Erro obtendo cache Redis: {e}")
            self.stats.misses += 1
            return None
            
        finally:
            self.stats.total_requests += 1
            response_time = time.time() - start_time
            self.stats.avg_response_time = (
                (self.stats.avg_response_time * (self.stats.total_requests - 1) + response_time) 
                / self.stats.total_requests
            )
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Definir valor no cache Redis"""
        if not self.redis_client:
            return False
        
        try:
            redis_key = self._make_key(key)
            data = self._serialize(value)
            
            if ttl:
                result = self.redis_client.setex(redis_key, ttl, data)
            else:
                result = self.redis_client.set(redis_key, data)
            
            if result:
                self.stats.sets += 1
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro definindo cache Redis: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Deletar chave do cache Redis"""
        if not self.redis_client:
            return False
        
        try:
            redis_key = self._make_key(key)
            result = self.redis_client.delete(redis_key)
            
            if result:
                self.stats.deletes += 1
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro deletando cache Redis: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Limpar chaves que correspondem ao padrão"""
        if not self.redis_client:
            return 0
        
        try:
            redis_pattern = self._make_key(pattern)
            keys = self.redis_client.keys(redis_pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                self.stats.deletes += deleted
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Erro limpando padrão: {e}")
            return 0
    
    def get_stats(self) -> CacheStats:
        """Obter estatísticas do cache Redis"""
        if not self.redis_client:
            return self.stats
        
        try:
            info = self.redis_client.info('memory')
            self.stats.memory_usage = info.get('used_memory', 0)
            
            # Contar chaves do nosso namespace
            pattern = self._make_key("*")
            keys = self.redis_client.keys(pattern)
            self.stats.cache_size = len(keys)
            
        except Exception as e:
            logger.error(f"Erro obtendo estatísticas Redis: {e}")
        
        return self.stats

class MultiLevelCache:
    """Cache multinível (L1 Memory + L2 Redis)"""
    
    def __init__(self, l1_size: int = 1000, l1_ttl: int = 300, l2_ttl: int = 3600):
        self.l1_cache = MemoryCache(max_size=l1_size, ttl=l1_ttl)
        self.l2_cache = RedisCache()
        self.l2_ttl = l2_ttl
        self.stats = CacheStats()
        
    def get(self, key: str) -> Optional[Any]:
        """Obter valor do cache multinível"""
        start_time = time.time()
        
        try:
            # Tentar L1 primeiro (mais rápido)
            value = self.l1_cache.get(key)
            if value is not None:
                self.stats.hits += 1
                return value
            
            # Tentar L2 (Redis)
            value = self.l2_cache.get(key)
            if value is not None:
                # Promover para L1
                self.l1_cache.set(key, value)
                self.stats.hits += 1
                return value
            
            self.stats.misses += 1
            return None
            
        finally:
            self.stats.total_requests += 1
            response_time = time.time() - start_time
            self.stats.avg_response_time = (
                (self.stats.avg_response_time * (self.stats.total_requests - 1) + response_time) 
                / self.stats.total_requests
            )
    
    def set(self, key: str, value: Any, l1_ttl: Optional[int] = None, l2_ttl: Optional[int] = None) -> bool:
        """Definir valor em ambos os níveis"""
        l2_ttl = l2_ttl or self.l2_ttl
        
        # Definir em ambos os caches
        l1_result = self.l1_cache.set(key, value, l1_ttl)
        l2_result = self.l2_cache.set(key, value, l2_ttl)
        
        if l1_result or l2_result:
            self.stats.sets += 1
            return True
        
        return False
    
    def delete(self, key: str) -> bool:
        """Deletar de ambos os níveis"""
        l1_result = self.l1_cache.delete(key)
        l2_result = self.l2_cache.delete(key)
        
        if l1_result or l2_result:
            self.stats.deletes += 1
            return True
        
        return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Limpar padrão em ambos os níveis"""
        # L1 não suporta padrões, limpar tudo
        self.l1_cache.clear()
        
        # L2 suporta padrões
        return self.l2_cache.clear_pattern(pattern)
    
    def get_combined_stats(self) -> Dict[str, Any]:
        """Obter estatísticas combinadas"""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()
        
        return {
            'combined': self.stats.to_dict(),
            'l1_memory': l1_stats.to_dict(),
            'l2_redis': l2_stats.to_dict(),
            'total_hit_rate': self.stats.hit_rate,
            'total_requests': self.stats.total_requests
        }

# Instância global do cache
cache_manager = MultiLevelCache()

def cached(ttl: int = 3600, key_prefix: str = "", use_request_args: bool = True):
    """
    Decorator para cache automático de funções
    
    Args:
        ttl: Time to live em segundos
        key_prefix: Prefixo da chave de cache
        use_request_args: Incluir argumentos da request na chave
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Gerar chave de cache
            cache_key_parts = [key_prefix or func.__name__]
            
            # Adicionar argumentos da função
            if args:
                cache_key_parts.extend([str(arg) for arg in args])
            
            if kwargs:
                cache_key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
            
            # Adicionar argumentos da request se habilitado
            if use_request_args and request:
                if request.args:
                    cache_key_parts.append(f"args:{hashlib.md5(str(dict(request.args)).encode()).hexdigest()[:8]}")
                
                # Incluir usuário logado se disponível
                if hasattr(g, 'current_user') and g.current_user:
                    cache_key_parts.append(f"user:{g.current_user.id}")
            
            cache_key = CacheKey.generate(*cache_key_parts)
            
            # Tentar obter do cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit para: {func.__name__}")
                return cached_result
            
            # Executar função e cachear resultado
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, l2_ttl=ttl)
            
            logger.debug(f"Cache miss para: {func.__name__}, resultado cacheado")
            return result
        
        return wrapper
    return decorator

def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidar cache por padrão"""
    return cache_manager.clear_pattern(pattern)

def get_cache_stats() -> Dict[str, Any]:
    """Obter estatísticas do cache"""
    return cache_manager.get_combined_stats()

def warm_cache():
    """Pré-aquecer cache com dados frequentes"""
    logger.info("Iniciando aquecimento do cache...")
    
    try:
        # Cache de configurações do sistema
        from config import get_config
        config = get_config()
        cache_manager.set("system:config", config, l2_ttl=86400)  # 24 horas
        
        # Cache de estatísticas básicas
        # Aqui você pode adicionar outras operações de aquecimento
        
        logger.info("Aquecimento do cache concluído")
        
    except Exception as e:
        logger.error(f"Erro no aquecimento do cache: {e}")

def cleanup_expired_cache():
    """Limpar cache expirado (tarefa periódica)"""
    try:
        # Limpar padrões antigos
        patterns_to_clean = [
            "temp:*",  # Dados temporários
            "session:expired:*",  # Sessões expiradas
            "download:status:*"  # Status antigos de download
        ]
        
        total_cleaned = 0
        for pattern in patterns_to_clean:
            cleaned = cache_manager.clear_pattern(pattern)
            total_cleaned += cleaned
            logger.debug(f"Limpou {cleaned} chaves do padrão: {pattern}")
        
        logger.info(f"Limpeza do cache concluída: {total_cleaned} chaves removidas")
        return total_cleaned
        
    except Exception as e:
        logger.error(f"Erro na limpeza do cache: {e}")
        return 0
