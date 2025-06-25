from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from controllers.games_controller import GamesController
from controllers.superadmin.game_promo_controller import GamePromoAdminController
from auth.utils import super_admin_role_required

# Blueprint
games_bp = Blueprint('games_bp', __name__, url_prefix='/api/games')

@games_bp.route('/spin-wheel', methods=['POST'])
@jwt_required()
def play_spin_wheel():
    user_id = get_jwt_identity()
    result, status = GamesController.play_game(user_id, 'spin-wheel')
    return jsonify(result), status

@games_bp.route('/match-card', methods=['POST'])
@jwt_required()
def play_match_card():
    user_id = get_jwt_identity()
    result, status = GamesController.play_game(user_id, 'match-card')
    return jsonify(result), status

@games_bp.route('/my-promos', methods=['GET'])
@jwt_required()
def get_my_promos():
    user_id = get_jwt_identity()
    result, status = GamesController.get_user_game_promos(user_id)
    return jsonify(result), status

@games_bp.route('/current-promos', methods=['GET'])
@jwt_required()
@super_admin_role_required
def get_current_promos():
    promos = GamePromoAdminController.list_current_game_promos()
    return jsonify({'promotions': promos}), 200

@games_bp.route('/can-play/<game_type>', methods=['GET'])
@jwt_required()
def can_play_game(game_type):
    user_id = get_jwt_identity()
    result, status = GamesController.can_play_today(user_id, game_type)
    return jsonify(result), status 