# controllers/merchant/product_controller.py

from flask_jwt_extended import get_jwt_identity
from flask import abort
from common.database import db
from models.product import Product
from auth.models.models import MerchantProfile
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

class MerchantProductController:
    @staticmethod
    def list_all():
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")
        return Product.query.filter_by(
            merchant_id=merchant.id,
            deleted_at=None
        ).all()

    @staticmethod
    def get(pid):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")
        return Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

    @staticmethod
    def create(data):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        # selling_price and special_price from data are GST-inclusive
        p = Product(
            merchant_id=merchant.id,
            category_id=data['category_id'],
            brand_id=data['brand_id'],
            sku=data['sku'],
            product_name=data['product_name'],
            product_description=data['product_description'],
            cost_price=data['cost_price'], 
            selling_price=Decimal(data['selling_price']), # GST-inclusive
            discount_pct=data.get('discount_pct', Decimal('0.00')), 
            special_price=Decimal(data['special_price']) if data.get('special_price') is not None else None, # GST-inclusive
            special_start=data.get('special_start'),
            special_end=data.get('special_end'),
            approval_status='pending'
        )
        # NO call to p.update_base_price_and_gst_details() here
        db.session.add(p)
        db.session.commit()
        return p

    @staticmethod
    def update(pid, data):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        p = Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

        # If product is approved, changing certain fields will require re-approval
        if p.approval_status == 'approved':
            fields_requiring_reapproval = {
                'product_name', 'product_description', 'cost_price', 
                'selling_price', 'special_price', 'special_start', 'special_end'
            }
            if any(field in data for field in fields_requiring_reapproval):
                p.approval_status = 'pending'
                p.approved_at = None
                p.approved_by = None
                p.rejection_reason = None

        update_fields = [
            'category_id','brand_id','sku','product_name','product_description',
            'cost_price','selling_price','discount_pct','special_price',
            'special_start','special_end','active_flag'
        ]
        for field in update_fields:
            if field in data:
                value_to_set = data[field]
                if field in ['selling_price', 'special_price', 'cost_price', 'discount_pct']:
                    value_to_set = Decimal(value_to_set) if value_to_set is not None else None
                setattr(p, field, value_to_set)
        
        db.session.commit()
        return p

    @staticmethod
    def delete(pid):
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        p = Product.query.filter_by(
            product_id=pid,
            merchant_id=merchant.id
        ).first_or_404()

        p.deleted_at = db.func.current_timestamp()
        db.session.commit()
        return p

    @staticmethod
    def approve(pid, admin_id):
        """Approve a product by superadmin."""
        p = Product.query.get_or_404(pid)
        p.approval_status = 'approved'
        p.approved_at = datetime.now(timezone.utc)
        p.approved_by = admin_id
        p.rejection_reason = None
        db.session.commit()
        return p

    @staticmethod
    def reject(pid, admin_id, reason):
        """Reject a product by superadmin."""
        p = Product.query.get_or_404(pid)
        p.approval_status = 'rejected'
        p.approved_at = None
        p.approved_by = None
        p.rejection_reason = reason
        db.session.commit()
        return p

    @staticmethod
    def get_pending_products():
        """Get all products pending approval."""
        return Product.query.filter_by(
            approval_status='pending',
            deleted_at=None
        ).all()

    @staticmethod
    def get_approved_products():
        """Get all approved products."""
        return Product.query.filter_by(
            approval_status='approved',
            deleted_at=None
        ).all()

    @staticmethod
    def get_rejected_products():
        """Get all rejected products."""
        return Product.query.filter_by(
            approval_status='rejected',
            deleted_at=None
        ).all()

    @staticmethod
    def create_variant(parent_id, data):
        """
        Create a variant product from a parent product.
        Required fields in data:
        - sku: unique SKU for the variant
        - stock_qty: initial stock quantity
        - selling_price: variant's selling price
        Optional fields:
        - cost_price: variant's cost price (defaults to parent's cost_price)
        - attributes: dictionary of attribute values
        """
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        # Get parent product
        parent_product = Product.query.filter_by(
            product_id=parent_id,
            merchant_id=merchant.id,
            deleted_at=None
        ).first_or_404()

        # Get parent's stock info for low stock threshold
        parent_stock = parent_product.stock
        if not parent_stock:
            abort(400, "Parent product stock information not found")

        # Check if SKU is unique
        if Product.query.filter_by(sku=data['sku']).first():
            abort(400, "SKU already exists")

        try:
            # Start a transaction
            db.session.begin_nested()

            # Create variant product inheriting most fields from parent
            variant = Product(
                merchant_id=merchant.id,
                category_id=parent_product.category_id,
                brand_id=parent_product.brand_id,
                parent_product_id=parent_id,
                sku=data['sku'],
                product_name=parent_product.product_name,
                product_description=parent_product.product_description,
                cost_price=data.get('cost_price', parent_product.cost_price),
                selling_price=data['selling_price'],
                discount_pct=parent_product.discount_pct,
                special_price=parent_product.special_price,
                special_start=parent_product.special_start,
                special_end=parent_product.special_end,
                active_flag=parent_product.active_flag,
                approval_status='pending'  # Variants need approval like new products
            )

            # Save the variant to get its ID
            db.session.add(variant)
            db.session.flush()

            # Create product stock record
            from models.product_stock import ProductStock
            stock = ProductStock(
                product_id=variant.product_id,
                stock_qty=data['stock_qty'],
                low_stock_threshold=parent_stock.low_stock_threshold  # Use parent's threshold
            )
            db.session.add(stock)

            # Copy product meta from parent product
            if parent_product.meta:
                from models.product_meta import ProductMeta
                variant_meta = ProductMeta(
                    product_id=variant.product_id,
                    short_desc=parent_product.meta.short_desc,
                    full_desc=parent_product.meta.full_desc,
                    meta_title=parent_product.meta.meta_title,
                    meta_desc=parent_product.meta.meta_desc,
                    meta_keywords=parent_product.meta.meta_keywords
                )
                db.session.add(variant_meta)

            # Copy product shipping from parent product
            if parent_product.shipping:
                from models.product_shipping import ProductShipping
                variant_shipping = ProductShipping(
                    product_id=variant.product_id,
                    length_cm=parent_product.shipping.length_cm,
                    width_cm=parent_product.shipping.width_cm,
                    height_cm=parent_product.shipping.height_cm,
                    weight_kg=parent_product.shipping.weight_kg
                )
                db.session.add(variant_shipping)

            # Handle attributes if provided
            if 'attributes' in data and isinstance(data['attributes'], dict):
                from models.product_attribute import ProductAttribute
                from models.attribute import Attribute

                for attr_id, attr_value in data['attributes'].items():
                    # Get the attribute
                    attribute = Attribute.query.get(attr_id)
                    if not attribute:
                        continue

                    # Create product attribute
                    product_attr = ProductAttribute(
                        product_id=variant.product_id,
                        attribute_id=attribute.attribute_id
                    )

                    # Set the appropriate value based on attribute type
                    if attribute.input_type in ['select', 'multiselect']:
                        product_attr.value_code = str(attr_value)
                    elif attribute.input_type == 'number':
                        product_attr.value_number = float(attr_value)
                    else:  # text or other types
                        product_attr.value_text = str(attr_value)

                    db.session.add(product_attr)

            # Commit the transaction
            db.session.commit()
            return variant

        except Exception as e:
            db.session.rollback()
            abort(500, f"Failed to create variant: {str(e)}")

    @staticmethod
    def find_size_attribute(category_id):
        """
        Find the Size attribute for a given category.
        Returns attribute_id if found, None otherwise.
        """
        from models.category_attribute import CategoryAttribute
        from models.attribute import Attribute
        from sqlalchemy import func

        try:
            # Query for Size attribute (case-insensitive)
            size_attr = db.session.query(Attribute).join(
                CategoryAttribute,
                Attribute.attribute_id == CategoryAttribute.attribute_id
            ).filter(
                CategoryAttribute.category_id == category_id,
                func.lower(Attribute.name) == 'size'
            ).first()

            return size_attr.attribute_id if size_attr else None
        except Exception as e:
            return None

    @staticmethod
    def bulk_create_size_variants(parent_id, size_quantities, low_stock_threshold=None):
        """
        Bulk create size-based variants for a parent product.
        
        Args:
            parent_id: ID of the parent product
            size_quantities: List of dicts with 'size' and 'quantity' keys
            low_stock_threshold: Optional low stock threshold (defaults to parent's)
        
        Returns:
            dict with message and list of created variants
        """
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id)
        if not merchant:
            abort(404, "Merchant profile not found")

        # Get parent product
        parent_product = Product.query.filter_by(
            product_id=parent_id,
            merchant_id=merchant.id,
            deleted_at=None
        ).first_or_404()

        # Check if variants already exist
        existing_variants = Product.query.filter_by(
            parent_product_id=parent_id,
            deleted_at=None
        ).all()

        if existing_variants:
            abort(400, "Product already has variants. Cannot use size-quantity bulk creation.")

        # Find Size attribute for the category
        size_attribute_id = MerchantProductController.find_size_attribute(parent_product.category_id)
        if not size_attribute_id:
            abort(404, "Size attribute not found for this category. Please contact admin to set it up.")

        # Get parent's stock info for low stock threshold
        parent_stock = parent_product.stock
        if not parent_stock:
            abort(400, "Parent product stock information not found")

        threshold = low_stock_threshold if low_stock_threshold is not None else parent_stock.low_stock_threshold

        created_variants = []
        
        try:
            from models.product_stock import ProductStock
            from models.product_attribute import ProductAttribute
            from models.product_meta import ProductMeta
            from models.product_shipping import ProductShipping
            from models.attribute import Attribute

            # Get the Size attribute object
            size_attribute = Attribute.query.get(size_attribute_id)
            if not size_attribute:
                abort(404, "Size attribute not found")

            for sq in size_quantities:
                size_value = sq['size'].strip()
                quantity = int(sq['quantity'])

                # Generate SKU for variant
                size_code = size_value.upper().replace(' ', '').replace('-', '')[:3]
                variant_sku = f"{parent_product.sku}-{size_code}"

                # Check if SKU already exists
                existing_sku = Product.query.filter_by(sku=variant_sku).first()
                if existing_sku:
                    # Add timestamp to make it unique
                    variant_sku = f"{variant_sku}-{int(datetime.now(timezone.utc).timestamp()) % 10000}"

                # Create variant product inheriting most fields from parent
                variant = Product(
                    merchant_id=merchant.id,
                    category_id=parent_product.category_id,
                    brand_id=parent_product.brand_id,
                    parent_product_id=parent_id,
                    sku=variant_sku,
                    product_name=parent_product.product_name,
                    product_description=parent_product.product_description,
                    cost_price=parent_product.cost_price,
                    selling_price=parent_product.selling_price,
                    discount_pct=parent_product.discount_pct,
                    special_price=parent_product.special_price,
                    special_start=parent_product.special_start,
                    special_end=parent_product.special_end,
                    active_flag=parent_product.active_flag,
                    approval_status='pending'  # Variants need approval like new products
                )

                # Save the variant to get its ID
                db.session.add(variant)
                db.session.flush()

                # Create product stock record
                stock = ProductStock(
                    product_id=variant.product_id,
                    stock_qty=quantity,
                    low_stock_threshold=threshold
                )
                db.session.add(stock)

                # Copy product meta from parent product
                if parent_product.meta:
                    variant_meta = ProductMeta(
                        product_id=variant.product_id,
                        short_desc=parent_product.meta.short_desc,
                        full_desc=parent_product.meta.full_desc,
                        meta_title=parent_product.meta.meta_title,
                        meta_desc=parent_product.meta.meta_desc,
                        meta_keywords=parent_product.meta.meta_keywords
                    )
                    db.session.add(variant_meta)

                # Copy product shipping from parent product
                if parent_product.shipping:
                    variant_shipping = ProductShipping(
                        product_id=variant.product_id,
                        length_cm=parent_product.shipping.length_cm,
                        width_cm=parent_product.shipping.width_cm,
                        height_cm=parent_product.shipping.height_cm,
                        weight_kg=parent_product.shipping.weight_kg
                    )
                    db.session.add(variant_shipping)

                # Create Size attribute for variant
                product_attr = ProductAttribute(
                    product_id=variant.product_id,
                    attribute_id=size_attribute_id
                )

                # Set the appropriate value based on attribute type
                if size_attribute.input_type in ['select', 'multiselect']:
                    # Try to find matching AttributeValue first
                    from models.attribute_value import AttributeValue
                    attr_value = AttributeValue.query.filter_by(
                        attribute_id=size_attribute_id
                    ).filter(
                        db.or_(
                            AttributeValue.value_label.ilike(size_value),
                            AttributeValue.value_code.ilike(size_value)
                        )
                    ).first()
                    
                    if attr_value:
                        product_attr.value_code = attr_value.value_code
                    else:
                        # Fallback to value_text if no predefined value found
                        product_attr.value_text = size_value
                elif size_attribute.input_type == 'number':
                    try:
                        product_attr.value_number = float(size_value)
                    except ValueError:
                        product_attr.value_text = size_value
                else:  # text or other types
                    product_attr.value_text = size_value

                db.session.add(product_attr)

                created_variants.append(variant.serialize())

            db.session.commit()

            return {
                'message': f'Successfully created {len(created_variants)} size variants',
                'variants': created_variants
            }

        except Exception as e:
            db.session.rollback()
            abort(500, f"Failed to create size variants: {str(e)}")
