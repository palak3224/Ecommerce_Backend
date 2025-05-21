from models.attribute import Attribute
from models.attribute_value import AttributeValue
from common.database import db

class MerchantAttributeController:
    @staticmethod
    def get_values(attribute_id: int) -> list[AttributeValue]:
        """
        Get all values for a specific attribute
        
        Args:
            attribute_id (int): The ID of the attribute
            
        Returns:
            list[AttributeValue]: List of attribute values
            
        Raises:
            ValueError: If the attribute doesn't exist
        """
        # First check if the attribute exists
        attribute = Attribute.query.get(attribute_id)
        if not attribute:
            raise ValueError(f"Attribute with ID {attribute_id} not found")
            
        # Get all values for this attribute
        values = AttributeValue.query.filter_by(attribute_id=attribute_id).all()
        return values 