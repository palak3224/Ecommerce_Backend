from common.database import db
from models.system_monitoring import SystemMonitoring
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc, and_, case
import psutil
import time

class SystemMonitoringController:
    @staticmethod
    def get_system_status():
        """Get current system status and uptime"""
        try:
            # Get current system metrics
            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
            cpu_usage = process.cpu_percent()
            uptime = time.time() - psutil.boot_time()

            # Get latest status for each service
            services = db.session.query(
                SystemMonitoring.service_name,
                SystemMonitoring.status,
                SystemMonitoring.response_time,
                SystemMonitoring.timestamp
            ).order_by(
                SystemMonitoring.timestamp.desc()
            ).distinct(
                SystemMonitoring.service_name
            ).all()

            return {
                'status': 'success',
                'data': {
                    'system_metrics': {
                        'memory_usage_mb': round(memory_usage, 2),
                        'cpu_usage_percent': round(cpu_usage, 2),
                        'uptime_seconds': round(uptime, 2),
                        'uptime_formatted': str(timedelta(seconds=int(uptime)))
                    },
                    'services': [{
                        'service_name': service.service_name,
                        'status': service.status,
                        'response_time': service.response_time,
                        'last_updated': service.timestamp.isoformat()
                    } for service in services]
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def get_response_times(hours=24):
        """Get response time trends and averages"""
        try:
            time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Get average response time by service
            avg_response_times = db.session.query(
                SystemMonitoring.service_name,
                func.avg(SystemMonitoring.response_time).label('avg_response_time'),
                func.min(SystemMonitoring.response_time).label('min_response_time'),
                func.max(SystemMonitoring.response_time).label('max_response_time')
            ).filter(
                SystemMonitoring.timestamp >= time_threshold,
                SystemMonitoring.response_time.isnot(None)
            ).group_by(
                SystemMonitoring.service_name
            ).all()

            # Get response time trend (hourly averages)
            hourly_trend = db.session.query(
                func.date_format(
                    func.convert_tz(SystemMonitoring.timestamp, '+00:00', '+05:30'),
                    '%Y-%m-%d %H:00:00'
                ).label('hour'),
                func.avg(SystemMonitoring.response_time).label('avg_response_time')
            ).filter(
                SystemMonitoring.timestamp >= time_threshold,
                SystemMonitoring.response_time.isnot(None)
            ).group_by(
                func.date_format(
                    func.convert_tz(SystemMonitoring.timestamp, '+00:00', '+05:30'),
                    '%Y-%m-%d %H:00:00'
                )
            ).order_by(
                func.date_format(
                    func.convert_tz(SystemMonitoring.timestamp, '+00:00', '+05:30'),
                    '%Y-%m-%d %H:00:00'
                )
            ).all()

            # Calculate overall summary
            all_response_times = [rt.avg_response_time for rt in avg_response_times if rt.avg_response_time is not None]
            summary = {
                'average': round(sum(all_response_times) / len(all_response_times), 2) if all_response_times else 0,
                'min': round(min(all_response_times), 2) if all_response_times else 0,
                'max': round(max(all_response_times), 2) if all_response_times else 0
            }

            return {
                'status': 'success',
                'data': {
                    'response_times': [{
                        'timestamp': trend.hour,
                        'average_time': round(trend.avg_response_time, 2)
                    } for trend in hourly_trend],
                    'summary': summary
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def get_error_distribution(hours=24):
        """Get error distribution and details"""
        try:
            time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Get error count by type
            error_counts = db.session.query(
                SystemMonitoring.error_type,
                func.count(SystemMonitoring.monitoring_id).label('count')
            ).filter(
                SystemMonitoring.timestamp >= time_threshold,
                SystemMonitoring.status == 'error'
            ).group_by(
                SystemMonitoring.error_type
            ).all()

            # Get recent errors with details
            recent_errors = db.session.query(
                SystemMonitoring
            ).filter(
                SystemMonitoring.timestamp >= time_threshold,
                SystemMonitoring.status == 'error'
            ).order_by(
                SystemMonitoring.timestamp.desc()
            ).limit(50).all()

            return {
                'status': 'success',
                'data': {
                    'error_distribution': [{
                        'error_type': error.error_type,
                        'count': error.count
                    } for error in error_counts],
                    'recent_errors': [{
                        'timestamp': error.timestamp.isoformat(),
                        'service_name': error.service_name,
                        'error_type': error.error_type,
                        'error_message': error.error_message,
                        'endpoint': error.endpoint,
                        'http_method': error.http_method,
                        'http_status': error.http_status
                    } for error in recent_errors]
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def get_service_status(service_name, hours=24):
        """Get detailed status for a specific service"""
        try:
            time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Get service metrics
            service_metrics = db.session.query(
                func.avg(SystemMonitoring.response_time).label('avg_response_time'),
                func.min(SystemMonitoring.response_time).label('min_response_time'),
                func.max(SystemMonitoring.response_time).label('max_response_time'),
                func.count(SystemMonitoring.monitoring_id).label('total_requests'),
                func.sum(case((SystemMonitoring.status == 'error', 1), else_=0)).label('error_count'),
                func.avg(SystemMonitoring.cpu_usage).label('avg_cpu_usage'),
                func.avg(SystemMonitoring.memory_usage).label('avg_memory_usage')
            ).filter(
                SystemMonitoring.service_name == service_name,
                SystemMonitoring.timestamp >= time_threshold
            ).first()

            # Get hourly metrics for trend analysis
            hourly_metrics = db.session.query(
                func.date_format(
                    func.convert_tz(SystemMonitoring.timestamp, '+00:00', '+05:30'),
                    '%Y-%m-%d %H:00:00'
                ).label('hour'),
                func.avg(SystemMonitoring.response_time).label('avg_response_time'),
                func.avg(SystemMonitoring.cpu_usage).label('avg_cpu_usage'),
                func.avg(SystemMonitoring.memory_usage).label('avg_memory_usage'),
                func.count(case((SystemMonitoring.status == 'error', 1), else_=0)).label('error_count'),
                func.count(SystemMonitoring.monitoring_id).label('request_count')
            ).filter(
                SystemMonitoring.service_name == service_name,
                SystemMonitoring.timestamp >= time_threshold
            ).group_by(
                func.date_format(
                    func.convert_tz(SystemMonitoring.timestamp, '+00:00', '+05:30'),
                    '%Y-%m-%d %H:00:00'
                )
            ).order_by(
                func.date_format(
                    func.convert_tz(SystemMonitoring.timestamp, '+00:00', '+05:30'),
                    '%Y-%m-%d %H:00:00'
                )
            ).all()

            # Get recent errors
            recent_errors = db.session.query(
                SystemMonitoring
            ).filter(
                SystemMonitoring.service_name == service_name,
                SystemMonitoring.status == 'error',
                SystemMonitoring.timestamp >= time_threshold
            ).order_by(
                SystemMonitoring.timestamp.desc()
            ).limit(10).all()

            # Calculate metrics
            total_requests = service_metrics.total_requests or 0
            error_count = service_metrics.error_count or 0
            error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
            uptime_percentage = ((total_requests - error_count) / total_requests * 100) if total_requests > 0 else 100

            # Calculate performance score (0-100)
            response_score = 100 - (service_metrics.avg_response_time / 1000 * 10) if service_metrics.avg_response_time else 100
            error_score = 100 - error_rate
            cpu_score = 100 - (service_metrics.avg_cpu_usage or 0)
            memory_score = 100 - ((service_metrics.avg_memory_usage or 0) / 1024)  # Assuming memory in MB
            performance_score = (response_score + error_score + cpu_score + memory_score) / 4

            return {
                'status': 'success',
                'data': {
                    'service_name': service_name,
                    'metrics': {
                        'response_time': {
                            'average': round(service_metrics.avg_response_time or 0, 2),
                            'minimum': round(service_metrics.min_response_time or 0, 2),
                            'maximum': round(service_metrics.max_response_time or 0, 2)
                        },
                        'requests': {
                            'total': total_requests,
                            'error_count': error_count,
                            'error_rate': round(error_rate, 2),
                            'success_rate': round(100 - error_rate, 2)
                        },
                        'resources': {
                            'cpu_usage': round(service_metrics.avg_cpu_usage or 0, 2),
                            'memory_usage': round(service_metrics.avg_memory_usage or 0, 2)
                        },
                        'uptime': round(uptime_percentage, 2),
                        'performance_score': round(performance_score, 2)
                    },
                    'hourly_trends': [{
                        'timestamp': metric.hour,
                        'response_time': round(metric.avg_response_time or 0, 2),
                        'cpu_usage': round(metric.avg_cpu_usage or 0, 2),
                        'memory_usage': round(metric.avg_memory_usage or 0, 2),
                        'error_count': metric.error_count,
                        'request_count': metric.request_count
                    } for metric in hourly_metrics],
                    'recent_errors': [{
                        'timestamp': error.timestamp.isoformat(),
                        'error_type': error.error_type,
                        'error_message': error.error_message,
                        'endpoint': error.endpoint,
                        'http_method': error.http_method,
                        'http_status': error.http_status
                    } for error in recent_errors]
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def get_system_health(hours=1):
        """Get overall system health status"""
        try:
            time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Get current system metrics
            process = psutil.Process()
            system_memory = psutil.virtual_memory()
            memory_usage = system_memory.used / 1024 / 1024  # Convert to MB
            cpu_usage = process.cpu_percent()
            disk_usage = psutil.disk_usage('/').percent

            # Get service health metrics
            service_health = db.session.query(
                SystemMonitoring.service_name,
                func.avg(SystemMonitoring.response_time).label('avg_response_time'),
                func.count(case((SystemMonitoring.status == 'error', 1), else_=0)).label('error_count'),
                func.count(SystemMonitoring.monitoring_id).label('total_requests'),
                func.avg(SystemMonitoring.memory_usage).label('avg_memory_usage'),
                func.avg(SystemMonitoring.cpu_usage).label('avg_cpu_usage')
            ).filter(
                SystemMonitoring.timestamp >= time_threshold
            ).group_by(
                SystemMonitoring.service_name
            ).all()

            # Calculate health scores
            health_scores = []
            for service in service_health:
                error_rate = (service.error_count / service.total_requests * 100) if service.total_requests > 0 else 0
                response_score = 100 - (service.avg_response_time / 1000 * 10) if service.avg_response_time else 100
                memory_score = 100 - ((service.avg_memory_usage or 0) / system_memory.total * 100)
                cpu_score = 100 - (service.avg_cpu_usage or 0)
                health_score = (100 - error_rate + response_score + memory_score + cpu_score) / 4

                health_scores.append({
                    'service_name': service.service_name,
                    'health_score': round(health_score, 2),
                    'error_rate': round(error_rate, 2),
                    'avg_response_time': round(service.avg_response_time or 0, 2),
                    'memory_usage': round(service.avg_memory_usage or 0, 2),
                    'cpu_usage': round(service.avg_cpu_usage or 0, 2)
                })

            return {
                'status': 'success',
                'data': {
                    'system_metrics': {
                        'memory_usage_percent': round((system_memory.used / system_memory.total) * 100, 2),
                        'memory_usage_mb': round(memory_usage, 2),
                        'cpu_usage_percent': round(cpu_usage, 2),
                        'disk_usage_percent': round(disk_usage, 2)
                    },
                    'service_health': health_scores,
                    'overall_health': round(sum(score['health_score'] for score in health_scores) / len(health_scores), 2) if health_scores else 100
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)} 