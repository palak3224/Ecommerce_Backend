# FILE: controllers/superadmin/plinko_admin_controller.py
"""Superadmin view of the lead-capture game.

The list query joins leads -> promotions -> redemptions -> orders so the panel answers
the question that actually matters: not "how many emails did we collect" but "which of
them bought, and what did the discount cost". That is why PromotionRedemption stores
discount_amount rather than deriving it — the promotion's rules may have changed since.
"""
import csv
import io
from datetime import datetime
from decimal import Decimal

from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import joinedload

from common.database import db
from models.plinko import PlinkoCampaign, PlinkoLead, PlinkoPrize
from models.promotion import Promotion
from models.promotion_redemption import PromotionRedemption
from services.promotion_service import business_today


class PlinkoAdminController:

    @staticmethod
    def _base_query(status=None, campaign_id=None, search=None,
                    date_from=None, date_to=None, sort_by='-created_at'):
        query = PlinkoLead.query.options(joinedload(PlinkoLead.prize))

        if status and status.lower() != 'all':
            query = query.filter(PlinkoLead.status == status.lower())
        if campaign_id:
            query = query.filter(PlinkoLead.campaign_id == campaign_id)
        if date_from:
            query = query.filter(PlinkoLead.created_at >= date_from)
        if date_to:
            query = query.filter(PlinkoLead.created_at <= date_to)

        if search:
            like = f"%{search.strip()}%"
            # Outer-join the promotion so a search by coupon code works even for
            # leads that never completed (they have no promotion at all).
            query = query.outerjoin(
                Promotion, Promotion.promotion_id == PlinkoLead.promotion_id
            ).filter(or_(
                PlinkoLead.email.ilike(like),
                PlinkoLead.phone.ilike(like),
                Promotion.code.ilike(like),
            ))

        direction = desc if (sort_by or '').startswith('-') else asc
        field = (sort_by or '-created_at').lstrip('-')
        column = getattr(PlinkoLead, field, None)
        query = query.order_by(direction(column) if column is not None
                               else desc(PlinkoLead.created_at))
        return query

    @staticmethod
    def list_leads(page=1, per_page=20, **filters):
        return PlinkoAdminController._base_query(**filters).paginate(
            page=page, per_page=per_page, error_out=False
        )

    @staticmethod
    def serialize_lead(lead):
        """A lead plus what became of its coupon."""
        data = lead.serialize()
        promo = Promotion.query.get(lead.promotion_id) if lead.promotion_id else None
        redemption = (
            PromotionRedemption.query.filter_by(promotion_id=promo.promotion_id).first()
            if promo else None
        )
        data.update({
            'code': promo.code if promo else None,
            'discount': (
                f"{promo.discount_value:g}"
                f"{'%' if promo and promo.discount_type.value == 'percentage' else ''}"
                if promo else None
            ),
            'valid_until': promo.end_date.isoformat() if promo else None,
            'redeemed': redemption is not None,
            'redeemed_at': redemption.redeemed_at.isoformat() if redemption else None,
            'order_id': redemption.order_id if redemption else None,
            'discount_given': float(redemption.discount_amount) if redemption else None,
        })
        return data

    @staticmethod
    def stats(campaign_id=None):
        """Funnel counts plus what the campaign has actually cost."""
        lead_q = PlinkoLead.query
        if campaign_id:
            lead_q = lead_q.filter(PlinkoLead.campaign_id == campaign_id)

        plays = lead_q.count()
        emails = lead_q.filter(PlinkoLead.email.isnot(None)).count()
        completed = lead_q.filter(PlinkoLead.status == 'completed').count()

        redeemed_q = db.session.query(
            db.func.count(PromotionRedemption.redemption_id),
            db.func.coalesce(db.func.sum(PromotionRedemption.discount_amount), 0),
        ).join(Promotion, Promotion.promotion_id == PromotionRedemption.promotion_id) \
         .filter(Promotion.source == 'plinko')
        redeemed_count, discount_total = redeemed_q.one()

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        minted_today = Promotion.query.filter(
            Promotion.source == 'plinko', Promotion.created_at >= today_start
        ).count()

        campaign = (
            PlinkoCampaign.query.get(campaign_id) if campaign_id
            else PlinkoCampaign.query.filter_by(is_active=True).first()
        )
        ceiling = campaign.daily_mint_ceiling if campaign else 0

        return {
            'plays': plays,
            'emails_captured': emails,
            'completed': completed,
            # The number that says whether the game is working as a lead magnet.
            'completion_rate': round((completed / plays * 100), 1) if plays else 0.0,
            'codes_redeemed': int(redeemed_count or 0),
            'discount_given': float(discount_total or 0),
            'minted_today': minted_today,
            'daily_mint_ceiling': ceiling,
            'remaining_today': max(ceiling - minted_today, 0),
        }

    @staticmethod
    def export_csv(**filters):
        """Returns (bytes, mimetype, filename), matching the analytics export convention."""
        leads = PlinkoAdminController._base_query(**filters).all()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            'Lead ID', 'Captured At', 'Email', 'Phone', 'Prize', 'Code',
            'Valid Until', 'Status', 'Redeemed', 'Order ID', 'Discount Given',
        ])
        for lead in leads:
            row = PlinkoAdminController.serialize_lead(lead)
            writer.writerow([
                row['lead_id'], row['created_at'], row['email'] or '',
                row['phone'] or '', row['prize_label'] or '', row['code'] or '',
                row['valid_until'] or '', row['status'],
                'Yes' if row['redeemed'] else 'No', row['order_id'] or '',
                row['discount_given'] if row['discount_given'] is not None else '',
            ])
        stamp = business_today().strftime('%Y%m%d')
        return (
            buffer.getvalue().encode('utf-8'),
            'text/csv',
            f'plinko_leads_{stamp}.csv',
        )

    # --- campaigns ---------------------------------------------------------

    @staticmethod
    def list_campaigns():
        campaigns = PlinkoCampaign.query.filter(
            PlinkoCampaign.deleted_at.is_(None)
        ).order_by(PlinkoCampaign.campaign_id.desc()).all()
        return [c.serialize(include_weights=True) for c in campaigns]

    @staticmethod
    def save_campaign(payload, campaign_id=None):
        """Create or update a campaign and replace its prize slots."""
        campaign = PlinkoCampaign.query.get(campaign_id) if campaign_id else PlinkoCampaign()

        if campaign_id and not campaign:
            raise ValueError("Campaign not found.")

        for field in ('name', 'headline', 'subheadline', 'terms_text', 'coupon_prefix'):
            if field in payload:
                setattr(campaign, field, payload[field])
        for field in ('validity_days', 'popup_delay_seconds', 'redisplay_after_days',
                      'daily_mint_ceiling'):
            if field in payload and payload[field] is not None:
                setattr(campaign, field, int(payload[field]))
        for field in ('min_order_value', 'max_discount_amount'):
            if field in payload:
                value = payload[field]
                setattr(campaign, field, Decimal(str(value)) if value not in (None, '') else None)
        if 'is_active' in payload:
            campaign.is_active = bool(payload['is_active'])

        if not campaign.name:
            raise ValueError("Campaign name is required.")

        db.session.add(campaign)
        db.session.flush()

        # Only one campaign may be live at a time — the storefront asks for "the"
        # active campaign, so two would make which one a visitor sees arbitrary.
        if campaign.is_active:
            PlinkoCampaign.query.filter(
                PlinkoCampaign.campaign_id != campaign.campaign_id
            ).update({PlinkoCampaign.is_active: False}, synchronize_session=False)

        if 'prizes' in payload:
            PlinkoPrize.query.filter_by(campaign_id=campaign.campaign_id).delete()
            for order, raw in enumerate(payload['prizes'] or []):
                value = raw.get('discount_value')
                db.session.add(PlinkoPrize(
                    campaign_id=campaign.campaign_id,
                    label=raw.get('label') or 'Prize',
                    slot_kind=raw.get('slot_kind') or 'coupon',
                    discount_type=raw.get('discount_type') or 'percentage',
                    discount_value=Decimal(str(value)) if value not in (None, '') else None,
                    weight=int(raw.get('weight') or 0),
                    display_order=int(raw.get('display_order', order)),
                    is_active=bool(raw.get('is_active', True)),
                ))

        db.session.commit()
        return campaign.serialize(include_weights=True)
