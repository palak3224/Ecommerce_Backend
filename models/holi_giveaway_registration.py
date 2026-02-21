from common.database import db


class HoliGiveawayRegistration(db.Model):
    __tablename__ = 'holi_giveaway_registrations'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'registeredAt': self.created_at.strftime('%d %b, %I:%M %p') if self.created_at else ''
        }
