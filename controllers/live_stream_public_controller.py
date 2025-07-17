from models.live_stream import LiveStream
from flask import current_app
from controllers.product_controller import ProductController

class LiveStreamPublicController:
    @staticmethod
    def list_public_streams(status=None):
        """
        List all public live streams (optionally filter by status: LIVE, SCHEDULED).
        Only streams that are not deleted are returned.
        """
        query = LiveStream.query.filter_by(deleted_at=None)
        if status:
            query = query.filter_by(status=status)
        streams = query.order_by(LiveStream.scheduled_time.desc()).all()
        return [s.serialize() for s in streams]

    @staticmethod
    def get_public_stream_by_id(stream_id):
        from models.product_media import ProductMedia
        from models.product_attribute import ProductAttribute
        from models.product_meta import ProductMeta
        from models.enums import MediaType, AttributeInputType
        import json
        stream = LiveStream.query.filter_by(stream_id=stream_id, deleted_at=None).first()
        if not stream:
            return None
        stream_data = stream.serialize()
        try:
            product = stream.product
            if product:
                # Return all media (images/videos) as in product_controller.py
                product_media = ProductMedia.query.filter_by(
                    product_id=product.product_id,
                    deleted_at=None
                ).order_by(ProductMedia.sort_order).all()
                media = [m.serialize() for m in product_media] if product_media else []

                # Get selectable attributes (select, multiselect)
                product_attributes = ProductAttribute.query.filter_by(product_id=product.product_id).all()
                selectable_attributes = []
                for attr in product_attributes:
                    input_type = attr.attribute.input_type.value if attr.attribute and hasattr(attr.attribute.input_type, 'value') else str(attr.attribute.input_type)
                    if input_type in [AttributeInputType.SELECT.value, AttributeInputType.MULTISELECT.value]:
                        # Handle array values as in ProductController
                        if attr.value_text and (
                            (attr.value_text.startswith('[') and attr.value_text.endswith(']')) or
                            (attr.value_text.startswith("['") and attr.value_text.endswith("']"))
                        ):
                            try:
                                values = json.loads(attr.value_text)
                                if isinstance(values, list):
                                    for index, value in enumerate(values):
                                        selectable_attributes.append({
                                            "attribute_id": attr.attribute_id + index,
                                            "attribute_name": attr.attribute.name,
                                            "value_code": attr.value_code,
                                            "value_text": str(value),
                                            "value_label": str(value),
                                            "input_type": input_type
                                        })
                                else:
                                    selectable_attributes.append({
                                        "attribute_id": attr.attribute_id,
                                        "attribute_name": attr.attribute.name,
                                        "value_code": attr.value_code,
                                        "value_text": attr.value_text,
                                        "value_label": attr.attribute_value.value_label if attr.attribute_value else None,
                                        "input_type": input_type
                                    })
                            except Exception:
                                selectable_attributes.append({
                                    "attribute_id": attr.attribute_id,
                                    "attribute_name": attr.attribute.name,
                                    "value_code": attr.value_code,
                                    "value_text": attr.value_text,
                                    "value_label": attr.attribute_value.value_label if attr.attribute_value else None,
                                    "input_type": input_type
                                })
                        else:
                            selectable_attributes.append({
                                "attribute_id": attr.attribute_id,
                                "attribute_name": attr.attribute.name,
                                "value_code": attr.value_code,
                                "value_text": attr.value_text,
                                "value_label": attr.attribute_value.value_label if attr.attribute_value else None,
                                "input_type": input_type
                            })

                # Get small description (prefer ProductMeta.short_desc, fallback to product_description)
                product_meta = ProductMeta.query.filter_by(product_id=product.product_id).first()
                small_desc = product_meta.short_desc if product_meta and product_meta.short_desc else product.product_description[:120] if product.product_description else None

                # Compose minimal product info
                stream_data['product'] = {
                    'product_id': product.product_id,
                    'name': product.product_name,
                    'media': media,  # <-- add this
                    'attributes': selectable_attributes,
                    'description': small_desc
                }
        except Exception as e:
            current_app.logger.error(f"Error fetching product for stream {stream_id}: {e}")
            stream_data['product'] = None
        return stream_data 