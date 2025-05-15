from flask import Blueprint, request, jsonify, current_app
from auth.utils import super_admin_role_required
from flask_jwt_extended import get_jwt_identity
import cloudinary
import cloudinary.uploader
from common.database import db
from models.brand import Brand
from sqlalchemy.exc import IntegrityError
from http import HTTPStatus
from datetime import datetime, timezone 
import re

from controllers.superadmin.category_controller import CategoryController
from controllers.superadmin.attribute_controller import AttributeController
from controllers.superadmin.brand_controller import BrandController
from controllers.superadmin.brand_request_controller import BrandRequestController
from controllers.superadmin.promotion_controller import PromotionController
from controllers.superadmin.review_controller import ReviewController

admin_bp = Blueprint('admin_bp', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ── CATEGORY ─────────────────────────────────────────────────────────────────────
@admin_bp.route('/categories', methods=['GET'])
@super_admin_role_required
def list_categories():
    try:
        cats = CategoryController.list_all()
        return jsonify([c.serialize() for c in cats]), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error listing categories: {e}")
        return jsonify({'message': 'Failed to retrieve categories.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/categories', methods=['POST'])
@super_admin_role_required
def create_category():
   
    name = request.form.get('name')
    slug = request.form.get('slug')

    if not name or not name.strip():
        return jsonify({'message': 'Name is required'}), HTTPStatus.BAD_REQUEST
    if not slug or not slug.strip():
        return jsonify({'message': 'Slug is required'}), HTTPStatus.BAD_REQUEST

    category_data = {
        'name': name.strip(),
        'slug': slug.strip()
    }

    
    raw_parent_id = request.form.get('parent_id')
    if raw_parent_id and raw_parent_id.strip():
        try:
            category_data['parent_id'] = int(raw_parent_id)
        except ValueError:
            return jsonify({'message': 'Invalid parent_id format. Must be an integer.'}), HTTPStatus.BAD_REQUEST
    else:
        category_data['parent_id'] = None

    
    category_data['icon_url'] = request.form.get('icon_url', None)
    if category_data['icon_url'] == '':
        category_data['icon_url'] = None


    
    icon_url_from_cloudinary = None
    if 'icon_file' in request.files:
        file = request.files['icon_file']
        
        
        if file and file.filename and file.filename.strip() != '':
            if not allowed_file(file.filename):
                return jsonify({'message': f"Invalid icon file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), HTTPStatus.BAD_REQUEST
            
            try:
                
                upload_result = cloudinary.uploader.upload(
                    file,
                    folder="category_icons",  
                    resource_type="image"
                )
                
                icon_url_from_cloudinary = upload_result.get('secure_url')
                
                if not icon_url_from_cloudinary:
                   
                    current_app.logger.error("Cloudinary upload succeeded but no secure_url was returned.")
                    return jsonify({'message': 'Cloudinary upload succeeded but did not return a URL.'}), HTTPStatus.INTERNAL_SERVER_ERROR
                
                
                category_data['icon_url'] = icon_url_from_cloudinary

            except cloudinary.exceptions.Error as e:
                current_app.logger.error(f"Cloudinary upload failed: {e}")
                return jsonify({'message': f"Cloudinary icon upload failed: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
            except Exception as e: 
                current_app.logger.error(f"An error occurred during icon file upload: {e}")
                return jsonify({'message': f"An error occurred during icon file upload: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
        elif file.filename == '' and 'icon_file' in request.files:
           
            pass

   
    try:
        cat = CategoryController.create(category_data) 
        return jsonify(cat.serialize()), HTTPStatus.CREATED
    except IntegrityError as e:
        db.session.rollback()
       
        current_app.logger.error(f"IntegrityError creating category: {e}")
        if "unique constraint" in str(e.orig).lower() or (hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23505'):
             return jsonify({'message': 'A category with this slug already exists.'}), HTTPStatus.CONFLICT
        return jsonify({'message': 'Failed to create category due to a data conflict (e.g., duplicate slug or invalid parent_id).'}), HTTPStatus.CONFLICT
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating category: {e}")
        return jsonify({'message': f'Could not create category: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR


@admin_bp.route('/categories/<int:cid>', methods=['PUT'])
@super_admin_role_required
def update_category(cid):
   
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided for update'}), HTTPStatus.BAD_REQUEST
    
   
    if 'parent_id' in data and data['parent_id'] is not None:
        if data['parent_id'] == '': 
            data['parent_id'] = None
        else:
            try:
                data['parent_id'] = int(data['parent_id'])
            except (ValueError, TypeError):
                 return jsonify({'message': 'Invalid parent_id format. Must be an integer or null.'}), HTTPStatus.BAD_REQUEST

    try:
        
        cat = CategoryController.update(cid, data)
        return jsonify(cat.serialize()), HTTPStatus.OK
    except IntegrityError as e: 
        db.session.rollback()
        current_app.logger.error(f"IntegrityError updating category {cid}: {e}")
        if "unique constraint" in str(e.orig).lower() or (hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23505'):
            return jsonify({'message': 'Update failed. A category with the new slug might already exist.'}), HTTPStatus.CONFLICT
        return jsonify({'message': 'Update failed due to a data conflict (e.g., duplicate slug or invalid parent_id).'}), HTTPStatus.CONFLICT
    except FileNotFoundError: 
        return jsonify({'message': 'Category not found'}), HTTPStatus.NOT_FOUND
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating category {cid}: {e}")
        return jsonify({'message': f'Could not update category: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR


@admin_bp.route('/categories/<int:cid>', methods=['DELETE'])
@super_admin_role_required
def delete_category(cid):
    try:
        
        cat = CategoryController.soft_delete(cid)
        return jsonify(cat.serialize()), HTTPStatus.OK
    except FileNotFoundError: 
        return jsonify({'message': 'Category not found'}), HTTPStatus.NOT_FOUND
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting category {cid}: {e}")
        return jsonify({'message': f'Could not delete category: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR


@admin_bp.route('/categories/<int:cid>/upload_icon', methods=['POST'])
@super_admin_role_required
def upload_category_icon(cid):
    try:
        
        from models.category import Category 
        category = Category.query.filter_by(id=cid, deleted_at=None).first()
        if not category:
            return jsonify({'message': 'Category not found or has been deleted'}), HTTPStatus.NOT_FOUND

        if 'file' not in request.files:
            return jsonify({'message': 'No file part in the request'}), HTTPStatus.BAD_REQUEST
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), HTTPStatus.BAD_REQUEST

        if not allowed_file(file.filename):
            return jsonify({'message': f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), HTTPStatus.BAD_REQUEST

        public_id_for_cloudinary = f"category_icons/category_{cid}_{file.filename.rsplit('.', 1)[0]}"

        upload_result = cloudinary.uploader.upload(
            file,
            folder="category_icons",
            public_id=public_id_for_cloudinary,
            overwrite=True,
            resource_type="image"
        )
        
        icon_url = upload_result.get('secure_url')
        if not icon_url:
            current_app.logger.error(f"Cloudinary upload for category {cid} succeeded but no secure_url.")
            return jsonify({'message': 'Cloudinary did not return a URL'}), HTTPStatus.INTERNAL_SERVER_ERROR

        category.icon_url = icon_url
       
        db.session.commit()

        return jsonify({
            'message': 'Icon uploaded and category updated successfully',
            'category': category.serialize()
        }), HTTPStatus.OK

    except cloudinary.exceptions.Error as e:
        current_app.logger.error(f"Cloudinary upload failed for category {cid}: {e}")
        return jsonify({'message': f"Cloudinary upload failed: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
   
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error uploading icon for category {cid}: {e}")
        return jsonify({'message': f"An unexpected error occurred: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR



# ── BRAND REQUESTS ────────────────────────────────────────────────────────────────
@admin_bp.route('/brand-requests', methods=['GET'])
@super_admin_role_required
def list_brand_requests():
    try:
        reqs = BrandRequestController.list_pending()
        
        return jsonify([r.serialize() for r in reqs]), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error listing brand requests: {e}")
        return jsonify({'message': 'Failed to retrieve brand requests.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/brand-requests/<int:rid>/approve', methods=['POST'])
@super_admin_role_required
def approve_brand_request(rid):
    user_id = get_jwt_identity()
    icon_url_from_cloudinary = None

    if 'brand_icon_file' in request.files:
        file = request.files['brand_icon_file']
        if file and file.filename and file.filename.strip() != '':
            if not allowed_file(file.filename):
                return jsonify({'message': f"Invalid brand icon file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), HTTPStatus.BAD_REQUEST
            try:
                upload_result = cloudinary.uploader.upload(
                    file,
                    folder="brand_icons",
                    resource_type="image"
                )
                icon_url_from_cloudinary = upload_result.get('secure_url')
                if not icon_url_from_cloudinary:
                    current_app.logger.error(f"Cloudinary upload for brand request {rid} succeeded but no secure_url.")
                    return jsonify({'message': 'Cloudinary upload succeeded but did not return a URL.'}), HTTPStatus.INTERNAL_SERVER_ERROR
            except cloudinary.exceptions.Error as e:
                current_app.logger.error(f"Cloudinary upload failed for brand request {rid}: {e}")
                return jsonify({'message': f"Cloudinary icon upload failed: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
            except Exception as e:
                current_app.logger.error(f"Error during brand icon file upload for request {rid}: {e}")
                return jsonify({'message': f"An error occurred during brand icon file upload: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
        elif file.filename == '' and 'brand_icon_file' in request.files:
            pass # No file chosen

    try:
        
        created_brand = BrandRequestController.approve(rid, user_id, icon_url=icon_url_from_cloudinary)
        # Ensure Brand.serialize() includes icon_url
        return jsonify(created_brand.serialize()), HTTPStatus.CREATED 
    except FileNotFoundError as e: 
        return jsonify({'message': str(e)}), HTTPStatus.NOT_FOUND
    except IntegrityError as e:
        db.session.rollback()
        error_message = e.args[0] if e.args else "Data conflict during brand approval."
        current_app.logger.error(f"Data conflict approving brand request {rid}: {error_message}")
        return jsonify({'message': error_message}), HTTPStatus.CONFLICT
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error approving brand request {rid}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int): 
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': f'Could not approve brand request: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/brand-requests/<int:rid>/reject', methods=['POST'])
@super_admin_role_required
def reject_brand_request(rid):
    user_id = get_jwt_identity()
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Rejection notes are required in JSON body.'}), HTTPStatus.BAD_REQUEST
    
    notes = data.get('notes')
    if notes is None:
        return jsonify({'message': 'Rejection notes (`notes` field) are required.'}), HTTPStatus.BAD_REQUEST

    try:
        br = BrandRequestController.reject(rid, user_id, notes)
        return jsonify(br.serialize()), HTTPStatus.OK
    except FileNotFoundError as e:
        return jsonify({'message': str(e)}), HTTPStatus.NOT_FOUND
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting brand request {rid}: {e}")
        if hasattr(e, 'code') and isinstance(e.code, int):
            return jsonify({'message': getattr(e, 'description', str(e))}), e.code
        return jsonify({'message': f'Could not reject brand request: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

# ── BRANDS ────────────────────────────────────────────────────────────────────────
@admin_bp.route('/brands', methods=['GET'])
@super_admin_role_required
def list_brands():
    try:
        brands_list = BrandController.list_all()
        
        return jsonify([b.serialize() for b in brands_list]), HTTPStatus.OK
    except Exception as e:
        current_app.logger.error(f"Error listing brands: {e}")
        return jsonify({'message': 'Failed to retrieve brands.'}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/brands', methods=['POST'])
@super_admin_role_required
def create_brand_directly(): 
    name = request.form.get('name', '').strip()
    slug_provided = request.form.get('slug', '').strip()

    if not name:
        return jsonify({'message': 'Brand name is required'}), HTTPStatus.BAD_REQUEST

    slug = ""
    if slug_provided:
        slug = slug_provided
        if Brand.query.filter_by(slug=slug, deleted_at=None).first():
            return jsonify({'message': f"A brand with the provided slug '{slug}' already exists."}), HTTPStatus.CONFLICT
    else:
        base_slug = name.lower()
        base_slug = re.sub(r'\s+', '-', base_slug)
        base_slug = re.sub(r'[^a-z0-9-]', '', base_slug)
        base_slug = re.sub(r'-+', '-', base_slug).strip('-')
        if not base_slug:
            temp_brand_check = Brand.query.order_by(Brand.brand_id.desc()).first()
            next_id = (temp_brand_check.brand_id + 1) if temp_brand_check else 1
            base_slug = f"brand-{next_id}"

        temp_slug = base_slug
        counter = 1
        while Brand.query.filter_by(slug=temp_slug, deleted_at=None).first():
            temp_slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 100:
                 current_app.logger.error(f"Could not generate a unique slug for direct brand creation: {name}")
                 return jsonify({'message': f"Could not generate a unique slug for brand: {name}. Try providing a unique slug manually."}), HTTPStatus.INTERNAL_SERVER_ERROR
        slug = temp_slug
    
    brand_data = {
        'name': name,
        'slug': slug,
        'approved_by': get_jwt_identity(),
        'approved_at': datetime.now(timezone.utc),
        'icon_url': None 
    }

    icon_url_from_text = request.form.get('icon_url', None)
    if icon_url_from_text and icon_url_from_text.strip():
        brand_data['icon_url'] = icon_url_from_text.strip()

    if 'icon_file' in request.files:
        file = request.files['icon_file']
        if file and file.filename and file.filename.strip() != '':
            if not allowed_file(file.filename):
                return jsonify({'message': f"Invalid icon file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), HTTPStatus.BAD_REQUEST
            try:
                upload_result = cloudinary.uploader.upload(file, folder="brand_icons", resource_type="image")
                icon_url_from_cloudinary = upload_result.get('secure_url')
                if not icon_url_from_cloudinary:
                    current_app.logger.error("Cloudinary brand icon upload (direct create) succeeded but no secure_url.")
                    return jsonify({'message': 'Cloudinary upload did not return a URL.'}), HTTPStatus.INTERNAL_SERVER_ERROR
                brand_data['icon_url'] = icon_url_from_cloudinary 
            except cloudinary.exceptions.Error as e:
                current_app.logger.error(f"Cloudinary icon upload failed (direct brand create): {e}")
                return jsonify({'message': f"Cloudinary icon upload failed: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
            except Exception as e:
                current_app.logger.error(f"An error occurred during icon file upload (direct brand create): {e}")
                return jsonify({'message': f"An error occurred during icon file upload: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
    
    try:
        new_brand = BrandController.create(brand_data)
        return jsonify(new_brand.serialize()), HTTPStatus.CREATED
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"IntegrityError creating brand directly: {e}")
        if "unique constraint" in str(e.orig).lower() or (hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23505'):
             return jsonify({'message': f"A brand with this name or slug already exists: {name} / {slug}"}), HTTPStatus.CONFLICT
        return jsonify({'message': 'Failed to create brand due to a data conflict.'}), HTTPStatus.CONFLICT
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating brand directly: {e}")
        return jsonify({'message': f'Could not create brand: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/brands/<int:bid>/upload_icon', methods=['POST'])
@super_admin_role_required
def upload_brand_icon(bid):
    try:
        
        brand = Brand.query.filter_by(brand_id=bid, deleted_at=None).first()
        if not brand:
            return jsonify({'message': 'Brand not found or has been deleted'}), HTTPStatus.NOT_FOUND

        if 'file' not in request.files:
            return jsonify({'message': 'No file part in the request'}), HTTPStatus.BAD_REQUEST
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), HTTPStatus.BAD_REQUEST

        if not allowed_file(file.filename):
            return jsonify({'message': f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"}), HTTPStatus.BAD_REQUEST

        public_id_for_cloudinary = f"brand_icons/brand_{bid}_{file.filename.rsplit('.', 1)[0]}"

        upload_result = cloudinary.uploader.upload(
            file,
            folder="brand_icons",
            public_id=public_id_for_cloudinary,
            overwrite=True,
            resource_type="image"
        )
        
        icon_url = upload_result.get('secure_url')
        if not icon_url:
            current_app.logger.error(f"Cloudinary upload for brand {bid} succeeded but no secure_url.")
            return jsonify({'message': 'Cloudinary did not return a URL'}), HTTPStatus.INTERNAL_SERVER_ERROR

        brand.icon_url = icon_url
        db.session.add(brand)
        db.session.commit()

        return jsonify({
            'message': 'Brand icon uploaded and updated successfully',
            'brand': brand.serialize()
        }), HTTPStatus.OK

    except cloudinary.exceptions.Error as e:
        current_app.logger.error(f"Cloudinary upload failed for brand {bid}: {e}")
        return jsonify({'message': f"Cloudinary upload failed: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error uploading icon for brand {bid}: {e}")
        return jsonify({'message': f"An unexpected error occurred: {str(e)}"}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/brands/<int:bid>', methods=['PUT'])
@super_admin_role_required
def update_brand(bid):
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided for update'}), HTTPStatus.BAD_REQUEST
    
    update_data = {}
    if 'name' in data and data['name'].strip(): 
        update_data['name'] = data['name'].strip()
    if 'slug' in data and data['slug'].strip(): 
        update_data['slug'] = data['slug'].strip()
    
    if not update_data: 
        return jsonify({'message': 'No updatable fields (name, slug) provided or fields are empty.'}), HTTPStatus.BAD_REQUEST

    try:
       
        updated_brand = BrandController.update(bid, update_data)
        return jsonify(updated_brand.serialize()), HTTPStatus.OK
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"IntegrityError updating brand {bid}: {e}")
        if "unique constraint" in str(e.orig).lower() or (hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23505'):
             return jsonify({'message': 'Update failed. A brand with this name or slug already exists.'}), HTTPStatus.CONFLICT
        return jsonify({'message': 'Update failed due to a data conflict.'}), HTTPStatus.CONFLICT
    except FileNotFoundError: 
        return jsonify({'message': 'Brand not found'}), HTTPStatus.NOT_FOUND
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating brand {bid}: {e}")
        return jsonify({'message': f'Could not update brand: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/brands/<int:bid>', methods=['DELETE'])
@super_admin_role_required
def delete_brand(bid):
    try:
        
        deleted_brand = BrandController.delete(bid)
        return jsonify(deleted_brand.serialize()), HTTPStatus.OK
    except FileNotFoundError: 
        return jsonify({'message': 'Brand not found'}), HTTPStatus.NOT_FOUND
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting brand {bid}: {e}")
        return jsonify({'message': f'Could not delete brand: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR

@admin_bp.route('/brands/<int:bid>/restore', methods=['POST']) # Or PUT
@super_admin_role_required
def restore_brand(bid):
    try:
        restored_brand = BrandController.undelete(bid)
        return jsonify(restored_brand.serialize()), HTTPStatus.OK
    except FileNotFoundError: 
        return jsonify({'message': 'Brand not found, cannot restore.'}), HTTPStatus.NOT_FOUND
    except Exception as e:
        db.session.rollback() 
        current_app.logger.error(f"Error restoring brand {bid}: {e}")
        return jsonify({'message': f'Could not restore brand: {str(e)}'}), HTTPStatus.INTERNAL_SERVER_ERROR


# ── PROMOTIONS ────────────────────────────────────────────────────────────────────
@admin_bp.route('/promotions', methods=['GET'])
@super_admin_role_required
def list_promotions():
    ps = PromotionController.list_all()
    return jsonify([p.serialize() for p in ps]), 200

@admin_bp.route('/promotions', methods=['POST'])
@super_admin_role_required
def create_promotion():
    data = request.get_json()
    p = PromotionController.create(data)
    return jsonify(p.serialize()), 201

@admin_bp.route('/promotions/<int:pid>', methods=['PUT'])
@super_admin_role_required
def update_promotion(pid):
    data = request.get_json()
    p = PromotionController.update(pid, data)
    return jsonify(p.serialize()), 200

@admin_bp.route('/promotions/<int:pid>', methods=['DELETE'])
@super_admin_role_required
def delete_promotion(pid):
    p = PromotionController.soft_delete(pid)
    return jsonify(p.serialize()), 200

# ── REVIEWS ──────────────────────────────────────────────────────────────────────
@admin_bp.route('/reviews', methods=['GET'])
@super_admin_role_required
def list_reviews():
    rs = ReviewController.list_recent()
    return jsonify([r.serialize() for r in rs]), 200

@admin_bp.route('/reviews/<int:rid>', methods=['DELETE'])
@super_admin_role_required
def delete_review(rid):
    r = ReviewController.delete(rid)
    return jsonify(r.serialize()), 200


# ── ATTRIBUTE VALUES ─────────────────────────────────────────────────────────────
from controllers.superadmin.attribute_value_controller import AttributeValueController

@admin_bp.route('/attribute-values', methods=['GET'])
@super_admin_role_required
def list_attribute_values():
    avs = AttributeValueController.list_all()
    return jsonify([ {
        'attribute_id': av.attribute_id,
        'value_code': av.value_code,
        'value_label': av.value_label
    } for av in avs]), 200

@admin_bp.route('/attribute-values/<int:aid>', methods=['GET'])
@super_admin_role_required
def list_values_for_attribute(aid):
    avs = AttributeValueController.list_for_attribute(aid)
    return jsonify([ {
        'attribute_id': av.attribute_id,
        'value_code': av.value_code,
        'value_label': av.value_label
    } for av in avs]), 200

@admin_bp.route('/attribute-values', methods=['POST'])
@super_admin_role_required
def create_attribute_value():
    data = request.get_json()
    av = AttributeValueController.create(data)
    return jsonify({
        'attribute_id': av.attribute_id,
        'value_code': av.value_code,
        'value_label': av.value_label
    }), 201

@admin_bp.route('/attribute-values/<int:aid>/<value_code>', methods=['PUT'])
@super_admin_role_required
def update_attribute_value(aid, value_code):
    data = request.get_json()
    av = AttributeValueController.update(aid, value_code, data)
    return jsonify({
        'attribute_id': av.attribute_id,
        'value_code': av.value_code,
        'value_label': av.value_label
    }), 200

@admin_bp.route('/attribute-values/<int:aid>/<value_code>', methods=['DELETE'])
@super_admin_role_required
def delete_attribute_value(aid, value_code):
    AttributeValueController.delete(aid, value_code)
    return '', 204
