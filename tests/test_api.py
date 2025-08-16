import unittest
import json
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from app import create_app, db
from app.models.users import User, UserRole
from app.models.downloads import Download, DownloadStatus, DownloadPriority
from app.models.servers import Server, ServerStatus, ServerProtocol
from app.utils.jwt_auth import jwt_manager


class APITestCase(unittest.TestCase):
    """Test cases for MediaDown API endpoints"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        
        # Create test database
        db.create_all()
        
        # Create test users
        self.admin_user = User(
            username='admin_test',
            email='admin@test.com',
            role=UserRole.ADMIN,
            is_active=True
        )
        self.admin_user.set_password('test_password')
        
        self.operator_user = User(
            username='operator_test',
            email='operator@test.com',
            role=UserRole.OPERATOR,
            is_active=True
        )
        self.operator_user.set_password('test_password')
        
        self.viewer_user = User(
            username='viewer_test',
            email='viewer@test.com',
            role=UserRole.VIEWER,
            is_active=True
        )
        self.viewer_user.set_password('test_password')
        
        db.session.add(self.admin_user)
        db.session.add(self.operator_user)
        db.session.add(self.viewer_user)
        db.session.commit()
        
        # Create test server
        self.test_server = Server(
            name='Test Server',
            description='Server for testing',
            host='192.168.1.100',
            port=22,
            protocol=ServerProtocol.SFTP,
            username='test_user',
            base_path='/mnt/test/',
            status=ServerStatus.ONLINE,
            content_types=['movie', 'series']
        )
        self.test_server.set_password('test_password')
        db.session.add(self.test_server)
        db.session.commit()
        
        # API key for testing
        self.api_key = 'test-api-key-2025'
        self.app.config['API_KEY'] = self.api_key
        
        # JWT tokens for testing
        self.admin_tokens = jwt_manager.generate_tokens(self.admin_user)
        self.operator_tokens = jwt_manager.generate_tokens(self.operator_user)
        self.viewer_tokens = jwt_manager.generate_tokens(self.viewer_user)
    
    def tearDown(self):
        """Clean up after each test method"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def get_headers_with_api_key(self):
        """Get headers with API key"""
        return {'X-API-Key': self.api_key, 'Content-Type': 'application/json'}
    
    def get_headers_with_jwt(self, token):
        """Get headers with JWT token"""
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    
    def test_system_status_with_api_key(self):
        """Test system status endpoint with API key"""
        response = self.client.get('/api/v1/status', headers=self.get_headers_with_api_key())
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('status', data)
        self.assertIn('timestamp', data)
        self.assertIn('version', data)
        self.assertIn('stats', data)
        self.assertEqual(data['status'], 'healthy')
    
    def test_system_status_with_jwt(self):
        """Test system status endpoint with JWT"""
        headers = self.get_headers_with_jwt(self.admin_tokens['access_token'])
        response = self.client.get('/api/v1/status', headers=headers)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
    
    def test_system_status_without_auth(self):
        """Test system status endpoint without authentication"""
        response = self.client.get('/api/v1/status')
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_invalid_api_key(self):
        """Test endpoint with invalid API key"""
        headers = {'X-API-Key': 'invalid-key', 'Content-Type': 'application/json'}
        response = self.client.get('/api/v1/status', headers=headers)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_expired_jwt_token(self):
        """Test endpoint with expired JWT token"""
        # Create an expired token
        import jwt
        expired_payload = {
            'user_id': self.admin_user.id,
            'exp': datetime.utcnow() - timedelta(hours=1),
            'type': 'access'
        }
        expired_token = jwt.encode(expired_payload, self.app.config['SECRET_KEY'], algorithm='HS256')
        
        headers = self.get_headers_with_jwt(expired_token)
        response = self.client.get('/api/v1/status', headers=headers)
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_list_downloads_empty(self):
        """Test listing downloads when none exist"""
        response = self.client.get('/api/v1/downloads', headers=self.get_headers_with_api_key())
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('downloads', data)
        self.assertIn('pagination', data)
        self.assertEqual(len(data['downloads']), 0)
    
    def test_create_download_valid(self):
        """Test creating a valid download"""
        download_data = {
            'title': 'Test Movie (2024)',
            'url': 'https://example.com/test.m3u8',
            'content_type': 'movie',
            'quality': '1080p',
            'server_id': self.test_server.id,
            'year': 2024
        }
        
        response = self.client.post(
            '/api/v1/downloads',
            headers=self.get_headers_with_api_key(),
            data=json.dumps(download_data)
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        
        self.assertIn('id', data)
        self.assertIn('message', data)
        self.assertIn('status', data)
        
        # Verify download was created in database
        download = Download.query.get(data['id'])
        self.assertIsNotNone(download)
        self.assertEqual(download.title, download_data['title'])
        self.assertEqual(download.quality, download_data['quality'])
    
    def test_create_download_invalid_data(self):
        """Test creating download with invalid data"""
        invalid_data = {
            'title': 'Test Movie',
            # Missing required fields
        }
        
        response = self.client.post(
            '/api/v1/downloads',
            headers=self.get_headers_with_api_key(),
            data=json.dumps(invalid_data)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_create_download_invalid_quality(self):
        """Test creating download with invalid quality"""
        download_data = {
            'title': 'Test Movie (2024)',
            'url': 'https://example.com/test.m3u8',
            'content_type': 'movie',
            'quality': '4K',  # Invalid quality
        }
        
        response = self.client.post(
            '/api/v1/downloads',
            headers=self.get_headers_with_api_key(),
            data=json.dumps(download_data)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('quality', data['error'])
    
    def test_get_download_details(self):
        """Test getting details of a specific download"""
        # Create a test download
        download = Download(
            title='Test Download',
            content_type='movie',
            quality='720p',
            url='https://example.com/test.m3u8',
            server_id=self.test_server.id,
            user_id=self.admin_user.id,
            status=DownloadStatus.DOWNLOADING,
            progress_percentage=45.5
        )
        db.session.add(download)
        db.session.commit()
        
        response = self.client.get(
            f'/api/v1/downloads/{download.id}',
            headers=self.get_headers_with_api_key()
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertEqual(data['id'], download.id)
        self.assertEqual(data['title'], download.title)
        self.assertEqual(data['status'], download.status.value)
        self.assertEqual(data['progress_percentage'], download.progress_percentage)
    
    def test_get_nonexistent_download(self):
        """Test getting details of non-existent download"""
        response = self.client.get(
            '/api/v1/downloads/99999',
            headers=self.get_headers_with_api_key()
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_control_download_pause(self):
        """Test pausing a download"""
        # Create a test download
        download = Download(
            title='Test Download',
            content_type='movie',
            quality='720p',
            url='https://example.com/test.m3u8',
            server_id=self.test_server.id,
            user_id=self.admin_user.id,
            status=DownloadStatus.DOWNLOADING
        )
        db.session.add(download)
        db.session.commit()
        
        control_data = {'action': 'pause'}
        
        response = self.client.post(
            f'/api/v1/downloads/{download.id}/control',
            headers=self.get_headers_with_api_key(),
            data=json.dumps(control_data)
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('message', data)
        self.assertIn('status', data)
        
        # Verify status changed in database
        db.session.refresh(download)
        self.assertEqual(download.status, DownloadStatus.PAUSED)
    
    def test_control_download_invalid_action(self):
        """Test download control with invalid action"""
        download = Download(
            title='Test Download',
            content_type='movie',
            quality='720p',
            url='https://example.com/test.m3u8',
            server_id=self.test_server.id,
            user_id=self.admin_user.id,
            status=DownloadStatus.DOWNLOADING
        )
        db.session.add(download)
        db.session.commit()
        
        control_data = {'action': 'invalid_action'}
        
        response = self.client.post(
            f'/api/v1/downloads/{download.id}/control',
            headers=self.get_headers_with_api_key(),
            data=json.dumps(control_data)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_list_servers(self):
        """Test listing servers"""
        response = self.client.get('/api/v1/servers', headers=self.get_headers_with_api_key())
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('servers', data)
        self.assertEqual(len(data['servers']), 1)
        
        server_data = data['servers'][0]
        self.assertEqual(server_data['name'], self.test_server.name)
        self.assertEqual(server_data['host'], self.test_server.host)
        self.assertEqual(server_data['protocol'], self.test_server.protocol.value)
    
    @patch('app.services.file_transfer_service.FileTransferService.test_connection')
    def test_test_server_connection(self, mock_test_connection):
        """Test server connection testing"""
        mock_test_connection.return_value = True
        
        response = self.client.get(
            f'/api/v1/servers/{self.test_server.id}/test',
            headers=self.get_headers_with_api_key()
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('server_id', data)
        self.assertIn('connected', data)
        self.assertIn('status', data)
        self.assertTrue(data['connected'])
        
        mock_test_connection.assert_called_once()
    
    def test_m3u_parse_valid(self):
        """Test M3U parsing with valid content"""
        m3u_content = """#EXTM3U
#EXTINF:-1 tvg-name="Test Movie" group-title="Movies",Test Movie (2024) - 1080p
https://example.com/movie.m3u8
#EXTINF:-1 tvg-name="Test Series" group-title="Series",Test Series S01E01 - 720p
https://example.com/series.m3u8"""
        
        parse_data = {'content': m3u_content}
        
        with patch('app.services.m3u_parser.M3UParser.parse_m3u_file') as mock_parse:
            mock_parse.return_value = [
                {
                    'title': 'Test Movie (2024)',
                    'content_type': 'movie',
                    'quality': '1080p',
                    'url': 'https://example.com/movie.m3u8',
                    'year': 2024
                },
                {
                    'title': 'Test Series S01E01',
                    'content_type': 'series',
                    'quality': '720p',
                    'url': 'https://example.com/series.m3u8',
                    'season': 1,
                    'episode': 1
                }
            ]
            
            response = self.client.post(
                '/api/v1/m3u/parse',
                headers=self.get_headers_with_api_key(),
                data=json.dumps(parse_data)
            )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('total_items', data)
        self.assertIn('filtered_items', data)
        self.assertIn('items', data)
        self.assertEqual(data['total_items'], 2)
        self.assertEqual(data['filtered_items'], 2)
    
    def test_m3u_parse_missing_content(self):
        """Test M3U parsing without content"""
        parse_data = {}
        
        response = self.client.post(
            '/api/v1/m3u/parse',
            headers=self.get_headers_with_api_key(),
            data=json.dumps(parse_data)
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_search_content(self):
        """Test content search"""
        # Create test downloads
        downloads = [
            Download(
                title='Action Movie 2024',
                content_type='movie',
                quality='1080p',
                url='https://example.com/action.m3u8',
                server_id=self.test_server.id,
                user_id=self.admin_user.id,
                status=DownloadStatus.COMPLETED,
                year=2024
            ),
            Download(
                title='Comedy Series S01E01',
                content_type='series',
                quality='720p',
                url='https://example.com/comedy.m3u8',
                server_id=self.test_server.id,
                user_id=self.admin_user.id,
                status=DownloadStatus.COMPLETED,
                season=1,
                episode=1
            )
        ]
        
        for download in downloads:
            db.session.add(download)
        db.session.commit()
        
        # Test search by title
        response = self.client.get(
            '/api/v1/search?q=Action',
            headers=self.get_headers_with_api_key()
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('query', data)
        self.assertIn('results', data)
        self.assertEqual(data['query'], 'Action')
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['title'], 'Action Movie 2024')
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # This test would need Redis to work properly
        # For now, just test that the endpoint responds correctly
        
        response = self.client.get('/api/v1/status', headers=self.get_headers_with_api_key())
        self.assertEqual(response.status_code, 200)
        
        # Check that rate limit headers are present
        self.assertIn('X-RateLimit-Limit', response.headers)
        self.assertIn('X-RateLimit-Remaining', response.headers)
    
    def test_jwt_token_refresh(self):
        """Test JWT token refresh"""
        refresh_token = self.admin_tokens['refresh_token']
        
        # Test refresh endpoint (would need to implement)
        # For now, test token generation directly
        new_tokens = jwt_manager.refresh_access_token(refresh_token)
        
        self.assertIn('access_token', new_tokens)
        self.assertIn('expires_in', new_tokens)
        self.assertNotEqual(new_tokens['access_token'], self.admin_tokens['access_token'])


class WebhookTestCase(unittest.TestCase):
    """Test cases for webhook endpoints"""
    
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        
        db.create_all()
        
        # Create test download
        self.test_download = Download(
            title='Webhook Test Download',
            content_type='movie',
            quality='1080p',
            url='https://example.com/webhook_test.m3u8',
            status=DownloadStatus.DOWNLOADING
        )
        db.session.add(self.test_download)
        db.session.commit()
        
        self.webhook_secret = 'test-webhook-secret'
        self.app.config['WEBHOOK_SECRET'] = self.webhook_secret
    
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def generate_webhook_signature(self, payload):
        """Generate HMAC signature for webhook"""
        import hmac
        import hashlib
        
        signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return f'sha256={signature}'
    
    def test_webhook_download_progress(self):
        """Test download progress webhook"""
        payload_data = {
            'download_id': self.test_download.id,
            'progress': 75.5,
            'speed': '5.2 MB/s',
            'eta': '2m 30s'
        }
        
        payload = json.dumps(payload_data).encode()
        signature = self.generate_webhook_signature(payload)
        
        headers = {
            'X-Webhook-Signature': signature,
            'Content-Type': 'application/json'
        }
        
        response = self.client.post(
            '/api/v1/webhooks/download/progress',
            headers=headers,
            data=payload
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('message', data)
        
        # Verify download was updated
        db.session.refresh(self.test_download)
        self.assertEqual(self.test_download.progress_percentage, 75.5)
        self.assertEqual(self.test_download.download_speed, '5.2 MB/s')
    
    def test_webhook_invalid_signature(self):
        """Test webhook with invalid signature"""
        payload_data = {
            'download_id': self.test_download.id,
            'progress': 50
        }
        
        payload = json.dumps(payload_data).encode()
        
        headers = {
            'X-Webhook-Signature': 'sha256=invalid_signature',
            'Content-Type': 'application/json'
        }
        
        response = self.client.post(
            '/api/v1/webhooks/download/progress',
            headers=headers,
            data=payload
        )
        
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
