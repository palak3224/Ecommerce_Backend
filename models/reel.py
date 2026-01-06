# models/reel.py
from datetime import datetime, timezone
from common.database import db, BaseModel
from auth.models.models import MerchantProfile, User
from models.product import Product
from models.product_stock import ProductStock


class Reel(BaseModel):
    """Reel model for mobile app video content."""
    __tablename__ = 'reels'
    
    reel_id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False, index=True)
    
    # Video storage
    video_url = db.Column(db.String(512), nullable=False)
    video_public_id = db.Column(db.String(255), nullable=True)  # Cloudinary public_id or S3 key
    thumbnail_url = db.Column(db.String(512), nullable=True)
    thumbnail_public_id = db.Column(db.String(255), nullable=True)
    
    # Metadata
    description = db.Column(db.Text, nullable=False)  # REQUIRED
    duration_seconds = db.Column(db.Integer, nullable=True)
    file_size_bytes = db.Column(db.BigInteger, nullable=True)
    video_format = db.Column(db.String(10), nullable=True)  # mp4, mov, avi, etc.
    resolution = db.Column(db.String(20), nullable=True)  # e.g., "1920x1080"
    
    # Stats
    views_count = db.Column(db.Integer, default=0, nullable=False)
    likes_count = db.Column(db.Integer, default=0, nullable=False)
    shares_count = db.Column(db.Integer, default=0, nullable=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    # Note: approval_status kept for backward compatibility but defaults to 'approved'
    # Reels don't require approval - they are active immediately
    approval_status = db.Column(db.String(20), default='approved', nullable=False, index=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)
    
    # Timestamps (inherited from BaseModel, but we'll override for consistency)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    merchant = db.relationship('MerchantProfile', backref=db.backref('reels', lazy='dynamic'))
    product = db.relationship('Product', backref=db.backref('reels', lazy='dynamic'))
    approved_by_admin = db.relationship('User', backref=db.backref('approved_reels', lazy='dynamic'), foreign_keys=[approved_by])
    
    # Disabling reasons constants
    DISABLING_REASONS = {
        'PRODUCT_OUT_OF_STOCK': 'Product stock quantity is 0',
        'PRODUCT_DELETED': 'Product has been deleted',
        'PRODUCT_NOT_APPROVED': 'Product is not approved by admin',
        'PRODUCT_REJECTED': 'Product has been rejected',
        'PRODUCT_PENDING_APPROVAL': 'Product is pending approval',
        'PRODUCT_INACTIVE': 'Product is inactive',
        'PRODUCT_MERCHANT_MISMATCH': 'Product does not belong to merchant',
        'REEL_DELETED': 'Reel has been deleted',
        'REEL_INACTIVE': 'Reel is inactive',
        'PRODUCT_NOT_FOUND': 'Product not found'
    }
    
    @property
    def is_visible(self):
        """Check if reel should be visible (no disabling reasons)."""
        return len(self.get_disabling_reasons()) == 0
    
    def get_disabling_reasons(self):
        """
        Get array of reasons why reel is disabled.
        Returns empty array if reel is visible.
        
        Returns:
            list: Array of reason codes (strings)
        """
        reasons = []
        
        # Check reel status
        if self.deleted_at is not None:
            reasons.append('REEL_DELETED')
        
        if not self.is_active:
            reasons.append('REEL_INACTIVE')
        
        # Note: Reels don't require approval, so we don't check approval_status
        
        # Check product (product_id is required, so product should exist)
        if not self.product:
            reasons.append('PRODUCT_NOT_FOUND')
            return reasons  # Can't check further if product doesn't exist
        
        # Check product status
        if self.product.deleted_at is not None:
            reasons.append('PRODUCT_DELETED')
        
        if not self.product.active_flag:
            reasons.append('PRODUCT_INACTIVE')
        
        if self.product.approval_status == 'pending':
            reasons.append('PRODUCT_PENDING_APPROVAL')
        elif self.product.approval_status == 'rejected':
            reasons.append('PRODUCT_REJECTED')
        elif self.product.approval_status != 'approved':
            reasons.append('PRODUCT_NOT_APPROVED')
        
        # Check merchant ownership
        if self.product.merchant_id != self.merchant_id:
            reasons.append('PRODUCT_MERCHANT_MISMATCH')
        
        # Check stock
        stock_qty = self.product.stock.stock_qty if self.product.stock else 0
        if stock_qty <= 0:
            reasons.append('PRODUCT_OUT_OF_STOCK')
        
        return reasons
    
    def serialize(self, include_reasons=True, include_product=True, include_merchant=False, fields=None):
        """
        Serialize reel with disabling reasons.
        
        Args:
            include_reasons: Whether to include disabling_reasons array
            include_product: Whether to include product info
            include_merchant: Whether to include merchant info
            fields: Optional list of field names to include (if None, includes all)
            
        Returns:
            dict: Serialized reel data
        """
        # Define all available fields
        all_data = {
            'reel_id': self.reel_id,
            'merchant_id': self.merchant_id,
            'product_id': self.product_id,
            'video_url': self.video_url,
            'thumbnail_url': self.thumbnail_url,
            'description': self.description,
            'duration_seconds': self.duration_seconds,
            'file_size_bytes': self.file_size_bytes,
            'video_format': self.video_format,
            'resolution': self.resolution,
            'views_count': self.views_count,
            'likes_count': self.likes_count,
            'shares_count': self.shares_count,
            'is_active': self.is_active,
            'approval_status': self.approval_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        # Include disabling reasons if requested
        if include_reasons:
            disabling_reasons = self.get_disabling_reasons()
            all_data['disabling_reasons'] = disabling_reasons
            all_data['is_visible'] = len(disabling_reasons) == 0
        
        # Include product info
        if include_product and self.product:
            all_data['product'] = {
                'product_id': self.product.product_id,
                'product_name': self.product.product_name,
                'category_id': self.product.category_id,
                'category_name': self.product.category.name if self.product.category else None,
                'stock_qty': self.product.stock.stock_qty if self.product.stock else 0,
                'selling_price': float(self.product.selling_price) if self.product.selling_price else None,
            }
        
        # Include merchant info
        if include_merchant and self.merchant:
            all_data['merchant'] = {
                'merchant_id': self.merchant.id,
                'business_name': self.merchant.business_name,
            }
        
        # Filter by fields if specified
        if fields:
            # Validate fields
            valid_fields = set(all_data.keys())
            requested_fields = set(fields)
            invalid_fields = requested_fields - valid_fields
            
            if invalid_fields:
                # Log warning but continue with valid fields
                from flask import current_app
                if current_app:
                    current_app.logger.warning(f"Invalid fields requested: {invalid_fields}")
            
            # Filter data to only include requested valid fields
            data = {k: v for k, v in all_data.items() if k in requested_fields and k in valid_fields}
        else:
            data = all_data
        
        return data
    
    def increment_views(self):
        """Increment views count."""
        self.views_count += 1
        db.session.commit()
    
    def increment_likes(self):
        """Increment likes count."""
        self.likes_count += 1
        db.session.commit()
    
    def decrement_likes(self):
        """Decrement likes count."""
        if self.likes_count > 0:
            self.likes_count -= 1
            db.session.commit()
    
    def increment_shares(self):
        """Increment shares count."""
        self.shares_count += 1
        db.session.commit()
    
    @classmethod
    def get_visible_reels(cls, query=None):
        """
        Get query for visible reels only.
        
        Args:
            query: Optional base query to filter
            
        Returns:
            Query: Filtered query with only visible reels
        """
        if query is None:
            query = cls.query
        
        # Filter out deleted reels
        query = query.filter(cls.deleted_at.is_(None))
        
        # Filter active reels
        query = query.filter(cls.is_active == True)
        
        # Note: Reels don't require approval, so we don't filter by approval_status
        
        # Filter products that are not deleted, active, and approved
        from models.product import Product
        query = query.join(Product).filter(
            Product.deleted_at.is_(None),
            Product.active_flag == True,
            Product.approval_status == 'approved'
        )
        
        # Filter products with stock > 0
        query = query.join(ProductStock, Product.product_id == ProductStock.product_id).filter(
            ProductStock.stock_qty > 0
        )
        
        return query

