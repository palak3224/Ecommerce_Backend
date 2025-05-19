# routes/merchant_routes.py
from flask import Blueprint, request, jsonify, current_app
from http import HTTPStatus
from auth.utils import merchant_role_required
from common.database import db
import cloudinary
import cloudinary.uploader
from controllers.merchant.brand_request_controller import MerchantBrandRequestController
from controllers.merchant.brand_controller         import MerchantBrandController
from controllers.merchant.category_controller      import MerchantCategoryController
from controllers.merchant.product_controller       import MerchantProductController
from controllers.merchant.product_meta_controller  import MerchantProductMetaController
from controllers.merchant.product_tax_controller   import MerchantProductTaxController
from controllers.merchant.product_shipping_controller import MerchantProductShippingController
from controllers.merchant.product_media_controller import MerchantProductMediaController
from controllers.merchant.variant_controller       import MerchantVariantController
from controllers.merchant.variant_stock_controller import MerchantVariantStockController
from controllers.merchant.product_attribute_controller import MerchantProductAttributeController

ALLOWED_MEDIA_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'avi'} 

def allowed_media_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_MEDIA_EXTENSIONS



merchant_dashboard_bp = Blueprint('merchant_dashboard_bp', __name__)

# ── BRAND REQUESTS ───────────────────────────────────────────────────────────────
@merchant_dashboard_bp.route('/brand-requests', methods=['GET'])
@merchant_role_required
def list_brand_requests():
    items = MerchantBrandRequestController.list_all()
    return jsonify([i.serialize() for i in items]), 200

@merchant_dashboard_bp.route('/brand-requests', methods=['POST'])
@merchant_role_required
def create_brand_request():
    data = request.get_json()
    br = MerchantBrandRequestController.create(data)
    return jsonify(br.serialize()), 201

# ── BRANDS ────────────────────────────────────────────────────────────────────────
@merchant_dashboard_bp.route('/brands', methods=['GET'])
@merchant_role_required
def list_brands():
    items = MerchantBrandController.list_all()
    return jsonify([i.serialize() for i in items]), 200

# ── CATEGORIES ───────────────────────────────────────────────────────────────────

@merchant_dashboard_bp.route('/categories', methods=['GET'])
@merchant_role_required
def list_merchant_categories():
    try:
        cats = MerchantCategoryController.list_all()
       
        return jsonify([c.serialize() for c in cats]), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Merchant: Error listing categories: {e}")
        return jsonify({'message': 'Failed to retrieve categories.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@merchant_dashboard_bp.route('/categories/<int:cid>/attributes', methods=['GET'])
@merchant_role_required
def list_attributes_for_merchant_category_view(cid):
    """
    Allows a merchant to view attributes associated with a specific category.
    """
    try:
       
        attributes_data = MerchantCategoryController.list_attributes_for_category(cid)
        return jsonify(attributes_data), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Merchant: Error fetching attributes for category {cid}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int): 
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': 'An error occurred while retrieving category attributes.'}), HTTPStatus.INTERNAL_SERVER_ERROR


# ── PRODUCTS ─────────────────────────────────────────────────────────────────────
@merchant_dashboard_bp.route('/products', methods=['GET'])
@merchant_role_required
def list_products():
    ps = MerchantProductController.list_all()
    return jsonify([p.serialize() for p in ps]), 200

@merchant_dashboard_bp.route('/products', methods=['POST'])
@merchant_role_required
def create_product():
    data = request.get_json()
    p = MerchantProductController.create(data)
    return jsonify(p.serialize()), 201

@merchant_dashboard_bp.route('/products/<int:pid>', methods=['GET'])
@merchant_role_required
def get_product(pid):
    p = MerchantProductController.get(pid)
    return jsonify(p.serialize()), 200

@merchant_dashboard_bp.route('/products/<int:pid>', methods=['PUT'])
@merchant_role_required
def update_product(pid):
    data = request.get_json()
    p = MerchantProductController.update(pid, data)
    return jsonify(p.serialize()), 200

@merchant_dashboard_bp.route('/products/<int:pid>', methods=['DELETE'])
@merchant_role_required
def delete_product(pid):
    p = MerchantProductController.delete(pid)
    return jsonify(p.serialize()), 200



# PRODUCT META
@merchant_dashboard_bp.route('/products/<int:pid>/meta', methods=['GET'])
@merchant_role_required
def get_product_meta(pid):
    pm = MerchantProductMetaController.get(pid)
    return jsonify(pm.serialize()), 200

@merchant_dashboard_bp.route('/products/<int:pid>/meta', methods=['POST','PUT'])
@merchant_role_required
def upsert_product_meta(pid):
    data = request.get_json()
    pm = MerchantProductMetaController.upsert(pid, data)
    return jsonify(pm.serialize()), 200

# PRODUCT TAX
@merchant_dashboard_bp.route('/products/<int:pid>/tax', methods=['GET'])
@merchant_role_required
def get_product_tax(pid):
    t = MerchantProductTaxController.get(pid)
    return jsonify({'product_id': t.product_id, 'tax_rate': str(t.tax_rate)}), 200

@merchant_dashboard_bp.route('/products/<int:pid>/tax', methods=['POST','PUT'])
@merchant_role_required
def upsert_product_tax(pid):
    data = request.get_json()
    t = MerchantProductTaxController.upsert(pid, data)
    return jsonify({'product_id': t.product_id, 'tax_rate': str(t.tax_rate)}), 200

# PRODUCT SHIPPING
@merchant_dashboard_bp.route('/products/<int:pid>/shipping', methods=['GET'])
@merchant_role_required
def get_product_shipping(pid):
    s = MerchantProductShippingController.get(pid)
    return jsonify(s.serialize()), 200

@merchant_dashboard_bp.route('/products/<int:pid>/shipping', methods=['POST','PUT'])
@merchant_role_required
def upsert_product_shipping(pid):
    data = request.get_json()
    s = MerchantProductShippingController.upsert(pid, data)
    return jsonify(s.serialize()), 200

# PRODUCT MEDIA
@merchant_dashboard_bp.route('/products/<int:pid>/media', methods=['GET'])
@merchant_role_required
def list_product_media(pid):
    try:
        m = MerchantProductMediaController.list(pid)
        return jsonify([x.serialize() for x in m]), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Merchant: Error listing media for product {pid}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to retrieve product media."}), HTTPStatus.INTERNAL_SERVER_ERROR


@merchant_dashboard_bp.route('/products/<int:pid>/media', methods=['POST'])
@merchant_role_required
def create_product_media(pid):
   
    
    if 'media_file' not in request.files:
        return jsonify({'message': 'No media file part in the request'}), HTTPStatus.BAD_REQUEST
    
    file = request.files['media_file']

    if file.filename == '':
        return jsonify({'message': 'No selected file'}), HTTPStatus.BAD_REQUEST

    
    if not allowed_media_file(file.filename):
        return jsonify({'message': f"Invalid file type. Allowed types: {', '.join(ALLOWED_MEDIA_EXTENSIONS)}"}), HTTPStatus.BAD_REQUEST

  
    file_mimetype = file.mimetype.lower()
    media_type_str = "IMAGE" 
    if file_mimetype.startswith('video/'):
        media_type_str = "VIDEO"
    elif not file_mimetype.startswith('image/'):
       
        return jsonify({'message': f"Unsupported file content type: {file.mimetype}"}), HTTPStatus.BAD_REQUEST

   
    media_type_from_form = request.form.get('type', media_type_str).upper()


    sort_order_str = request.form.get('sort_order', '0')
    try:
        sort_order = int(sort_order_str)
    except ValueError:
        return jsonify({'message': 'Invalid sort_order format, must be an integer.'}), HTTPStatus.BAD_REQUEST
    
   
   
    cloudinary_url = None
    cloudinary_public_id = None 
    resource_type_for_cloudinary = "image" if media_type_from_form == "IMAGE" else "video"

    try:
        
        upload_result = cloudinary.uploader.upload(
            file,
            folder=f"product_media/{pid}",  
            resource_type=resource_type_for_cloudinary
        )
        cloudinary_url = upload_result.get('secure_url')
        cloudinary_public_id = upload_result.get('public_id') 

        if not cloudinary_url:
            current_app.logger.error("Cloudinary upload for product media succeeded but no secure_url was returned.")
            return jsonify({'message': 'Cloudinary upload succeeded but did not return a URL.'}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    except cloudinary.exceptions.Error as e:
        current_app.logger.error(f"Cloudinary upload failed for product media (product {pid}): {e}")
        return jsonify({'message': f"Cloudinary media upload failed: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
    except Exception as e:
        current_app.logger.error(f"Error during product media file upload (product {pid}): {e}")
        return jsonify({'message': f"An error occurred during media file upload: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR

   
    media_data = {
        'url': cloudinary_url,
        'type': media_type_from_form, 
        'sort_order': sort_order,
       
    }

   
    try:
       
        new_media = MerchantProductMediaController.create(pid, media_data)
        return jsonify(new_media.serialize()), HTTPStatus.CREATED
    except ValueError as e: 
        return jsonify({'message': str(e)}), HTTPStatus.BAD_REQUEST
    except RuntimeError as e: 
        return jsonify({'message': str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR
    except Exception as e:
        db.session.rollback() 
        current_app.logger.error(f"Error saving product media to DB for product {pid}: {e}")
       
        return jsonify({'message': 'Failed to save product media information.'}), HTTPStatus.INTERNAL_SERVER_ERROR


@merchant_dashboard_bp.route('/products/media/<int:mid>', methods=['DELETE'])
@merchant_role_required
def delete_product_media(mid):
    try:
       
        m = MerchantProductMediaController.delete(mid)
        return jsonify(m.serialize()), HTTPStatus.OK 
    except Exception as e:
      
        current_app.logger.error(f"Merchant: Error deleting media {mid}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': "Failed to delete product media."}), HTTPStatus.INTERNAL_SERVER_ERROR

# VARIANTS
@merchant_dashboard_bp.route('/products/<int:pid>/variants', methods=['GET'])
@merchant_role_required
def list_variants(pid):
    vs = MerchantVariantController.list(pid)
    return jsonify([v.serialize() for v in vs]), HTTPStatus.OK 

@merchant_dashboard_bp.route('/products/<int:pid>/variants', methods=['POST'])
@merchant_role_required
def create_variant(pid):
    data = request.get_json()
    if not data: 
        return jsonify({"message": "Request body cannot be empty."}), HTTPStatus.BAD_REQUEST
    try:
        v = MerchantVariantController.create(pid, data)
        return jsonify(v.serialize()), HTTPStatus.CREATED 
    except ValueError as e: 
        return jsonify({"message": str(e)}), HTTPStatus.BAD_REQUEST
    except Exception as e: 
        
        return jsonify({"message": "An error occurred while creating the variant."}), HTTPStatus.INTERNAL_SERVER_ERROR


@merchant_dashboard_bp.route('/products/variants/<int:vid>', methods=['PUT'])
@merchant_role_required
def update_variant(vid):
    data = request.get_json()
    if not data:
        return jsonify({"message": "Request body cannot be empty for update."}), HTTPStatus.BAD_REQUEST
    try:
        v = MerchantVariantController.update(vid, data)
        return jsonify(v.serialize()), HTTPStatus.OK
    except ValueError as e: 
        return jsonify({"message": str(e)}), HTTPStatus.BAD_REQUEST
    except Exception as e:
        if hasattr(e, 'code') and e.code == 404: 
            return jsonify({"message": getattr(e, 'description', "Variant not found.")}), HTTPStatus.NOT_FOUND
        current_app.logger.error(f"Error updating variant {vid}: {e}")
        return jsonify({"message": "An error occurred while updating the variant."}), HTTPStatus.INTERNAL_SERVER_ERROR

@merchant_dashboard_bp.route('/products/variants/<int:vid>', methods=['DELETE'])
@merchant_role_required
def delete_variant(vid):
    try:
        v = MerchantVariantController.delete(vid)
        return jsonify(v.serialize()), HTTPStatus.OK 
    except Exception as e: 
        if hasattr(e, 'code') and e.code == 404:
            return jsonify({"message": getattr(e, 'description', "Variant not found.")}), HTTPStatus.NOT_FOUND
        return jsonify({"message": "An error occurred while deleting the variant."}), HTTPStatus.INTERNAL_SERVER_ERROR

# VARIANT STOCK
@merchant_dashboard_bp.route('/products/variants/<int:vid>/stock', methods=['GET'])
@merchant_role_required
def get_variant_stock(vid):
    vs = MerchantVariantStockController.get(vid)
    return jsonify(vs.serialize()), 200

@merchant_dashboard_bp.route('/products/variants/<int:vid>/stock', methods=['POST','PUT'])
@merchant_role_required
def upsert_variant_stock(vid):
    data = request.get_json()
    vs = MerchantVariantStockController.upsert(vid, data)
    return jsonify(vs.serialize()), 200

# PRODUCT ATTRIBUTES
@merchant_dashboard_bp.route('/products/<int:pid>/attributes', methods=['GET'])
@merchant_role_required
def list_product_attributes(pid):
    pas = MerchantProductAttributeController.list(pid)
    return jsonify([p.serialize() for p in pas]), 200

@merchant_dashboard_bp.route('/products/<int:pid>/attributes', methods=['POST'])
@merchant_role_required
def create_product_attribute(pid):
    data = request.get_json()
    pa = MerchantProductAttributeController.create(pid, data)
    return jsonify(pa.serialize()), 201

@merchant_dashboard_bp.route('/products/<int:pid>/attributes/<int:aid>/<value_code>', methods=['PUT'])
@merchant_role_required
def update_product_attribute(pid, aid, value_code):
    data = request.get_json()
    pa = MerchantProductAttributeController.update(pid, aid, value_code, data)
    return jsonify(pa.serialize()), 200

@merchant_dashboard_bp.route('/products/<int:pid>/attributes/<int:aid>/<value_code>', methods=['DELETE'])
@merchant_role_required
def delete_product_attribute(pid, aid, value_code):
    MerchantProductAttributeController.delete(pid, aid, value_code)
    return '', 204
