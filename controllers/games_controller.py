import random
from datetime import datetime, timedelta
from models.promotion import Promotion, GamePlay
from common.database import db
from models.enums import DiscountType

class GamesController:
    PROMO_DISCOUNTS = [5, 10, 15, 20]
    GAME_TYPES = ['spin-wheel', 'match-card']
    WIN_CHANCE = 1/3  # 1 in 3 chance to win

    @staticmethod
    def _get_or_create_promo(discount_value):
        # Find an active, unassigned promo code of this discount
        promo = Promotion.query.filter_by(
            discount_type=DiscountType.PERCENTAGE,
            discount_value=discount_value,
            active_flag=True,
            deleted_at=None,
        ).filter(Promotion.game_plays == None).first()
        if promo:
            return promo
        # If not found, create one
        code = f"GAME{discount_value}{random.randint(1000,9999)}"
        new_promo = Promotion(
            code=code,
            description=f"{discount_value}% off from game",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=discount_value,
            start_date=datetime.utcnow().date(),
            end_date=(datetime.utcnow() + timedelta(days=1)).date(),
            active_flag=True
        )
        db.session.add(new_promo)
        db.session.commit()
        return new_promo

    @staticmethod
    def play_game(user_id, game_type):
        if game_type not in GamesController.GAME_TYPES:
            return {'error': 'Invalid game type.'}, 400
        # Check if user already played this game today
        today = datetime.utcnow().date()
        already_played = GamePlay.query.filter_by(user_id=user_id, game_type=game_type).filter(
            db.func.date(GamePlay.played_at) == today
        ).first()
        if already_played:
            return {'error': 'You have already played this game today.'}, 403
        # Win logic: only win if random chance
        if random.random() > GamesController.WIN_CHANCE:
            # Record play with no promo
            gameplay = GamePlay(user_id=user_id, game_type=game_type, promotion_id=None, played_at=datetime.utcnow())
            db.session.add(gameplay)
            db.session.commit()
            return {'message': 'Sorry, you did not win a promocode this time.'}, 200
        # Pick a random discount
        discount = random.choice(GamesController.PROMO_DISCOUNTS)
        promo = GamesController._get_or_create_promo(discount)
        # Assign promo to user via GamePlay
        gameplay = GamePlay(user_id=user_id, game_type=game_type, promotion_id=promo.promotion_id, played_at=datetime.utcnow())
        db.session.add(gameplay)
        db.session.commit()
        # Generate a new promo of same type for pool
        GamesController._get_or_create_promo(discount)
        return {'message': 'You won a promocode!', 'promotion': promo.serialize()}, 200

    @staticmethod
    def get_user_game_promos(user_id):
        # Get all game plays assigned to this user via games
        game_plays = GamePlay.query.filter_by(user_id=user_id).all()
        return {'game_plays': [gp.serialize() for gp in game_plays]}, 200

    @staticmethod
    def can_play_today(user_id, game_type):
        today = datetime.utcnow().date()
        # Find any play for this user/game today
        gameplay_today = GamePlay.query.filter_by(user_id=user_id, game_type=game_type).filter(
            db.func.date(GamePlay.played_at) == today
        ).first()
        if gameplay_today:
            return {'can_play': False, 'message': 'You have already played this game today.'}, 200
        return {'can_play': True, 'message': 'You can play this game today.'}, 200
