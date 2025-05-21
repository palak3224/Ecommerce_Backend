from models.category_attribute import CategoryAttribute
from models.attribute import Attribute
from models.attribute_value import AttributeValue
from sqlalchemy.exc import SQLAlchemyError

class MerchantCategoryAttributeController:
    @staticmethod
    def get_attributes_for_category(category_id):
        """
        Get all attributes associated with a specific category
        Args:
            category_id (int): The ID of the category to get attributes for
        Returns:
            list: List of attributes with their required status and values
        Raises:
            SQLAlchemyError: If database error occurs
        """
        try:
            # Get attributes with their required status
            attributes = CategoryAttribute.query.filter_by(
                category_id=category_id
            ).join(
                Attribute
            ).add_columns(
                Attribute.attribute_id,
                Attribute.name,
                Attribute.input_type,
                CategoryAttribute.required_flag
            ).all()

            # Get attribute values for each attribute
            result = []
            for attr in attributes:
                # Get values for this attribute
                values = AttributeValue.query.filter_by(
                    attribute_id=attr.attribute_id
                ).all()

                # Convert to the format expected by the frontend
                result.append({
                    'attribute_id': attr.attribute_id,
                    'name': attr.name,
                    'type': attr.input_type.value,  # Convert enum to string
                    'options': [v.value_label for v in values] if values else None,
                    'help_text': None,  # Not currently supported in the model
                    'required': attr.required_flag
                })

            return result

        except SQLAlchemyError as e:
            raise SQLAlchemyError(f"Database error while fetching category attributes: {str(e)}") 