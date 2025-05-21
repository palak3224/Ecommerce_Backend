from models.product_attribute import ProductAttribute
from models.attribute import Attribute
from models.attribute_value import AttributeValue
from common.database import db
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import IntegrityError


class MerchantProductAttributeController:
    @staticmethod
    def list(pid):
        """Get all attributes for a product with their values"""
        attributes = ProductAttribute.query.filter_by(product_id=pid).all()
        return attributes

    @staticmethod
    def create(pid, data):
        """Create a new product attribute with single or multiple values"""
        try:
            # Validate attribute exists
            attribute = Attribute.query.get_or_404(data['attribute_id'])
            
            # Handle multiple values for multiselect type
            if attribute.input_type == 'multiselect' and isinstance(data.get('value_code'), list):
                product_attributes = []
                for value_code in data['value_code']:
                    # Validate value exists
                    AttributeValue.query.get_or_404((attribute.attribute_id, value_code))
                    
                    pa = ProductAttribute(
                        product_id=pid,
                        attribute_id=attribute.attribute_id,
                        value_code=value_code,
                        value_text=data.get('value_text')
                    )
                    product_attributes.append(pa)
                
                db.session.add_all(product_attributes)
                db.session.commit()
                return product_attributes
            else:
                # Handle single value
                if data.get('value_code'):
                    # Validate value exists for select/multiselect
                    AttributeValue.query.get_or_404((attribute.attribute_id, data['value_code']))
                
                pa = ProductAttribute(
                    product_id=pid,
                    attribute_id=attribute.attribute_id,
                    value_code=data.get('value_code'),
                    value_text=data.get('value_text')
                )
                db.session.add(pa)
                db.session.commit()
                return pa
                
        except IntegrityError as e:
            db.session.rollback()
            raise ValueError(f"Failed to create product attribute: {str(e)}")

    @staticmethod
    def update(pid, aid, code, data):
        """Update a product attribute value"""
        try:
            pa = ProductAttribute.query.get_or_404((pid, aid, code))
            
            # If updating value_code, validate it exists
            if 'value_code' in data:
                attribute = Attribute.query.get_or_404(aid)
                if attribute.input_type in ['select', 'multiselect']:
                    AttributeValue.query.get_or_404((aid, data['value_code']))
                pa.value_code = data['value_code']
            
            if 'value_text' in data:
                pa.value_text = data['value_text']
                
            db.session.commit()
            return pa
            
        except IntegrityError as e:
            db.session.rollback()
            raise ValueError(f"Failed to update product attribute: {str(e)}")

    @staticmethod
    def delete(pid, aid, code):
        """Delete a product attribute value"""
        try:
            pa = ProductAttribute.query.get_or_404((pid, aid, code))
            db.session.delete(pa)
            db.session.commit()
            return True
        except IntegrityError as e:
            db.session.rollback()
            raise ValueError(f"Failed to delete product attribute: {str(e)}")

    @staticmethod
    def delete_all_for_product(pid):
        """Delete all attributes for a product"""
        try:
            ProductAttribute.query.filter_by(product_id=pid).delete()
            db.session.commit()
            return True
        except IntegrityError as e:
            db.session.rollback()
            raise ValueError(f"Failed to delete product attributes: {str(e)}")

    @staticmethod
    def bulk_create(pid, attributes_data):
        """Create multiple product attributes at once"""
        try:
            product_attributes = []
            
            for data in attributes_data:
                attribute = Attribute.query.get_or_404(data['attribute_id'])
                
                if attribute.input_type == 'multiselect' and isinstance(data.get('value_code'), list):
                    for value_code in data['value_code']:
                        AttributeValue.query.get_or_404((attribute.attribute_id, value_code))
                        pa = ProductAttribute(
                            product_id=pid,
                            attribute_id=attribute.attribute_id,
                            value_code=value_code,
                            value_text=data.get('value_text')
                        )
                        product_attributes.append(pa)
                else:
                    if data.get('value_code'):
                        AttributeValue.query.get_or_404((attribute.attribute_id, data['value_code']))
                    pa = ProductAttribute(
                        product_id=pid,
                        attribute_id=attribute.attribute_id,
                        value_code=data.get('value_code'),
                        value_text=data.get('value_text')
                    )
                    product_attributes.append(pa)
            
            db.session.add_all(product_attributes)
            db.session.commit()
            return product_attributes
            
        except IntegrityError as e:
            db.session.rollback()
            raise ValueError(f"Failed to create product attributes: {str(e)}")

    @staticmethod
    def upsert(pid, attribute_id, value):
        """Create or update a product attribute value"""
        try:
            # Validate attribute exists
            attribute = Attribute.query.get_or_404(attribute_id)
            
            # For select/multiselect types, validate the value exists
            if attribute.input_type in ['select', 'multiselect']:
                if not value:
                    raise ValueError(f"Value is required for attribute type {attribute.input_type}")
                # Get the attribute value to ensure it exists
                attribute_value = AttributeValue.query.get_or_404((attribute_id, value))
                value_code = attribute_value.value_code
            else:
                # For text/number types, use the value as is
                value_code = value
            
            # Check if attribute value already exists
            existing = ProductAttribute.query.filter_by(
                product_id=pid,
                attribute_id=attribute_id
            ).first()

            if existing:
                # Update existing value
                if attribute.input_type in ['select', 'multiselect']:
                    existing.value_code = value_code
                    existing.value_text = None
                else:
                    existing.value_text = value
                    existing.value_code = value_code
            else:
                # Create new value
                new_attr = ProductAttribute(
                    product_id=pid,
                    attribute_id=attribute_id,
                    value_code=value_code,
                    value_text=value if attribute.input_type not in ['select', 'multiselect'] else None
                )
                db.session.add(new_attr)

            db.session.commit()
            return True

        except IntegrityError as e:
            db.session.rollback()
            raise ValueError(f"Failed to upsert product attribute: {str(e)}")
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error upserting product attribute: {str(e)}")
