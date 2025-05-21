from datetime import datetime, timezone, timedelta
from common.database import db, BaseModel
from models.enums import PlacementTypeEnum

class ProductPlacement(BaseModel):
    __tablename__ = 'product_placements'

    placement_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False)
    
    placement_type = db.Column(db.Enum(PlacementTypeEnum), nullable=False)
    
  
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default=db.true(), index=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    
   
    added_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
  
    expires_at = db.Column(db.DateTime, nullable=True) 

 

    product = db.relationship('Product', backref=db.backref('placements', lazy='dynamic'))
    merchant = db.relationship('MerchantProfile', back_populates='product_placements')

    __table_args__ = (
       
        db.UniqueConstraint('product_id', 'merchant_id', 'placement_type', name='uq_product_merchant_placement_type_unique'),
        db.Index('idx_placement_display_query', 'placement_type', 'is_active', 'expires_at', 'sort_order'), 
        db.Index('idx_merchant_placement_count', 'merchant_id', 'placement_type') 
    )

    def __repr__(self):
        return f"<ProductPlacement id={self.placement_id} p_id={self.product_id} type='{self.placement_type.value}' active={self.is_active}>"

    def serialize(self):
        product_info = None
        if self.product:
            
            try:
                product_info = self.product.serialize() 
              
            except Exception: 
                product_info = {"product_id": self.product.product_id, "name": getattr(self.product, 'name', None)}
        
        return {
            "placement_id": self.placement_id,
            "product_id": self.product_id,
            "merchant_id": self.merchant_id,
            "placement_type": self.placement_type.value,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "product_details": product_info,
            "created_at": self.created_at.isoformat() if hasattr(self, 'created_at') and self.created_at else None,
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') and self.updated_at else None,
        }

    @classmethod
    def count_placements_by_merchant_and_type(cls, merchant_id, placement_type):
        """Counts all non-hard-deleted placements for a merchant of a specific type."""
        # This count is used to check against the limit (e.g., 10).
        return cls.query.filter(
            cls.merchant_id == merchant_id,
            cls.placement_type == placement_type
        ).count()

    @classmethod
    def get_active_display_placements(cls, placement_type, limit=10):
        """Gets placements to be displayed on the frontend."""
        now_utc = datetime.now(timezone.utc)
        return cls.query.filter(
            cls.placement_type == placement_type,
            cls.is_active == True,
            (cls.expires_at == None) | (cls.expires_at > now_utc)
        ).order_by(cls.sort_order.asc(), cls.added_at.desc()).limit(limit).all()


    @classmethod
    def set_placements_inactive_for_merchant(cls, merchant_id):
        """
        Sets is_active=False and expires_at=now for all currently considered active placements of a merchant.
        Called when merchant's 'can_place_premium' subscription becomes False.
        These records are NOT hard deleted by this method.
        """
        now_utc = datetime.now(timezone.utc)
        
       
        placements_to_deactivate = cls.query.filter(
            cls.merchant_id == merchant_id,
            cls.is_active == True,
            (cls.expires_at == None) | (cls.expires_at > now_utc)
        )
        
        updated_count = 0
        for placement in placements_to_deactivate.all(): 
            placement.is_active = False
            placement.expires_at = now_utc 
            updated_count +=1
        
        return updated_count


    @classmethod
    def reactivate_placements_for_merchant(cls, merchant_id, subscription_duration_days=30, placement_limit_per_type=10):
        """
        Reactivates placements for a merchant whose subscription ('can_place_premium') just became True.
        It targets placements that were previously active for this merchant but became inactive
        (is_active=False OR expires_at is past/set by previous deactivation).
        It reactivates up to the placement_limit_per_type for each placement type.
        """
        now_utc = datetime.now(timezone.utc)
        new_expiry_date = None
        if subscription_duration_days:
            new_expiry_date = now_utc + timedelta(days=subscription_duration_days)

        total_reactivated_count = 0
        
        for p_type_enum_member in PlacementTypeEnum:
            p_type = p_type_enum_member # Get the enum member itself

       
            already_active_count = cls.query.filter(
                cls.merchant_id == merchant_id,
                cls.placement_type == p_type,
                cls.is_active == True,
                (cls.expires_at == None) | (cls.expires_at > now_utc)
            ).count()

            slots_to_fill = placement_limit_per_type - already_active_count
            if slots_to_fill <= 0:
                continue

           
            candidates_for_reactivation = cls.query.filter(
                cls.merchant_id == merchant_id,
                cls.placement_type == p_type,
                (cls.is_active == False) | ( (cls.expires_at != None) & (cls.expires_at <= now_utc) )
            ).order_by(cls.added_at.desc()).limit(slots_to_fill).all() 

            for placement in candidates_for_reactivation:
                placement.is_active = True
                placement.expires_at = new_expiry_date 
                total_reactivated_count += 1
        
        
        return total_reactivated_count