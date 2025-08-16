import time
import psutil
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from flask import current_app, g
import json
import redis

@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = None
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'tags': self.tags or {}
        }

@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    memory_total: int
    memory_available: int
    disk_usage: float
    disk_total: int
    disk_free: int
    network_sent: int
    network_recv: int
    process_count: int
    load_average: List[float]
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ApplicationMetrics:
    """Application-specific metrics"""
    timestamp: datetime
    active_downloads: int
    completed_downloads: int
    failed_downloads: int
    total_downloads: int
    active_users: int
    api_requests_total: int
    api_requests_rate: float
    database_connections: int
    redis_connections: int
    celery_tasks_pending: int
    celery_tasks_processing: int
    celery_workers_online: int
    
    def to_dict(self):
        return asdict(self)

class MetricsCollector:
    """Collects and stores system and application metrics"""
    
    def __init__(self, redis_client=None, retention_hours=24):
        self.redis_client = redis_client or self._get_redis_client()
        self.retention_hours = retention_hours
        self.metrics_buffer = defaultdict(lambda: deque(maxlen=1000))
        self.api_requests_counter = defaultdict(int)
        self.api_response_times = defaultdict(list)
        self.last_network_stats = None
        self.start_time = datetime.utcnow()
        
        # Start background collection
        self._start_collection_thread()
    
    def _get_redis_client(self):
        """Get Redis client for metrics storage"""
        try:
            import redis
            return redis.Redis(
                host=current_app.config.get('REDIS_HOST', 'localhost'),
                port=current_app.config.get('REDIS_PORT', 6379),
                db=current_app.config.get('REDIS_METRICS_DB', 2),
                decode_responses=True
            )
        except:
            return None
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Network I/O
            network = psutil.net_io_counters()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Load average (Unix only)
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                load_avg = [0.0, 0.0, 0.0]
            
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                memory_total=memory.total,
                memory_available=memory.available,
                disk_usage=round((disk.used / disk.total) * 100, 2),
                disk_total=disk.total,
                disk_free=disk.free,
                network_sent=network.bytes_sent,
                network_recv=network.bytes_recv,
                process_count=process_count,
                load_average=load_avg
            )
            
        except Exception as e:
            print(f"Error collecting system metrics: {e}")
            return None
    
    def collect_application_metrics(self) -> ApplicationMetrics:
        """Collect current application metrics"""
        try:
            from app.models.downloads import Download, DownloadStatus
            from app.models.users import User
            
            # Download statistics
            active_downloads = Download.query.filter(
                Download.status.in_([DownloadStatus.DOWNLOADING, DownloadStatus.TRANSFERRING])
            ).count()
            
            completed_downloads = Download.query.filter_by(status=DownloadStatus.COMPLETED).count()
            failed_downloads = Download.query.filter_by(status=DownloadStatus.FAILED).count()
            total_downloads = Download.query.count()
            
            # User statistics
            active_users = User.query.filter_by(is_active=True).count()
            
            # API request statistics
            api_requests_total = sum(self.api_requests_counter.values())
            api_requests_rate = self._calculate_request_rate()
            
            # Database connections (simplified)
            database_connections = 1  # Would implement actual connection count
            
            # Redis connections
            redis_connections = 1 if self.redis_client else 0
            
            # Celery statistics (would implement actual Celery inspection)
            celery_tasks_pending = 0
            celery_tasks_processing = 0
            celery_workers_online = 0
            
            return ApplicationMetrics(
                timestamp=datetime.utcnow(),
                active_downloads=active_downloads,
                completed_downloads=completed_downloads,
                failed_downloads=failed_downloads,
                total_downloads=total_downloads,
                active_users=active_users,
                api_requests_total=api_requests_total,
                api_requests_rate=api_requests_rate,
                database_connections=database_connections,
                redis_connections=redis_connections,
                celery_tasks_pending=celery_tasks_pending,
                celery_tasks_processing=celery_tasks_processing,
                celery_workers_online=celery_workers_online
            )
            
        except Exception as e:
            print(f"Error collecting application metrics: {e}")
            return None
    
    def _calculate_request_rate(self) -> float:
        """Calculate API requests per minute"""
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        
        # Count requests in last minute (simplified)
        recent_requests = 0
        for endpoint, count in self.api_requests_counter.items():
            recent_requests += count
        
        return recent_requests / 60.0  # requests per second
    
    def record_api_request(self, endpoint: str, method: str, status_code: int, response_time: float):
        """Record API request metrics"""
        key = f"{method}:{endpoint}"
        self.api_requests_counter[key] += 1
        self.api_response_times[key].append(response_time)
        
        # Keep only recent response times
        if len(self.api_response_times[key]) > 100:
            self.api_response_times[key] = self.api_response_times[key][-100:]
        
        # Store in Redis if available
        if self.redis_client:
            try:
                metric_key = f"api_request:{key}:{int(time.time())}"
                metric_data = {
                    'endpoint': endpoint,
                    'method': method,
                    'status_code': status_code,
                    'response_time': response_time,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                self.redis_client.setex(metric_key, 3600, json.dumps(metric_data))
            except Exception as e:
                print(f"Error storing API metric: {e}")
    
    def record_custom_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record custom application metric"""
        metric = MetricPoint(
            timestamp=datetime.utcnow(),
            value=value,
            tags=tags or {}
        )
        
        self.metrics_buffer[name].append(metric)
        
        # Store in Redis if available
        if self.redis_client:
            try:
                metric_key = f"custom_metric:{name}:{int(time.time())}"
                self.redis_client.setex(metric_key, 3600, json.dumps(metric.to_dict()))
            except Exception:
                pass
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the specified time period"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        summary = {
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'hours': hours
            },
            'system': self._get_system_metrics_summary(start_time, end_time),
            'application': self._get_application_metrics_summary(start_time, end_time),
            'api': self._get_api_metrics_summary(start_time, end_time),
            'custom': self._get_custom_metrics_summary(start_time, end_time)
        }
        
        return summary
    
    def _get_system_metrics_summary(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get system metrics summary"""
        current_metrics = self.collect_system_metrics()
        
        if not current_metrics:
            return {}
        
        return {
            'current': current_metrics.to_dict(),
            'averages': {
                'cpu_usage': current_metrics.cpu_usage,
                'memory_usage': current_metrics.memory_usage,
                'disk_usage': current_metrics.disk_usage
            },
            'alerts': self._check_system_alerts(current_metrics)
        }
    
    def _get_application_metrics_summary(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get application metrics summary"""
        current_metrics = self.collect_application_metrics()
        
        if not current_metrics:
            return {}
        
        return {
            'current': current_metrics.to_dict(),
            'trends': {
                'download_completion_rate': self._calculate_completion_rate(),
                'user_activity': self._calculate_user_activity(),
                'system_health': self._calculate_system_health()
            }
        }
    
    def _get_api_metrics_summary(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get API metrics summary"""
        total_requests = sum(self.api_requests_counter.values())
        
        # Calculate average response times
        avg_response_times = {}
        for endpoint, times in self.api_response_times.items():
            if times:
                avg_response_times[endpoint] = sum(times) / len(times)
        
        return {
            'total_requests': total_requests,
            'requests_per_endpoint': dict(self.api_requests_counter),
            'average_response_times': avg_response_times,
            'slowest_endpoints': self._get_slowest_endpoints(),
            'error_rate': self._calculate_error_rate()
        }
    
    def _get_custom_metrics_summary(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get custom metrics summary"""
        summary = {}
        
        for metric_name, points in self.metrics_buffer.items():
            if points:
                values = [p.value for p in points]
                summary[metric_name] = {
                    'count': len(values),
                    'latest': values[-1] if values else None,
                    'average': sum(values) / len(values) if values else 0,
                    'min': min(values) if values else 0,
                    'max': max(values) if values else 0
                }
        
        return summary
    
    def _check_system_alerts(self, metrics: SystemMetrics) -> List[Dict]:
        """Check for system alerts based on thresholds"""
        alerts = []
        
        # CPU usage alert
        if metrics.cpu_usage > 90:
            alerts.append({
                'type': 'critical',
                'metric': 'cpu_usage',
                'value': metrics.cpu_usage,
                'threshold': 90,
                'message': f'High CPU usage: {metrics.cpu_usage:.1f}%'
            })
        elif metrics.cpu_usage > 75:
            alerts.append({
                'type': 'warning',
                'metric': 'cpu_usage',
                'value': metrics.cpu_usage,
                'threshold': 75,
                'message': f'Elevated CPU usage: {metrics.cpu_usage:.1f}%'
            })
        
        # Memory usage alert
        if metrics.memory_usage > 90:
            alerts.append({
                'type': 'critical',
                'metric': 'memory_usage',
                'value': metrics.memory_usage,
                'threshold': 90,
                'message': f'High memory usage: {metrics.memory_usage:.1f}%'
            })
        elif metrics.memory_usage > 75:
            alerts.append({
                'type': 'warning',
                'metric': 'memory_usage',
                'value': metrics.memory_usage,
                'threshold': 75,
                'message': f'Elevated memory usage: {metrics.memory_usage:.1f}%'
            })
        
        # Disk usage alert
        if metrics.disk_usage > 95:
            alerts.append({
                'type': 'critical',
                'metric': 'disk_usage',
                'value': metrics.disk_usage,
                'threshold': 95,
                'message': f'Critical disk usage: {metrics.disk_usage:.1f}%'
            })
        elif metrics.disk_usage > 85:
            alerts.append({
                'type': 'warning',
                'metric': 'disk_usage',
                'value': metrics.disk_usage,
                'threshold': 85,
                'message': f'High disk usage: {metrics.disk_usage:.1f}%'
            })
        
        return alerts
    
    def _calculate_completion_rate(self) -> float:
        """Calculate download completion rate"""
        try:
            from app.models.downloads import Download, DownloadStatus
            
            total = Download.query.count()
            completed = Download.query.filter_by(status=DownloadStatus.COMPLETED).count()
            
            return (completed / total * 100) if total > 0 else 0
        except:
            return 0
    
    def _calculate_user_activity(self) -> Dict:
        """Calculate user activity metrics"""
        try:
            from app.models.users import User
            from app.models.logs import UserActivityLog
            
            # Users active in last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_activity = UserActivityLog.query.filter(
                UserActivityLog.timestamp >= one_hour_ago
            ).count()
            
            return {
                'recent_activity_count': recent_activity,
                'active_users': User.query.filter_by(is_active=True).count()
            }
        except:
            return {'recent_activity_count': 0, 'active_users': 0}
    
    def _calculate_system_health(self) -> str:
        """Calculate overall system health score"""
        system_metrics = self.collect_system_metrics()
        app_metrics = self.collect_application_metrics()
        
        if not system_metrics or not app_metrics:
            return 'unknown'
        
        # Simple health calculation
        health_score = 100
        
        # Deduct points for high resource usage
        if system_metrics.cpu_usage > 75:
            health_score -= 20
        if system_metrics.memory_usage > 75:
            health_score -= 20
        if system_metrics.disk_usage > 85:
            health_score -= 30
        
        # Deduct points for failed downloads
        if app_metrics.total_downloads > 0:
            failure_rate = (app_metrics.failed_downloads / app_metrics.total_downloads) * 100
            if failure_rate > 10:
                health_score -= 20
        
        if health_score >= 80:
            return 'healthy'
        elif health_score >= 60:
            return 'warning'
        else:
            return 'critical'
    
    def _get_slowest_endpoints(self, limit: int = 5) -> List[Dict]:
        """Get slowest API endpoints"""
        endpoint_times = []
        
        for endpoint, times in self.api_response_times.items():
            if times:
                avg_time = sum(times) / len(times)
                endpoint_times.append({
                    'endpoint': endpoint,
                    'average_response_time': avg_time,
                    'request_count': len(times)
                })
        
        return sorted(endpoint_times, key=lambda x: x['average_response_time'], reverse=True)[:limit]
    
    def _calculate_error_rate(self) -> float:
        """Calculate API error rate"""
        # This would need to track error responses
        # For now, return 0
        return 0.0
    
    def _start_collection_thread(self):
        """Start background thread for metrics collection"""
        def collect_metrics():
            while True:
                try:
                    # Collect metrics every 60 seconds
                    system_metrics = self.collect_system_metrics()
                    app_metrics = self.collect_application_metrics()
                    
                    if system_metrics and self.redis_client:
                        key = f"system_metrics:{int(time.time())}"
                        self.redis_client.setex(key, 3600, json.dumps(system_metrics.to_dict()))
                    
                    if app_metrics and self.redis_client:
                        key = f"app_metrics:{int(time.time())}"
                        self.redis_client.setex(key, 3600, json.dumps(app_metrics.to_dict()))
                    
                    time.sleep(60)
                    
                except Exception as e:
                    print(f"Error in metrics collection thread: {e}")
                    time.sleep(60)
        
        thread = threading.Thread(target=collect_metrics, daemon=True)
        thread.start()
    
    def export_metrics(self, format: str = 'json', hours: int = 24) -> str:
        """Export metrics in various formats"""
        summary = self.get_metrics_summary(hours)
        
        if format == 'json':
            return json.dumps(summary, indent=2)
        elif format == 'prometheus':
            return self._format_prometheus_metrics(summary)
        else:
            return json.dumps(summary)
    
    def _format_prometheus_metrics(self, summary: Dict) -> str:
        """Format metrics for Prometheus"""
        lines = []
        
        # System metrics
        if 'system' in summary and 'current' in summary['system']:
            system = summary['system']['current']
            lines.append(f"mediadown_cpu_usage {system['cpu_usage']}")
            lines.append(f"mediadown_memory_usage {system['memory_usage']}")
            lines.append(f"mediadown_disk_usage {system['disk_usage']}")
        
        # Application metrics
        if 'application' in summary and 'current' in summary['application']:
            app = summary['application']['current']
            lines.append(f"mediadown_active_downloads {app['active_downloads']}")
            lines.append(f"mediadown_completed_downloads {app['completed_downloads']}")
            lines.append(f"mediadown_failed_downloads {app['failed_downloads']}")
            lines.append(f"mediadown_total_downloads {app['total_downloads']}")
        
        return '\n'.join(lines)

# Global metrics collector instance
metrics_collector = MetricsCollector()

def record_api_request(endpoint: str, method: str, status_code: int, response_time: float):
    """Helper function to record API request metrics"""
    metrics_collector.record_api_request(endpoint, method, status_code, response_time)

def record_custom_metric(name: str, value: float, tags: Dict[str, str] = None):
    """Helper function to record custom metrics"""
    metrics_collector.record_custom_metric(name, value, tags)

def get_metrics_summary(hours: int = 1) -> Dict[str, Any]:
    """Helper function to get metrics summary"""
    return metrics_collector.get_metrics_summary(hours)
