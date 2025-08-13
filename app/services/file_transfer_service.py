import os
import shutil
import time
import subprocess
from typing import Callable, Tuple, Optional
import paramiko
from smb.SMBConnection import SMBConnection
from app.models.servers import Server
from app.services.logging_service import LoggingService

logger = LoggingService()

class FileTransferService:
    def __init__(self):
        pass
    
    def transfer_sftp(self, server: Server, source_path: str, destination_path: str, 
                     progress_callback: Optional[Callable] = None) -> Tuple[bool, Optional[str]]:
        """Transfer file using SFTP"""
        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to server
            ssh.connect(
                hostname=server.host,
                port=server.port,
                username=server.username,
                password=server.password_hash if server.password_hash else None,
                key_filename=server.ssh_key_path if server.ssh_key_path else None,
                timeout=30
            )
            
            # Create SFTP client
            sftp = ssh.open_sftp()
            
            # Get file size
            file_size = os.path.getsize(source_path)
            
            # Create remote directory if it doesn't exist
            remote_dir = os.path.dirname(destination_path)
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                sftp.mkdir(remote_dir)
            
            # Transfer file with progress callback
            start_time = time.time()
            transferred_bytes = 0
            
            def sftp_progress_callback(transferred, to_be_transferred):
                nonlocal transferred_bytes
                transferred_bytes = transferred
                if progress_callback:
                    elapsed_time = time.time() - start_time
                    speed = transferred / elapsed_time if elapsed_time > 0 else 0
                    progress_callback(transferred, file_size, speed)
            
            sftp.put(source_path, destination_path, callback=sftp_progress_callback)
            
            # Calculate transfer speed
            transfer_time = time.time() - start_time
            transfer_speed = file_size / transfer_time if transfer_time > 0 else 0
            
            sftp.close()
            ssh.close()
            
            logger.log_server(
                server.id,
                'info',
                f'SFTP transfer completed: {os.path.basename(source_path)}',
                action='transfer',
                response_time=transfer_time,
                connection_status='success'
            )
            
            return True, f"{transfer_speed/1024/1024:.1f} MB/s"
            
        except Exception as e:
            logger.log_server(
                server.id,
                'error',
                f'SFTP transfer failed: {str(e)}',
                action='transfer',
                connection_status='failed'
            )
            return False, None
    
    def transfer_nfs(self, server: Server, source_path: str, destination_path: str,
                    progress_callback: Optional[Callable] = None) -> Tuple[bool, Optional[str]]:
        """Transfer file using NFS (mounted directory)"""
        try:
            # For NFS, we assume the server path is mounted locally
            # This would need to be configured in the system
            nfs_mount_point = f"/mnt/{server.name}"
            
            if not os.path.exists(nfs_mount_point):
                raise Exception(f"NFS mount point not found: {nfs_mount_point}")
            
            # Construct full destination path
            full_destination = os.path.join(nfs_mount_point, destination_path.lstrip('/'))
            
            # Create destination directory
            os.makedirs(os.path.dirname(full_destination), exist_ok=True)
            
            # Get file size
            file_size = os.path.getsize(source_path)
            
            # Transfer file with progress tracking
            start_time = time.time()
            
            # Use shutil.copy2 for efficient copying
            shutil.copy2(source_path, full_destination)
            
            # Calculate transfer speed
            transfer_time = time.time() - start_time
            transfer_speed = file_size / transfer_time if transfer_time > 0 else 0
            
            logger.log_server(
                server.id,
                'info',
                f'NFS transfer completed: {os.path.basename(source_path)}',
                action='transfer',
                response_time=transfer_time,
                connection_status='success'
            )
            
            return True, f"{transfer_speed/1024/1024:.1f} MB/s"
            
        except Exception as e:
            logger.log_server(
                server.id,
                'error',
                f'NFS transfer failed: {str(e)}',
                action='transfer',
                connection_status='failed'
            )
            return False, None
    
    def transfer_smb(self, server: Server, source_path: str, destination_path: str,
                    progress_callback: Optional[Callable] = None) -> Tuple[bool, Optional[str]]:
        """Transfer file using SMB/CIFS"""
        try:
            # Parse server host and share
            host_parts = server.host.split('/')
            if len(host_parts) < 2:
                raise Exception("Invalid SMB host format. Expected: hostname/share")
            
            hostname = host_parts[0]
            share_name = host_parts[1]
            
            # Create SMB connection
            conn = SMBConnection(
                server.username,
                server.password_hash,
                'mediadownloader',
                hostname,
                use_ntlm_v2=True
            )
            
            # Connect to server
            connected = conn.connect(hostname, server.port)
            if not connected:
                raise Exception("Failed to connect to SMB server")
            
            # Get file size
            file_size = os.path.getsize(source_path)
            
            # Create remote directory if it doesn't exist
            remote_dir = os.path.dirname(destination_path)
            try:
                conn.listPath(share_name, remote_dir)
            except:
                conn.createDirectory(share_name, remote_dir)
            
            # Transfer file
            start_time = time.time()
            
            with open(source_path, 'rb') as source_file:
                conn.storeFile(share_name, destination_path, source_file)
            
            # Calculate transfer speed
            transfer_time = time.time() - start_time
            transfer_speed = file_size / transfer_time if transfer_time > 0 else 0
            
            conn.close()
            
            logger.log_server(
                server.id,
                'info',
                f'SMB transfer completed: {os.path.basename(source_path)}',
                action='transfer',
                response_time=transfer_time,
                connection_status='success'
            )
            
            return True, f"{transfer_speed/1024/1024:.1f} MB/s"
            
        except Exception as e:
            logger.log_server(
                server.id,
                'error',
                f'SMB transfer failed: {str(e)}',
                action='transfer',
                connection_status='failed'
            )
            return False, None
    
    def transfer_rsync(self, server: Server, source_path: str, destination_path: str,
                      progress_callback: Optional[Callable] = None) -> Tuple[bool, Optional[str]]:
        """Transfer file using rsync"""
        try:
            # Construct rsync command
            if server.ssh_key_path:
                rsync_cmd = [
                    'rsync',
                    '-avz',
                    '--progress',
                    '-e', f'ssh -i {server.ssh_key_path}',
                    source_path,
                    f"{server.username}@{server.host}:{destination_path}"
                ]
            else:
                rsync_cmd = [
                    'rsync',
                    '-avz',
                    '--progress',
                    source_path,
                    f"{server.username}@{server.host}:{destination_path}"
                ]
            
            # Execute rsync command
            start_time = time.time()
            
            process = subprocess.Popen(
                rsync_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor progress
            file_size = os.path.getsize(source_path)
            transferred_bytes = 0
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Parse rsync progress output
                    if '%' in output:
                        try:
                            percent_str = output.split('%')[0].split()[-1]
                            percent = float(percent_str)
                            transferred_bytes = int((percent / 100) * file_size)
                            
                            if progress_callback:
                                elapsed_time = time.time() - start_time
                                speed = transferred_bytes / elapsed_time if elapsed_time > 0 else 0
                                progress_callback(transferred_bytes, file_size, speed)
                        except:
                            pass
            
            # Wait for process to complete
            return_code = process.wait()
            
            if return_code != 0:
                raise Exception(f"rsync failed with return code {return_code}")
            
            # Calculate transfer speed
            transfer_time = time.time() - start_time
            transfer_speed = file_size / transfer_time if transfer_time > 0 else 0
            
            logger.log_server(
                server.id,
                'info',
                f'rsync transfer completed: {os.path.basename(source_path)}',
                action='transfer',
                response_time=transfer_time,
                connection_status='success'
            )
            
            return True, f"{transfer_speed/1024/1024:.1f} MB/s"
            
        except Exception as e:
            logger.log_server(
                server.id,
                'error',
                f'rsync transfer failed: {str(e)}',
                action='transfer',
                connection_status='failed'
            )
            return False, None
    
    def test_connection(self, server: Server) -> bool:
        """Test connection to server"""
        try:
            if server.protocol.value == 'sftp':
                return self._test_sftp_connection(server)
            elif server.protocol.value == 'nfs':
                return self._test_nfs_connection(server)
            elif server.protocol.value == 'smb':
                return self._test_smb_connection(server)
            elif server.protocol.value == 'rsync':
                return self._test_rsync_connection(server)
            else:
                return False
        except Exception as e:
            logger.log_server(
                server.id,
                'error',
                f'Connection test failed: {str(e)}',
                action='test_connection',
                connection_status='failed'
            )
            return False
    
    def _test_sftp_connection(self, server: Server) -> bool:
        """Test SFTP connection"""
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
            
            ssh.close()
            return True
        except:
            return False
    
    def _test_nfs_connection(self, server: Server) -> bool:
        """Test NFS connection"""
        try:
            nfs_mount_point = f"/mnt/{server.name}"
            return os.path.exists(nfs_mount_point) and os.access(nfs_mount_point, os.W_OK)
        except:
            return False
    
    def _test_smb_connection(self, server: Server) -> bool:
        """Test SMB connection"""
        try:
            host_parts = server.host.split('/')
            if len(host_parts) < 2:
                return False
            
            hostname = host_parts[0]
            
            conn = SMBConnection(
                server.username,
                server.password_hash,
                'mediadownloader',
                hostname,
                use_ntlm_v2=True
            )
            
            connected = conn.connect(hostname, server.port, timeout=10)
            conn.close()
            return connected
        except:
            return False
    
    def _test_rsync_connection(self, server: Server) -> bool:
        """Test rsync connection"""
        try:
            test_cmd = ['ssh', f"{server.username}@{server.host}", 'echo', 'test']
            if server.ssh_key_path:
                test_cmd = ['ssh', '-i', server.ssh_key_path, f"{server.username}@{server.host}", 'echo', 'test']
            
            result = subprocess.run(test_cmd, capture_output=True, timeout=10)
            return result.returncode == 0
        except:
            return False


