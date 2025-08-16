#!/usr/bin/env python3
"""
Sistema avançado de Rate Limiting para MediaDown
"""

import time
import json
import logging
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, asdict
from enum import Enum
import redis
from flask import request, jsonify, current_app, g, abort

logger = logging.getLogger(__name__)

class LimitStrategy(Enum):
    """Estratégias de rate limiting"""
    FIXED_WINDOW = "fixed_window"           # Janela fixa
    SLIDING_WINDOW = "sliding_window"       # Janela deslizante
    TOKEN_BUCKET = "token_bucket"           # Balde de tokens
    LEAKY_BUCKET = "leaky_bucket"          # Balde vazado
    ADAPTIVE = "adaptive"                   # Adaptativo baseado em carga

class ClientType(Enum):
    """Tipos de cliente"""
    ANONYMOUS = "anonymous"         # IP anônimo
    AUTHENTICATED = "authenticated" # Usuário logado
    API_KEY = "api_key"            # Chave API
    PREMIUM = "premium"            # Usuário premium
    ADMIN = "admin"                # Administrador

class LimitTier(Enum):
    """Níveis de limite"""
    VERY_STRICT = "very_strict"    # Muito restritivo
    STRICT = "strict"              # Restritivo
    NORMAL = "normal"              # Normal
    RELAXED = "relaxed"            # Relaxado
    UNLIMITED = "unlimited"        # Sem limite

@dataclass
class RateLimit:
    """Configuração de rate limit"""
    requests_per_second: int = 10
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_allowance: int = 20      # Rajadas permitidas
    strategy: LimitStrategy = LimitStrategy.SLIDING_WINDOW
    tier: LimitTier = LimitTier.NORMAL
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class LimitResult:
    """Resultado da verificação de limite"""
    allowed: bool
    limit: int
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    strategy_used: str = ""
    client_tier: str = ""
    blocked_reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)

class AdvancedRateLimiter:
    """Sistema avançado de rate limiting"""
    
    def __init__(self, redis_client=None, enable_adaptive=True):
        self.redis_client = redis_client or self._get_redis_client()
        self.enable_adaptive = enable_adaptive
        self.key_prefix = "rate_limit"
        
        # Configurações por tier
        self.tier_configs = {
            LimitTier.VERY_STRICT: RateLimit(
                requests_per_second=2,
                requests_per_minute=10,
                requests_per_hour=100,
                requests_per_day=500,
                burst_allowance=5,
                strategy=LimitStrategy.SLIDING_WINDOW,
                tier=LimitTier.VERY_STRICT
            ),
            LimitTier.STRICT: RateLimit(
                requests_per_second=5,
                requests_per_minute=30,
                requests_per_hour=500,
                requests_per_day=2000,
                burst_allowance=10,
                strategy=LimitStrategy.SLIDING_WINDOW,
                tier=LimitTier.STRICT
            ),
            LimitTier.NORMAL: RateLimit(
                requests_per_second=10,
                requests_per_minute=60,
                requests_per_hour=1000,
                requests_per_day=10000,
                burst_allowance=20,
                strategy=LimitStrategy.SLIDING_WINDOW,
                tier=LimitTier.NORMAL
            ),
            LimitTier.RELAXED: RateLimit(
                requests_per_second=20,
                requests_per_minute=120,
                requests_per_hour=2000,
                requests_per_day=50000,
                burst_allowance=50,
                strategy=LimitStrategy.TOKEN_BUCKET,
                tier=LimitTier.RELAXED
            )
        }
        
        # Configurações por tipo de cliente
        self.client_configs = {
            ClientType.ANONYMOUS: LimitTier.STRICT,
            ClientType.AUTHENTICATED: LimitTier.NORMAL,
            ClientType.API_KEY: LimitTier.RELAXED,
            ClientType.PREMIUM: LimitTier.RELAXED,
            ClientType.ADMIN: LimitTier.UNLIMITED
        }
        
        # Lista negra e branca
        self.blacklist = set()
        self.whitelist = set()
        
        # Métricas de sistema
        self.system_metrics = {
            'total_requests': 0,
            'blocked_requests': 0,
            'avg_response_time': 0.0,
            'peak_requests_per_second': 0
        }
    
    def _get_redis_client(self):
        """Obter cliente Redis"""
        try:
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/1')
            return redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.error(f"Erro conectando Redis para rate limiting: {e}")
            return None
    
    def _get_client_info(self) -> Tuple[str, ClientType]:
        """Obter informações do cliente"""
        # Verificar chave API
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization')
        if api_key:
            # Validar API key e determinar tipo
            client_id = f"api_key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
            
            # Verificar se é premium (você pode implementar lógica de DB aqui)
            if self._is_premium_api_key(api_key):
                return client_id, ClientType.PREMIUM
            else:
                return client_id, ClientType.API_KEY
        
        # Verificar usuário autenticado
        if hasattr(g, 'current_user') and g.current_user and g.current_user.is_authenticated:
            user_id = g.current_user.id
            client_id = f"user:{user_id}"
            
            # Verificar se é admin
            if g.current_user.is_admin():
                return client_id, ClientType.ADMIN
            # Verificar se é premium
            elif hasattr(g.current_user, 'is_premium') and g.current_user.is_premium():
                return client_id, ClientType.PREMIUM
            else:
                return client_id, ClientType.AUTHENTICATED
        
        # Fallback para IP
        ip = self._get_client_ip()
        return f"ip:{ip}", ClientType.ANONYMOUS
    
    def _get_client_ip(self) -> str:
        """Obter IP do cliente"""
        # Verificar headers de proxy
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr or '127.0.0.1'
    
    def _is_premium_api_key(self, api_key: str) -> bool:
        """Verificar se é API key premium"""
        # Implementar lógica de validação de API key premium
        # Por enquanto, retorna False
        return False
    
    def _make_redis_key(self, client_id: str, window: str, endpoint: str = None) -> str:
        """Criar chave Redis"""
        endpoint = endpoint or request.endpoint or 'unknown'
        return f"{self.key_prefix}:{client_id}:{endpoint}:{window}"
    
    def _sliding_window_check(self, client_id: str, limit: int, window_seconds: int, endpoint: str = None) -> LimitResult:
        """Implementar sliding window rate limiting"""
        if not self.redis_client:
            return LimitResult(allowed=True, limit=limit, remaining=limit, reset_time=int(time.time() + window_seconds))
        
        now = time.time()
        window_start = now - window_seconds
        key = self._make_redis_key(client_id, f"sliding_{window_seconds}", endpoint)
        
        try:
            # Pipeline para operações atômicas
            pipe = self.redis_client.pipeline()
            
            # Remover entradas antigas
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Contar requests atuais
            pipe.zcard(key)
            
            # Adicionar request atual (se permitido)
            current_count_result = pipe.execute()
            current_count = current_count_result[1]
            
            if current_count >= limit:
                # Encontrar o timestamp mais antigo para calcular reset
                oldest_scores = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_scores:
                    oldest_time = oldest_scores[0][1]
                    reset_time = int(oldest_time + window_seconds)
                else:
                    reset_time = int(now + window_seconds)
                
                return LimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_time=reset_time,
                    retry_after=max(1, reset_time - int(now)),
                    strategy_used="sliding_window",
                    blocked_reason="Rate limit exceeded"
                )
            
            # Permitir request
            pipe = self.redis_client.pipeline()
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window_seconds + 1)  # Expire um pouco depois da janela
            pipe.execute()
            
            remaining = max(0, limit - current_count - 1)
            reset_time = int(now + window_seconds)
            
            return LimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_time=reset_time,
                strategy_used="sliding_window"
            )
            
        except Exception as e:
            logger.error(f"Erro no sliding window check: {e}")
            # Em caso de erro, permitir (fail open)
            return LimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_time=int(time.time() + window_seconds),
                strategy_used="sliding_window_fallback"
            )
    
    def _token_bucket_check(self, client_id: str, rate: float, capacity: int, endpoint: str = None) -> LimitResult:
        """Implementar token bucket rate limiting"""
        if not self.redis_client:
            return LimitResult(allowed=True, limit=capacity, remaining=capacity, reset_time=int(time.time() + 60))
        
        now = time.time()
        key = self._make_redis_key(client_id, "token_bucket", endpoint)
        
        try:
            # Obter estado atual do bucket
            bucket_data = self.redis_client.get(key)
            
            if bucket_data:
                bucket = json.loads(bucket_data)
                last_refill = bucket['last_refill']
                tokens = bucket['tokens']
            else:
                # Inicializar bucket
                last_refill = now
                tokens = capacity
            
            # Calcular tokens a adicionar
            time_passed = now - last_refill
            tokens_to_add = time_passed * rate
            tokens = min(capacity, tokens + tokens_to_add)
            
            if tokens >= 1:
                # Consumir um token
                tokens -= 1
                
                # Salvar estado
                bucket_data = {
                    'tokens': tokens,
                    'last_refill': now,
                    'capacity': capacity,
                    'rate': rate
                }
                
                self.redis_client.setex(key, 86400, json.dumps(bucket_data))  # Expire em 24h
                
                return LimitResult(
                    allowed=True,
                    limit=capacity,
                    remaining=int(tokens),
                    reset_time=int(now + (capacity - tokens) / rate),
                    strategy_used="token_bucket"
                )
            else:
                # Sem tokens disponíveis
                retry_after = int((1 - tokens) / rate) + 1
                
                return LimitResult(
                    allowed=False,
                    limit=capacity,
                    remaining=0,
                    reset_time=int(now + retry_after),
                    retry_after=retry_after,
                    strategy_used="token_bucket",
                    blocked_reason="Token bucket empty"
                )
                
        except Exception as e:
            logger.error(f"Erro no token bucket check: {e}")
            return LimitResult(
                allowed=True,
                limit=capacity,
                remaining=capacity,
                reset_time=int(time.time() + 60),
                strategy_used="token_bucket_fallback"
            )
    
    def _adaptive_check(self, client_id: str, base_limit: RateLimit, endpoint: str = None) -> LimitResult:
        """Rate limiting adaptativo baseado na carga do sistema"""
        if not self.enable_adaptive:
            return self._sliding_window_check(client_id, base_limit.requests_per_minute, 60, endpoint)
        
        try:
            # Obter métricas do sistema
            system_load = self._get_system_load()
            
            # Ajustar limites baseado na carga
            if system_load > 0.9:  # Sistema sobrecarregado
                adjusted_limit = int(base_limit.requests_per_minute * 0.5)
            elif system_load > 0.7:  # Carga alta
                adjusted_limit = int(base_limit.requests_per_minute * 0.7)
            elif system_load < 0.3:  # Carga baixa
                adjusted_limit = int(base_limit.requests_per_minute * 1.2)
            else:  # Carga normal
                adjusted_limit = base_limit.requests_per_minute
            
            result = self._sliding_window_check(client_id, adjusted_limit, 60, endpoint)
            result.strategy_used = f"adaptive_{result.strategy_used}"
            
            return result
            
        except Exception as e:
            logger.error(f"Erro no adaptive check: {e}")
            return self._sliding_window_check(client_id, base_limit.requests_per_minute, 60, endpoint)
    
    def _get_system_load(self) -> float:
        """Obter carga atual do sistema"""
        try:
            import psutil
            
            # Combinar CPU e memória para carga geral
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            # Peso maior para CPU
            system_load = (cpu_percent * 0.7 + memory_percent * 0.3) / 100
            
            return min(1.0, system_load)
            
        except Exception:
            return 0.5  # Retornar carga média em caso de erro
    
    def check_rate_limit(self, endpoint: str = None, custom_limit: RateLimit = None) -> LimitResult:
        """Verificar rate limit principal"""
        client_id, client_type = self._get_client_info()
        
        # Verificar listas negra/branca
        if client_id in self.blacklist:
            return LimitResult(
                allowed=False,
                limit=0,
                remaining=0,
                reset_time=int(time.time() + 86400),  # 24h
                strategy_used="blacklist",
                blocked_reason="Client blacklisted"
            )
        
        if client_id in self.whitelist or client_type == ClientType.ADMIN:
            return LimitResult(
                allowed=True,
                limit=999999,
                remaining=999999,
                reset_time=int(time.time() + 86400),
                strategy_used="whitelist"
            )
        
        # Obter configuração de limite
        if custom_limit:
            limit_config = custom_limit
        else:
            tier = self.client_configs.get(client_type, LimitTier.NORMAL)
            limit_config = self.tier_configs.get(tier, self.tier_configs[LimitTier.NORMAL])
        
        # Aplicar estratégia
        if limit_config.strategy == LimitStrategy.SLIDING_WINDOW:
            result = self._sliding_window_check(client_id, limit_config.requests_per_minute, 60, endpoint)
        elif limit_config.strategy == LimitStrategy.TOKEN_BUCKET:
            rate = limit_config.requests_per_minute / 60.0  # tokens per second
            result = self._token_bucket_check(client_id, rate, limit_config.burst_allowance, endpoint)
        elif limit_config.strategy == LimitStrategy.ADAPTIVE:
            result = self._adaptive_check(client_id, limit_config, endpoint)
        else:
            # Default para sliding window
            result = self._sliding_window_check(client_id, limit_config.requests_per_minute, 60, endpoint)
        
        result.client_tier = client_type.value
        
        # Atualizar métricas
        self._update_metrics(result.allowed)
        
        # Log para auditoria
        if not result.allowed:
            logger.warning(f"Rate limit exceeded: {client_id} ({client_type.value}) - {endpoint}")
        
        return result
    
    def _update_metrics(self, allowed: bool):
        """Atualizar métricas do sistema"""
        self.system_metrics['total_requests'] += 1
        if not allowed:
            self.system_metrics['blocked_requests'] += 1
    
    def add_to_blacklist(self, client_identifier: str, duration: int = 3600):
        """Adicionar cliente à lista negra"""
        self.blacklist.add(client_identifier)
        
        if self.redis_client:
            key = f"{self.key_prefix}:blacklist:{client_identifier}"
            self.redis_client.setex(key, duration, "1")
        
        logger.warning(f"Client added to blacklist: {client_identifier} for {duration}s")
    
    def remove_from_blacklist(self, client_identifier: str):
        """Remover cliente da lista negra"""
        self.blacklist.discard(client_identifier)
        
        if self.redis_client:
            key = f"{self.key_prefix}:blacklist:{client_identifier}"
            self.redis_client.delete(key)
        
        logger.info(f"Client removed from blacklist: {client_identifier}")
    
    def add_to_whitelist(self, client_identifier: str):
        """Adicionar cliente à lista branca"""
        self.whitelist.add(client_identifier)
        
        if self.redis_client:
            key = f"{self.key_prefix}:whitelist:{client_identifier}"
            self.redis_client.set(key, "1")
        
        logger.info(f"Client added to whitelist: {client_identifier}")
    
    def get_client_stats(self, client_identifier: str) -> Dict:
        """Obter estatísticas do cliente"""
        if not self.redis_client:
            return {}
        
        stats = {}
        
        # Buscar todas as chaves do cliente
        pattern = f"{self.key_prefix}:{client_identifier}:*"
        keys = self.redis_client.keys(pattern)
        
        for key in keys:
            try:
                if "sliding" in key:
                    count = self.redis_client.zcard(key)
                    stats[key.split(':')[-1]] = count
                elif "token_bucket" in key:
                    data = self.redis_client.get(key)
                    if data:
                        bucket = json.loads(data)
                        stats['token_bucket'] = bucket
            except:
                continue
        
        return stats
    
    def get_global_stats(self) -> Dict:
        """Obter estatísticas globais"""
        return {
            'system_metrics': self.system_metrics,
            'blacklist_size': len(self.blacklist),
            'whitelist_size': len(self.whitelist),
            'tier_configs': {tier.value: config.to_dict() for tier, config in self.tier_configs.items()},
            'client_configs': {client.value: tier.value for client, tier in self.client_configs.items()}
        }
    
    def reset_client_limits(self, client_identifier: str):
        """Resetar limites de um cliente"""
        if not self.redis_client:
            return
        
        pattern = f"{self.key_prefix}:{client_identifier}:*"
        keys = self.redis_client.keys(pattern)
        
        if keys:
            self.redis_client.delete(*keys)
            logger.info(f"Reset rate limits for client: {client_identifier}")

# Instância global
rate_limiter = AdvancedRateLimiter()

def rate_limit(strategy: LimitStrategy = LimitStrategy.SLIDING_WINDOW, 
               tier: LimitTier = LimitTier.NORMAL,
               requests_per_minute: int = None,
               custom_endpoint: str = None):
    """
    Decorator para rate limiting
    
    Args:
        strategy: Estratégia de limiting
        tier: Tier de limite a usar
        requests_per_minute: Limite customizado
        custom_endpoint: Nome customizado do endpoint
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            endpoint = custom_endpoint or request.endpoint or func.__name__
            
            # Criar limite customizado se especificado
            custom_limit = None
            if requests_per_minute:
                custom_limit = RateLimit(
                    requests_per_minute=requests_per_minute,
                    strategy=strategy,
                    tier=tier
                )
            elif tier != LimitTier.NORMAL:
                custom_limit = rate_limiter.tier_configs.get(tier)
            
            # Verificar limite
            result = rate_limiter.check_rate_limit(endpoint, custom_limit)
            
            if not result.allowed:
                # Montar resposta de erro
                response_data = {
                    'error': 'Rate limit exceeded',
                    'message': result.blocked_reason or 'Too many requests',
                    'limit': result.limit,
                    'remaining': result.remaining,
                    'reset': result.reset_time,
                    'retry_after': result.retry_after
                }
                
                response = jsonify(response_data)
                response.status_code = 429
                
                # Headers padrão de rate limiting
                response.headers['X-RateLimit-Limit'] = str(result.limit)
                response.headers['X-RateLimit-Remaining'] = str(result.remaining)
                response.headers['X-RateLimit-Reset'] = str(result.reset_time)
                
                if result.retry_after:
                    response.headers['Retry-After'] = str(result.retry_after)
                
                return response
            
            # Adicionar headers informativos à resposta
            response = func(*args, **kwargs)
            
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(result.limit)
                response.headers['X-RateLimit-Remaining'] = str(result.remaining)
                response.headers['X-RateLimit-Reset'] = str(result.reset_time)
                response.headers['X-RateLimit-Strategy'] = result.strategy_used
            
            return response
        
        return wrapper
    return decorator

# Decorators de conveniência
def strict_rate_limit(requests_per_minute: int = 10):
    """Rate limiting estrito"""
    return rate_limit(
        strategy=LimitStrategy.SLIDING_WINDOW,
        tier=LimitTier.STRICT,
        requests_per_minute=requests_per_minute
    )

def normal_rate_limit(requests_per_minute: int = 60):
    """Rate limiting normal"""
    return rate_limit(
        strategy=LimitStrategy.SLIDING_WINDOW,
        tier=LimitTier.NORMAL,
        requests_per_minute=requests_per_minute
    )

def relaxed_rate_limit(requests_per_minute: int = 120):
    """Rate limiting relaxado"""
    return rate_limit(
        strategy=LimitStrategy.TOKEN_BUCKET,
        tier=LimitTier.RELAXED,
        requests_per_minute=requests_per_minute
    )

def adaptive_rate_limit():
    """Rate limiting adaptativo"""
    return rate_limit(strategy=LimitStrategy.ADAPTIVE)
