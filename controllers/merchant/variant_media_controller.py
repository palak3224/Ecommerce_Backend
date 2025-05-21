from flask import current_app
from flask_jwt_extended import get_jwt_identity
from models.variant_media import VariantMedia
from models.enums import MediaType
from models.variant import Variant
from models.product import Product
from auth.models.models import MerchantProfile 
from common.database import db
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import cloudinary 

class MerchantVariantMediaController:
    @staticmethod
    def _get_merchant_id_from_jwt(): 
        """Gets the merchant_id associated with the current JWT user."""
        user_id = get_jwt_identity()
        merchant = MerchantProfile.get_by_user_id(user_id) 
        if not merchant:
            raise FileNotFoundError("Merchant profile not found for the current user.") 
        return merchant.id 

    @staticmethod
    def list(variant_id):
        merchant_id = MerchantVariantMediaController._get_merchant_id_from_jwt() 
        variant = Variant.query.join(Variant.product).filter(
            Variant.variant_id == variant_id,
            Variant.deleted_at == None,
            Product.merchant_id == merchant_id
        ).first_or_404(
            description=f"Variant with ID {variant_id} not found or you do not have permission to access its media."
        )
        return VariantMedia.query.filter_by(variant_id=variant.variant_id, deleted_at=None).order_by(VariantMedia.display_order).all()

    @staticmethod
    def create(variant_id_param, data):
        merchant_id = MerchantVariantMediaController._get_merchant_id_from_jwt() 
        variant = Variant.query.join(Variant.product).filter(
            Variant.variant_id == variant_id_param,
            Variant.deleted_at == None,
            Product.merchant_id == merchant_id
        ).first_or_404(
            description=f"Variant with ID {variant_id_param} not found or you do not have permission to add media to it."
        )

        if not data.get('media_url'):
            raise ValueError("Media URL is required.")
        if not data.get('media_type'):
            raise ValueError("Media type is required.")

        media_type_str = data.get('media_type').upper()
        try:
            media_type_enum = MediaType[media_type_str]
        except KeyError:
            allowed_types = [t.name for t in MediaType]
            raise ValueError(f"Invalid media type '{data.get('media_type')}'. Allowed types are: {', '.join(allowed_types)}")

        display_order = data.get('display_order', 0)
        try:
            display_order = int(display_order)
        except (ValueError, TypeError):
            display_order = 0
       
        cloudinary_public_id = data.get('public_id', None) 

        try:
            vm = VariantMedia(
                variant_id=variant.variant_id, 
                media_url=data['media_url'],
                media_type=media_type_enum,
                display_order=display_order,
                is_primary=data.get('is_primary', False),
                public_id=cloudinary_public_id 
            )
            db.session.add(vm)
            db.session.commit()
            return vm
        except IntegrityError as e:
            db.session.rollback()
            raise ValueError("Failed to create variant media due to a data conflict.") from e
        except Exception as e:
            db.session.rollback()
            if cloudinary_public_id: 
                 try:
                    resource_type_for_cloudinary = "image" if media_type_enum == MediaType.IMAGE else "video"
                    cloudinary.uploader.destroy(cloudinary_public_id, resource_type=resource_type_for_cloudinary)
                 except Exception as cloud_e:
                    current_app.logger.error(f"Failed to delete orphaned Cloudinary file {cloudinary_public_id} after DB error: {cloud_e}")
            raise RuntimeError(f"An unexpected error occurred while creating variant media: {e}") from e

    @staticmethod
    def delete(media_id):
        merchant_id = MerchantVariantMediaController._get_merchant_id_from_jwt() 
        vm = VariantMedia.query.join(VariantMedia.variant).join(Variant.product).filter( 
            VariantMedia.media_id == media_id,
            VariantMedia.deleted_at == None,
            Product.merchant_id == merchant_id 
        ).first_or_404(
            description=f"Variant media with ID {media_id} not found or you do not have permission to delete it."
        )
        
        if hasattr(vm, 'public_id') and vm.public_id:
            try:
                resource_type_for_cloudinary = "image" if vm.media_type == MediaType.IMAGE else "video"
                cloudinary.uploader.destroy(vm.public_id, resource_type=resource_type_for_cloudinary)
                current_app.logger.info(f"Successfully deleted {vm.public_id} from Cloudinary.")
            except Exception as e:
                current_app.logger.error(f"Failed to delete media {vm.public_id} from Cloudinary: {e}")

        vm.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        return vm 