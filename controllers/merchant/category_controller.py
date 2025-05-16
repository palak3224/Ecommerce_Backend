
from flask import current_app 
from models.category import Category
from models.category_attribute import CategoryAttribute 
from models.attribute import Attribute 

class MerchantCategoryController:
    @staticmethod
    def list_all():
        """Lists all active categories available to merchants."""
        try:
           
            return Category.query.filter_by(deleted_at=None).order_by(Category.name).all()
        except Exception as e:
         
            raise


    @staticmethod
    def list_attributes_for_category(category_id):
        """
        Lists attributes (and their required flag) associated with a specific category,
        intended for merchant viewing.
        """
       
        category = Category.query.filter_by(category_id=category_id, deleted_at=None).first_or_404(
            description=f"Category with ID {category_id} not found or is inactive."
        )

       
        associations = CategoryAttribute.query.filter_by(category_id=category.category_id).all()
        
        # 3. Prepare the data for the merchant
        attributes_data = []
        for assoc in associations:
            if assoc.attribute: 
               
                defined_values_data = []
                
                if hasattr(assoc.attribute, 'defined_values') and assoc.attribute.defined_values:
                    for val in assoc.attribute.defined_values:
                        defined_values_data.append({
                            "value_code": val.value_code,
                            "value_label": val.value_label
                        })
                
                attributes_data.append({
                    "attribute_id": assoc.attribute.attribute_id, 
                    "attribute_name": assoc.attribute.name, 
                    "attribute_code": assoc.attribute.code, 
                   
                    "attribute_type": assoc.attribute.input_type.value if hasattr(assoc.attribute.input_type, 'value') else str(assoc.attribute.input_type), 
                    "required_flag": assoc.required_flag,
                    "defined_values": defined_values_data if defined_values_data else None 
                })
        
        return attributes_data