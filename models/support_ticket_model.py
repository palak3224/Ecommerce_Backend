from common.database import db 
from auth.models import User, MerchantProfile 
from models.enums import TicketPriority, TicketStatus, TicketCreatorRole 
from sqlalchemy.orm import validates, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime, Enum as SAEnum 
import datetime
import secrets

def generate_ticket_uid():
    # Generates a 6-character uppercase alphanumeric string
    return secrets.token_hex(3).upper() 

class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_uid: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, default=generate_ticket_uid, index=True)
    
    creator_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    # Storing as VARCHAR, validated by Python Enum on the way in
    creator_role: Mapped[str] = mapped_column(String(20), nullable=False) 

    # merchant_id is now nullable, only set if creator_role is MERCHANT
    merchant_id: Mapped[int] = mapped_column(ForeignKey('merchant_profiles.id', ondelete='SET NULL'), nullable=True, index=True) 
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str] = mapped_column(String(512), nullable=True)
    
    # Storing as VARCHAR, validated by Python Enum
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default=TicketPriority.MEDIUM.value)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=TicketStatus.OPEN.value)

    assigned_to_admin_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Optional fields for linking to orders or products
    related_order_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True) 
    # Assuming product_id is integer in your products table, adjust if different
    related_product_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True) 

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    resolved_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    creator = relationship('User', foreign_keys=[creator_user_id], backref=db.backref('created_support_tickets', lazy='dynamic'))
    merchant = relationship('MerchantProfile', foreign_keys=[merchant_id], backref=db.backref('support_tickets', lazy='dynamic'))
    assigned_admin = relationship('User', foreign_keys=[assigned_to_admin_id], backref=db.backref('assigned_support_tickets', lazy='dynamic'))
    
    messages = relationship(
        'SupportTicketMessage', 
        back_populates='ticket',  
        lazy='dynamic', 
        cascade="all, delete-orphan", 
        order_by="SupportTicketMessage.created_at"
    )

    @validates('priority')
    def validate_priority_str(self, key, value):
        if isinstance(value, TicketPriority):
            return value.value
        try:
            return TicketPriority(value).value
        except ValueError:
            raise ValueError(f"Invalid priority value: {value}. Must be one of {[item.value for item in TicketPriority]}")

    @validates('status')
    def validate_status_str(self, key, value):
        if isinstance(value, TicketStatus):
            return value.value
        try:
            return TicketStatus(value).value
        except ValueError:
            raise ValueError(f"Invalid status value: {value}. Must be one of {[item.value for item in TicketStatus]}")

    @validates('creator_role')
    def validate_creator_role_str(self, key, value):
        if isinstance(value, TicketCreatorRole):
            return value.value
        try:
            return TicketCreatorRole(value).value
        except ValueError:
            raise ValueError(f"Invalid creator_role value: {value}. Must be one of {[item.value for item in TicketCreatorRole]}")

    def serialize(self, include_messages=False, user_role='ANONYMOUS'):
        creator_name = "Unknown User"
        if self.creator:
            creator_name = f"{self.creator.first_name} {self.creator.last_name}".strip()
            if not creator_name and self.creator.email: # Fallback to email if name is empty
                creator_name = self.creator.email

        data = {
            'id': self.id,
            'ticket_uid': self.ticket_uid,
            'creator_user_id': self.creator_user_id,
            'creator_name': creator_name,
            'creator_role': self.creator_role, # Raw value from DB
            'merchant_id': self.merchant_id,
            'merchant_name': self.merchant.business_name if self.merchant else None,
            'title': self.title,
            'description': self.description,
            'image_url': self.image_url,
            'priority': self.priority,
            'status': self.status,
            'assigned_to_admin_id': self.assigned_to_admin_id,
            'assigned_admin_name': f"{self.assigned_admin.first_name} {self.assigned_admin.last_name}".strip() if self.assigned_admin else None,
            'related_order_id': self.related_order_id,
            'related_product_id': self.related_product_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }
        
        # Only include messages if requested and user has permission
        # (e.g., admin, or the creator of the ticket)
        # This permission check would typically be done in the controller/route.
        # Here we assume if include_messages is true, permission is granted.
        if include_messages:
            data['messages'] = [message.serialize() for message in self.messages.order_by(SupportTicketMessage.created_at.asc()).all()]
        
        return data

    def __repr__(self):
        return f"<SupportTicket {self.ticket_uid} - '{self.title[:30]}...' by User {self.creator_user_id}>"

class SupportTicketMessage(db.Model):
    __tablename__ = 'support_ticket_messages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey('support_tickets.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True) # Allow NULL if sender user is deleted
    
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str] = mapped_column(String(512), nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    ticket = relationship('SupportTicket', back_populates='messages') 
    sender = relationship('User', backref=db.backref('sent_support_messages', lazy='dynamic'))

    def serialize(self):
        sender_name = "User (Deleted)" # Default if sender is somehow null
        sender_role = "UNKNOWN"
        is_admin_sender = False

        if self.sender:
            sender_name = f"{self.sender.first_name} {self.sender.last_name}".strip()
            if not sender_name and self.sender.email:
                sender_name = self.sender.email
            
            if hasattr(self.sender, 'role') and self.sender.role:
                sender_role_value = self.sender.role.name if hasattr(self.sender.role, 'name') else str(self.sender.role)
                sender_role = sender_role_value.upper() 
                is_admin_sender = sender_role in ['ADMIN', 'SUPERADMIN', 'SUPPORT_TEAM'] 

        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'sender_user_id': self.sender_user_id,
            'sender_name': sender_name,
            'sender_role': sender_role, 
            'is_admin_reply': is_admin_sender, 
            'message_text': self.message_text,
            'attachment_url': self.attachment_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<SupportTicketMessage {self.id} (Ticket: {self.ticket_id} Sender: {self.sender_user_id})>"