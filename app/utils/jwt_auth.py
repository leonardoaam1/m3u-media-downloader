import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g
from app.models.users import User
from app.services.logging_service import LoggingService

logger = LoggingService()

class JWTManager:
    """Advanced JWT authentication manager for API access"""
    
    def __init__(self):
        self.algorithm = 'HS256'
        self.access_token_expires = timedelta(hours=1)
        self.refresh_token_expires = timedelta(days=30)
    
    def get_secret_key(self) -> str:
        """Get JWT secret key from config"""
        return current_app.config.get('JWT_SECRET_KEY', current_app.config['SECRET_KEY'])
    
    def generate_tokens(self, user: User) -> dict:
        """Generate access and refresh tokens for user"""
        now = datetime.utcnow()
        
        # Access token payload
        access_payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role.value,
            'permissions': user.get_permissions(),
            'iat': now,
            'exp': now + self.access_token_expires,
            'type': 'access',
            'jti': secrets.token_urlsafe(16)  # JWT ID for revocation
        }
        
        # Refresh token payload
        refresh_payload = {
            'user_id': user.id,
            'username': user.username,
            'iat': now,
            'exp': now + self.refresh_token_expires,
            'type': 'refresh',
            'jti': secrets.token_urlsafe(16)
        }
        
        # Generate tokens
        access_token = jwt.encode(access_payload, self.get_secret_key(), algorithm=self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.get_secret_key(), algorithm=self.algorithm)
        
        # Log token generation
        logger.log_user_activity(
            user.id,
            'jwt_tokens_generated',
            {
                'access_token_jti': access_payload['jti'],
                'refresh_token_jti': refresh_payload['jti'],
                'expires_at': access_payload['exp'].isoformat()
            }
        )
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': int(self.access_token_expires.total_seconds()),
            'access_token_expires': access_payload['exp'].isoformat(),
            'refresh_token_expires': refresh_payload['exp'].isoformat(),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role.value,
                'permissions': user.get_permissions()
            }
        }
    
    def verify_token(self, token: str, token_type: str = 'access') -> dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.get_secret_key(),
                algorithms=[self.algorithm],
                options={
                    'verify_exp': True,
                    'verify_iat': True,
                    'verify_signature': True
                }
            )
            
            # Verify token type
            if payload.get('type') != token_type:
                raise jwt.InvalidTokenError(f'Invalid token type. Expected {token_type}')
            
            # Check if token is blacklisted (would need Redis/database implementation)
            if self.is_token_blacklisted(payload.get('jti')):
                raise jwt.InvalidTokenError('Token has been revoked')
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError('Token has expired')
        except jwt.InvalidSignatureError:
            raise jwt.InvalidTokenError('Invalid token signature')
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(str(e))
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        """Generate new access token using refresh token"""
        try:
            payload = self.verify_token(refresh_token, 'refresh')
            
            # Get user from database
            user = User.query.get(payload['user_id'])
            if not user or not user.is_active:
                raise jwt.InvalidTokenError('User not found or inactive')
            
            # Generate new access token only
            now = datetime.utcnow()
            access_payload = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role.value,
                'permissions': user.get_permissions(),
                'iat': now,
                'exp': now + self.access_token_expires,
                'type': 'access',
                'jti': secrets.token_urlsafe(16)
            }
            
            access_token = jwt.encode(access_payload, self.get_secret_key(), algorithm=self.algorithm)
            
            logger.log_user_activity(
                user.id,
                'jwt_access_token_refreshed',
                {
                    'new_jti': access_payload['jti'],
                    'expires_at': access_payload['exp'].isoformat()
                }
            )
            
            return {
                'access_token': access_token,
                'token_type': 'Bearer',
                'expires_in': int(self.access_token_expires.total_seconds()),
                'expires_at': access_payload['exp'].isoformat()
            }
            
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f'Invalid refresh token: {str(e)}')
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a JWT token (add to blacklist)"""
        try:
            payload = self.verify_token(token, token_type=None)  # Accept any type
            jti = payload.get('jti')
            
            if jti:
                # Add to blacklist (would need Redis/database implementation)
                self.blacklist_token(jti, payload.get('exp'))
                
                logger.log_user_activity(
                    payload.get('user_id'),
                    'jwt_token_revoked',
                    {'jti': jti, 'type': payload.get('type')}
                )
                
                return True
            
        except jwt.InvalidTokenError:
            pass  # Token already invalid
        
        return False
    
    def blacklist_token(self, jti: str, exp: datetime) -> bool:
        """Add token to blacklist (implement with Redis)"""
        # This would be implemented with Redis for production
        # For now, just log it
        logger.log_system('info', f'Token blacklisted: {jti}')
        return True
    
    def is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        # This would be implemented with Redis for production
        # For now, always return False
        return False
    
    def decode_token_without_verification(self, token: str) -> dict:
        """Decode token without verification (for debugging)"""
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return {}

# Global JWT manager instance
jwt_manager = JWTManager()

def require_jwt_auth(required_permissions=None, allow_api_key=True):
    """
    Decorator to require JWT authentication
    
    Args:
        required_permissions: List of required permissions
        allow_api_key: Whether to allow API key as fallback
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check for API key first if allowed
            if allow_api_key:
                api_key = request.headers.get('X-API-Key')
                if api_key:
                    expected_key = current_app.config.get('API_KEY', 'mediadown-api-key-2025')
                    if api_key == expected_key:
                        # API key is valid, proceed without JWT
                        g.current_user = None  # No specific user for API key
                        g.auth_method = 'api_key'
                        return f(*args, **kwargs)
            
            # Check for JWT token
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    'error': 'Missing or invalid authorization header',
                    'message': 'Provide either "Authorization: Bearer <token>" or "X-API-Key: <key>"'
                }), 401
            
            token = auth_header.split(' ')[1]
            
            try:
                payload = jwt_manager.verify_token(token, 'access')
                
                # Get user from database
                user = User.query.get(payload['user_id'])
                if not user or not user.is_active:
                    return jsonify({
                        'error': 'User not found or inactive',
                        'code': 'USER_INACTIVE'
                    }), 401
                
                # Check permissions if required
                if required_permissions:
                    user_permissions = user.get_permissions()
                    missing_permissions = [
                        perm for perm in required_permissions 
                        if perm not in user_permissions
                    ]
                    
                    if missing_permissions:
                        return jsonify({
                            'error': 'Insufficient permissions',
                            'missing_permissions': missing_permissions,
                            'code': 'INSUFFICIENT_PERMISSIONS'
                        }), 403
                
                # Set user in global context
                g.current_user = user
                g.auth_method = 'jwt'
                g.token_payload = payload
                
                # Log API access
                logger.log_user_activity(
                    user.id,
                    'api_access',
                    {
                        'endpoint': request.endpoint,
                        'method': request.method,
                        'auth_method': 'jwt'
                    }
                )
                
                return f(*args, **kwargs)
                
            except jwt.InvalidTokenError as e:
                return jsonify({
                    'error': 'Invalid or expired token',
                    'message': str(e),
                    'code': 'INVALID_TOKEN'
                }), 401
            
        return decorated_function
    return decorator

def get_current_user():
    """Get current authenticated user from context"""
    return getattr(g, 'current_user', None)

def get_auth_method():
    """Get authentication method used"""
    return getattr(g, 'auth_method', None)

def generate_api_key(user: User, name: str = "API Key", expires_in_days: int = 365) -> dict:
    """Generate a named API key for a user"""
    # Create a unique API key
    key_data = f"{user.id}:{user.username}:{datetime.utcnow().isoformat()}:{secrets.token_urlsafe(32)}"
    api_key = hashlib.sha256(key_data.encode()).hexdigest()
    
    # In production, this would be stored in database with expiration
    key_info = {
        'key': api_key,
        'name': name,
        'user_id': user.id,
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat(),
        'is_active': True
    }
    
    logger.log_user_activity(
        user.id,
        'api_key_generated',
        {
            'key_name': name,
            'expires_at': key_info['expires_at']
        }
    )
    
    return key_info

def revoke_api_key(api_key: str) -> bool:
    """Revoke an API key"""
    # In production, this would mark the key as inactive in database
    logger.log_system('info', f'API key revoked: {api_key[:8]}...')
    return True
