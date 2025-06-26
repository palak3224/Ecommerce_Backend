from datetime import datetime
from flask import request
from models.promotion import Promotion

# Add serialize_with_game_plays to Promotion if not present
if not hasattr(Promotion, 'serialize_with_game_plays'):
    def serialize_with_game_plays(self):
        data = self.serialize()
        data['game_plays'] = [gp.serialize() for gp in self.game_plays]
        return data
    Promotion.serialize_with_game_plays = serialize_with_game_plays

class GamePromoAdminController:
    @staticmethod
    def list_current_game_promos():
        """List all current running (active, not expired, not deleted) game promocodes that have NOT been won by any user (no GamePlay records)."""
        today = datetime.utcnow().date()
        query = Promotion.query.filter(
            Promotion.active_flag == True,
            Promotion.deleted_at == None,
            Promotion.start_date <= today,
            Promotion.end_date >= today,
            ~Promotion.game_plays.any()  # Only promos with no associated GamePlay
        )
        # Optional filters
        discount = request.args.get('discount')
        if discount:
            try:
                discount = float(discount)
                query = query.filter(Promotion.discount_value == discount)
            except ValueError:
                pass
        game_type = request.args.get('game_type')
        if game_type:
            # Only promos that would be available for this game type (not yet assigned)
            # This filter is not strictly necessary since no GamePlay exists, but kept for API compatibility
            pass
        promos = query.order_by(Promotion.created_at.desc()).all()
        return [p.serialize_with_game_plays() for p in promos] 