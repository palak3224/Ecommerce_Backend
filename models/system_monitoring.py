from datetime import datetime, timezone
from common.database import db, BaseModel
from decimal import Decimal

class SystemMonitoring(BaseModel):
    __tablename__ = 'system_monitoring'

    monitoring_id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # System Status Fields
    service_name = db.Column(db.String(100), nullable=False)  # e.g., 'auth_service', 'product_service'
    status = db.Column(db.String(20), nullable=False)  # 'up', 'down', 'degraded'
    response_time = db.Column(db.Float, nullable=True)  # in milliseconds
    memory_usage = db.Column(db.Float, nullable=True)  # in MB
    cpu_usage = db.Column(db.Float, nullable=True)  # percentage
    
    # Error Tracking
    error_type = db.Column(db.String(100), nullable=True)  # e.g., 'DatabaseError', 'TimeoutError'
    error_message = db.Column(db.Text, nullable=True)
    error_stack_trace = db.Column(db.Text, nullable=True)
    endpoint = db.Column(db.String(255), nullable=True)  # API endpoint where error occurred
    http_method = db.Column(db.String(10), nullable=True)  # GET, POST, etc.
    http_status = db.Column(db.Integer, nullable=True)
    
    # Additional Metrics
    request_count = db.Column(db.Integer, default=0)
    active_connections = db.Column(db.Integer, nullable=True)
    database_connections = db.Column(db.Integer, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.Index('idx_monitoring_timestamp', 'timestamp'),
        db.Index('idx_monitoring_service', 'service_name'),
        db.Index('idx_monitoring_status', 'status'),
    )

    @classmethod
    def create_service_status(cls, service_name, status, response_time=None, 
                            memory_usage=None, cpu_usage=None):
        """Create a new service status record"""
        return cls(
            service_name=service_name,
            status=status,
            response_time=response_time,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage
        )

    @classmethod
    def create_error_record(cls, service_name, error_type, error_message, 
                          error_stack_trace=None, endpoint=None, 
                          http_method=None, http_status=None):
        """Create a new error record"""
        return cls(
            service_name=service_name,
            status='error',
            error_type=error_type,
            error_message=error_message,
            error_stack_trace=error_stack_trace,
            endpoint=endpoint,
            http_method=http_method,
            http_status=http_status
        )

    def update_metrics(self, response_time=None, memory_usage=None, 
                      cpu_usage=None, request_count=None):
        """Update service metrics"""
        if response_time is not None:
            self.response_time = response_time
        if memory_usage is not None:
            self.memory_usage = memory_usage
        if cpu_usage is not None:
            self.cpu_usage = cpu_usage
        if request_count is not None:
            self.request_count = request_count
        self.updated_at = datetime.now(timezone.utc)

    def serialize(self):
        """Convert monitoring data to dictionary format"""
        return {
            "monitoring_id": self.monitoring_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "service_name": self.service_name,
            "status": self.status,
            "response_time": self.response_time,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_stack_trace": self.error_stack_trace,
            "endpoint": self.endpoint,
            "http_method": self.http_method,
            "http_status": self.http_status,
            "request_count": self.request_count,
            "active_connections": self.active_connections,
            "database_connections": self.database_connections,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted
        } 