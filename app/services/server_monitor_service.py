import time
import threading
from datetime import datetime, timedelta
from app.models.servers import Server, ServerStatus
from app.services.file_transfer_service import FileTransferService
from app.services.logging_service import LoggingService
from app import db

class ServerMonitorService:
    def __init__(self):
        self.transfer_service = FileTransferService()
        self.logger = LoggingService()
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start server monitoring in background thread"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.logger.log_system('info', 'Server monitoring started')
    
    def stop_monitoring(self):
        """Stop server monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        self.logger.log_system('info', 'Server monitoring stopped')
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self.check_all_servers()
                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                self.logger.log_system('error', f'Error in server monitoring: {str(e)}')
                time.sleep(60)  # Wait 1 minute on error
    
    def check_all_servers(self):
        """Check status of all servers"""
        try:
            servers = Server.query.all()
            for server in servers:
                self.check_server_status(server)
        except Exception as e:
            self.logger.log_system('error', f'Error checking servers: {str(e)}')
    
    def check_server_status(self, server: Server):
        """Check individual server status"""
        try:
            start_time = time.time()
            
            # Test connection
            is_online = self.transfer_service.test_connection(server)
            
            response_time = time.time() - start_time
            
            # Update server status
            if is_online:
                server.update_status(ServerStatus.ONLINE)
                self.logger.log_server(
                    server.id,
                    'info',
                    f'Server {server.name} is online',
                    action='health_check',
                    response_time=response_time,
                    connection_status='success'
                )
                
                # Get disk usage if possible
                self.update_disk_usage(server)
            else:
                server.update_status(ServerStatus.OFFLINE)
                self.logger.log_server(
                    server.id,
                    'warning',
                    f'Server {server.name} is offline',
                    action='health_check',
                    response_time=response_time,
                    connection_status='failed'
                )
            
            db.session.commit()
            
        except Exception as e:
            server.update_status(ServerStatus.ERROR)
            db.session.commit()
            
            self.logger.log_server(
                server.id,
                'error',
                f'Error checking server {server.name}: {str(e)}',
                action='health_check',
                connection_status='error'
            )
    
    def update_disk_usage(self, server: Server):
        """Update disk usage information for server"""
        try:
            if server.protocol.value == 'sftp':
                self._update_disk_usage_sftp(server)
            elif server.protocol.value == 'nfs':
                self._update_disk_usage_nfs(server)
            elif server.protocol.value == 'smb':
                self._update_disk_usage_smb(server)
        except Exception as e:
            self.logger.log_server(
                server.id,
                'warning',
                f'Could not update disk usage for {server.name}: {str(e)}'
            )
    
    def _update_disk_usage_sftp(self, server: Server):
        """Update disk usage via SFTP"""
        import paramiko
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=server.host,
                port=server.port,
                username=server.username,
                password=server.password_hash if server.password_hash else None,
                key_filename=server.ssh_key_path if server.ssh_key_path else None,
                timeout=10
            )
            
            # Get disk usage
            stdin, stdout, stderr = ssh.exec_command(f"df {server.base_path}")
            output = stdout.read().decode()
            
            ssh.close()
            
            # Parse df output
            lines = output.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 5:
                    total = int(parts[1]) * 1024  # Convert to bytes
                    used = int(parts[2]) * 1024
                    available = int(parts[3]) * 1024
                    percentage = int(parts[4].rstrip('%'))
                    
                    server.update_disk_usage(
                        f"{total/1024/1024/1024:.1f}GB",
                        f"{used/1024/1024/1024:.1f}GB",
                        f"{available/1024/1024/1024:.1f}GB",
                        percentage
                    )
        
        except Exception as e:
            raise Exception(f"SFTP disk usage check failed: {str(e)}")
    
    def _update_disk_usage_nfs(self, server: Server):
        """Update disk usage for NFS mounted directory"""
        import os
        import shutil
        
        try:
            nfs_mount_point = f"/mnt/{server.name}"
            
            if not os.path.exists(nfs_mount_point):
                raise Exception(f"NFS mount point not found: {nfs_mount_point}")
            
            # Get disk usage
            total, used, free = shutil.disk_usage(nfs_mount_point)
            percentage = (used / total) * 100
            
            server.update_disk_usage(
                f"{total/1024/1024/1024:.1f}GB",
                f"{used/1024/1024/1024:.1f}GB",
                f"{free/1024/1024/1024:.1f}GB",
                int(percentage)
            )
        
        except Exception as e:
            raise Exception(f"NFS disk usage check failed: {str(e)}")
    
    def _update_disk_usage_smb(self, server: Server):
        """Update disk usage for SMB share"""
        # SMB disk usage check would require additional implementation
        # For now, we'll skip it
        pass
    
    def get_server_health_summary(self):
        """Get summary of server health"""
        try:
            total_servers = Server.query.count()
            online_servers = Server.query.filter_by(status=ServerStatus.ONLINE).count()
            offline_servers = Server.query.filter_by(status=ServerStatus.OFFLINE).count()
            error_servers = Server.query.filter_by(status=ServerStatus.ERROR).count()
            
            # Get servers with low disk space
            low_disk_servers = []
            servers = Server.query.all()
            for server in servers:
                disk_usage = server.disk_usage_dict
                if disk_usage and disk_usage.get('percentage', 0) > 90:
                    low_disk_servers.append(server)
            
            return {
                'total': total_servers,
                'online': online_servers,
                'offline': offline_servers,
                'error': error_servers,
                'low_disk': len(low_disk_servers),
                'low_disk_servers': low_disk_servers
            }
        
        except Exception as e:
            self.logger.log_system('error', f'Error getting server health summary: {str(e)}')
            return {}
    
    def test_server_connection(self, server_id: int):
        """Test connection to specific server"""
        try:
            server = Server.query.get(server_id)
            if not server:
                raise Exception("Server not found")
            
            self.check_server_status(server)
            return server.status == ServerStatus.ONLINE
        
        except Exception as e:
            self.logger.log_system('error', f'Error testing server connection: {str(e)}')
            return False




