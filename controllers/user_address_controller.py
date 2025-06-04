from flask import jsonify, request
from common.database import db
from models.user_address import UserAddress
from models.enums import AddressTypeEnum
from sqlalchemy.exc import SQLAlchemyError

class UserAddressController:
    @staticmethod
    def create_address(user_id):
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['address_line1', 'city', 'state_province', 'postal_code', 'country_code']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'error': f'{field} is required'}), 400

            # Create new address
            new_address = UserAddress(
                user_id=user_id,
                contact_name=data.get('contact_name'),
                contact_phone=data.get('contact_phone'),
                address_line1=data.get('address_line1'),
                address_line2=data.get('address_line2'),
                landmark=data.get('landmark'),
                city=data.get('city'),
                state_province=data.get('state_province'),
                postal_code=data.get('postal_code'),
                country_code=data.get('country_code'),
                address_type=AddressTypeEnum.SHIPPING if data.get('address_type') == 'shipping' else AddressTypeEnum.BILLING,
                is_default_shipping=data.get('is_default_shipping', False),
                is_default_billing=data.get('is_default_billing', False)
            )

            # If this is set as default, unset other default addresses
            if new_address.is_default_shipping:
                UserAddress.query.filter_by(
                    user_id=user_id,
                    is_default_shipping=True
                ).update({'is_default_shipping': False})
            
            if new_address.is_default_billing:
                UserAddress.query.filter_by(
                    user_id=user_id,
                    is_default_billing=True
                ).update({'is_default_billing': False})

            db.session.add(new_address)
            db.session.commit()

            return jsonify({
                'message': 'Address created successfully',
                'address': new_address.serialize()
            }), 201
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def get_addresses(user_id):
        try:
            addresses = UserAddress.query.filter_by(user_id=user_id).all()
            return jsonify({
                'addresses': [address.serialize() for address in addresses]
            }), 200
        except SQLAlchemyError as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def get_address(user_id, address_id):
        try:
            address = UserAddress.query.filter_by(
                user_id=user_id,
                address_id=address_id
            ).first_or_404()

            return jsonify({
                'address': address.serialize()
            }), 200
        except SQLAlchemyError as e:
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def update_address(user_id, address_id):
        try:
            address = UserAddress.query.filter_by(
                user_id=user_id,
                address_id=address_id
            ).first_or_404()

            data = request.get_json()

            # Update fields if provided
            fields = [
                'contact_name', 'contact_phone', 'address_line1', 'address_line2',
                'landmark', 'city', 'state_province', 'postal_code', 'country_code',
                'is_default_shipping', 'is_default_billing'
            ]

            for field in fields:
                if field in data:
                    setattr(address, field, data[field])

            # Handle address type if provided
            if 'address_type' in data:
                address.address_type = AddressTypeEnum.SHIPPING if data['address_type'] == 'shipping' else AddressTypeEnum.BILLING

            # If setting as default, unset other default addresses
            if address.is_default_shipping:
                UserAddress.query.filter(
                    UserAddress.user_id == user_id,
                    UserAddress.address_id != address_id,
                    UserAddress.is_default_shipping == True
                ).update({'is_default_shipping': False})
            
            if address.is_default_billing:
                UserAddress.query.filter(
                    UserAddress.user_id == user_id,
                    UserAddress.address_id != address_id,
                    UserAddress.is_default_billing == True
                ).update({'is_default_billing': False})

            db.session.commit()

            return jsonify({
                'message': 'Address updated successfully',
                'address': address.serialize()
            }), 200
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def delete_address(user_id, address_id):
        try:
            address = UserAddress.query.filter_by(
                user_id=user_id,
                address_id=address_id
            ).first_or_404()

            db.session.delete(address)
            db.session.commit()

            return jsonify({
                'message': 'Address deleted successfully'
            }), 200
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    @staticmethod
    def set_default_address(user_id, address_id, address_type):
        try:
            address = UserAddress.query.filter_by(
                user_id=user_id,
                address_id=address_id
            ).first_or_404()

            # Unset current default address
            if address_type == 'shipping':
                UserAddress.query.filter_by(
                    user_id=user_id,
                    is_default_shipping=True
                ).update({'is_default_shipping': False})
                address.is_default_shipping = True
            else:
                UserAddress.query.filter_by(
                    user_id=user_id,
                    is_default_billing=True
                ).update({'is_default_billing': False})
                address.is_default_billing = True

            db.session.commit()

            return jsonify({
                'message': f'Default {address_type} address updated successfully',
                'address': address.serialize()
            }), 200
        except SQLAlchemyError as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500 