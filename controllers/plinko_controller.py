# FILE: controllers/plinko_controller.py
"""The storefront lead-capture game.

Three steps, and the split is the whole security model: the full coupon code is never
sent to the browser until the phone number is in. A CSS blur is defeatable from the
devtools console in about two seconds, so "reveal half, then all" has to be enforced by
what the server *sends*, not by what the client renders.

  play   -> pick the prize, generate the code string, store it. No PII, no coupon row.
  reveal -> take the email, hand back half the code. Still no coupon row.
  claim  -> take the phone, mint the Promotion, hand back the whole code.

Minting at the last step means the promotions table only grows for visitors who
finished, while plinko_leads grows for everyone who played — so "how many played" and
"how many cost us money" stay separate numbers.
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy.exc import IntegrityError

from common.database import db
from models.enums import DiscountType
from models.plinko import PlinkoCampaign, PlinkoLead, PlinkoPrize
from models.promotion import Promotion
from services.promotion_service import business_today

SESSION_TTL_MINUTES = 30
MAX_CODE_ATTEMPTS = 5
PLAYS_PER_IP_PER_DAY = 20
CLAIMS_PER_IP_PER_DAY = 3

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class PlinkoError(Exception):
    """A refusal with a user-facing message and an HTTP status."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def hash_ip(ip):
    """Hashed, not stored raw. This is abuse plumbing, not a reason to keep visitor IPs."""
    if not ip:
        return None
    salt = current_app.config.get('SECRET_KEY', 'aoin')
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


def _normalise_email(value):
    email = (value or '').strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 255:
        raise PlinkoError("Please enter a valid email address.")
    return email


def _normalise_phone(value):
    """10 digits, matching routes/holi_giveaway_routes.py so the storefront is consistent."""
    digits = re.sub(r"\D", "", str(value or ''))
    if len(digits) != 10:
        raise PlinkoError("Please enter a valid 10-digit mobile number.")
    return digits


def mask_code(code):
    """Half the real characters, the rest hidden. The hidden half never leaves the server."""
    if not code:
        return ''
    shown = len(code) // 2
    return code[:shown] + ('•' * (len(code) - shown))


def get_active_campaign():
    today = business_today()
    campaign = PlinkoCampaign.query.filter(
        PlinkoCampaign.is_active.is_(True),
        PlinkoCampaign.deleted_at.is_(None),
    ).order_by(PlinkoCampaign.campaign_id.desc()).first()
    if not campaign:
        return None
    if campaign.start_date and today < campaign.start_date:
        return None
    if campaign.end_date and today > campaign.end_date:
        return None
    return campaign


def _pick_prize(campaign):
    """Weighted draw over winnable slots only.

    Decoy slots ("Try again", "Free gift") are excluded here but still rendered on the
    board, which is what makes "everyone wins" true regardless of how it looks.
    """
    winnable = [
        p for p in campaign.prizes
        if p.is_active and p.slot_kind == 'coupon' and (p.weight or 0) > 0
        and p.discount_value is not None
    ]
    if not winnable:
        raise PlinkoError("This game is not available right now.", 503)

    total = sum(p.weight for p in winnable)
    # secrets rather than random: the draw decides money, so it should not be
    # predictable from a seed someone can observe.
    roll = secrets.randbelow(total)
    upto = 0
    for prize in winnable:
        upto += prize.weight
        if roll < upto:
            return prize
    return winnable[-1]


def _slot_index(campaign, prize):
    """Where the puck must land: the prize's position among ALL rendered slots."""
    slots = [p for p in campaign.prizes if p.is_active]
    for i, p in enumerate(slots):
        if p.prize_id == prize.prize_id:
            return i
    return 0


def _generate_code(campaign):
    prefix = (campaign.coupon_prefix or 'PLK').upper()
    stamp = business_today().strftime('%y%m%d')
    return f"{prefix}{stamp}{secrets.token_hex(4).upper()}"


def _count_today(model, column, value):
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.session.query(db.func.count(model.lead_id)).filter(
        column == value, model.created_at >= start
    ).scalar() or 0


def _minted_today():
    """Codes issued today. The circuit breaker that bounds daily liability."""
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.session.query(db.func.count(Promotion.promotion_id)).filter(
        Promotion.source == 'plinko', Promotion.created_at >= start
    ).scalar() or 0


def _load_lead(session_token, expected_statuses):
    lead = PlinkoLead.query.filter_by(session_token=(session_token or '')).first()
    if not lead:
        raise PlinkoError("This session has expired. Please play again.", 404)
    if lead.expires_at and datetime.utcnow() > lead.expires_at:
        raise PlinkoError("This session has expired. Please play again.", 410)
    if lead.status not in expected_statuses:
        raise PlinkoError("This step has already been completed.", 409)
    return lead


def _coupon_payload(campaign, lead, promo):
    return {
        'code': promo.code,
        'label': lead.prize.label if lead.prize else None,
        'discount_type': promo.discount_type.value,
        'discount_value': float(promo.discount_value),
        'valid_until': promo.end_date.isoformat(),
        'terms': campaign.terms_text,
        'min_order_value': float(promo.min_order_value) if promo.min_order_value is not None else None,
        'max_discount_amount': float(promo.max_discount_amount) if promo.max_discount_amount is not None else None,
    }


# --------------------------------------------------------------------------- #
# endpoints
# --------------------------------------------------------------------------- #

def campaign_config():
    campaign = get_active_campaign()
    if not campaign:
        return {'active': False}
    # include_weights=False: the draw odds are admin data. Sending them to the browser
    # would tell a visitor exactly how the board is rigged.
    data = campaign.serialize(include_weights=False)
    data['active'] = True
    return data


def play(source_page=None, ip=None, user_agent=None, user_id=None):
    campaign = get_active_campaign()
    if not campaign:
        raise PlinkoError("No game is running right now.", 404)

    ip_hash = hash_ip(ip)
    if ip_hash and _count_today(PlinkoLead, PlinkoLead.ip_hash, ip_hash) >= PLAYS_PER_IP_PER_DAY:
        # A DB count, not the Redis rate limiter — that decorator silently no-ops when
        # Redis is down, which is exactly when someone would notice and lean on it.
        raise PlinkoError("You've played enough for today. Come back tomorrow!", 429)

    prize = _pick_prize(campaign)
    lead = PlinkoLead(
        campaign_id=campaign.campaign_id,
        prize_id=prize.prize_id,
        session_token=secrets.token_urlsafe(32)[:64],
        pending_code=_generate_code(campaign),
        status='played',
        user_id=user_id,
        source_page=(source_page or '')[:255] or None,
        ip_hash=ip_hash,
        user_agent=(user_agent or '')[:255] or None,
        expires_at=datetime.utcnow() + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    db.session.add(lead)
    db.session.commit()

    return {
        'session_token': lead.session_token,
        'slot_index': _slot_index(campaign, prize),
        'prize_label': prize.label,
        'code_length': len(lead.pending_code),
    }


def capture_email(session_token, email):
    lead = _load_lead(session_token, {'played', 'email_captured'})
    lead.email = _normalise_email(email)
    lead.status = 'email_captured'
    db.session.commit()
    return {'masked_code': mask_code(lead.pending_code)}


def claim(session_token, phone):
    # 'played' is accepted so a claim that skipped the email step reports *that*,
    # rather than the misleading "this step has already been completed".
    lead = _load_lead(session_token, {'played', 'email_captured', 'completed'})
    if not lead.email:
        raise PlinkoError("Please enter your email first.")

    campaign = PlinkoCampaign.query.get(lead.campaign_id)
    if not campaign:
        raise PlinkoError("No game is running right now.", 404)

    # Already finished — hand back the same coupon rather than minting a second one.
    if lead.status == 'completed' and lead.promotion_id:
        promo = Promotion.query.get(lead.promotion_id)
        if promo:
            return _coupon_payload(campaign, lead, promo)

    normalised_phone = _normalise_phone(phone)

    # A repeat visitor gets their existing code back. Returning it is the honest
    # answer and it is idempotent; erroring would just teach people to use a second
    # email address.
    existing = PlinkoLead.query.filter(
        PlinkoLead.campaign_id == campaign.campaign_id,
        PlinkoLead.lead_id != lead.lead_id,
        db.or_(
            PlinkoLead.claimed_email == lead.email,
            PlinkoLead.claimed_phone == normalised_phone,
        ),
    ).first()
    if existing and existing.promotion_id:
        promo = Promotion.query.get(existing.promotion_id)
        if promo and promo.end_date >= business_today():
            return _coupon_payload(campaign, existing, promo)
        raise PlinkoError(
            "You've already claimed a code for this campaign.", 409
        )

    ip_hash = lead.ip_hash
    if ip_hash and _count_today(PlinkoLead, PlinkoLead.ip_hash, ip_hash) > CLAIMS_PER_IP_PER_DAY * 5:
        raise PlinkoError("Too many claims from this connection today.", 429)

    if _minted_today() >= (campaign.daily_mint_ceiling or 0):
        raise PlinkoError(
            "Today's rewards have all been claimed. Please come back tomorrow!", 429
        )

    prize = lead.prize
    if not prize or prize.discount_value is None:
        raise PlinkoError("This game is not available right now.", 503)

    today = business_today()
    promo = _mint_promotion(campaign, lead, prize, today)

    lead.promotion_id = promo.promotion_id
    lead.phone = normalised_phone
    lead.claimed_email = lead.email
    lead.claimed_phone = normalised_phone
    lead.status = 'completed'
    lead.coupon_revealed_at = datetime.utcnow()
    try:
        db.session.commit()
    except IntegrityError:
        # Lost a race on claimed_email/claimed_phone against a concurrent claim.
        db.session.rollback()
        raise PlinkoError("You've already claimed a code for this campaign.", 409)

    return _coupon_payload(campaign, lead, promo)


def _mint_promotion(campaign, lead, prize, today):
    """Insert the coupon, retrying on a code collision.

    Insert-and-catch rather than check-then-insert: promotions.code is UNIQUE, and a
    "does this exist?" query followed by an insert is a race that collides under
    concurrency. The retry regenerates only the random tail.
    """
    discount_type = (
        DiscountType.PERCENTAGE if (prize.discount_type or 'percentage') == 'percentage'
        else DiscountType.FIXED
    )
    for attempt in range(MAX_CODE_ATTEMPTS):
        code = lead.pending_code if attempt == 0 else _generate_code(campaign)
        promo = Promotion(
            code=code,
            description=f"{prize.label} — {campaign.name}",
            discount_type=discount_type,
            discount_value=Decimal(prize.discount_value),
            start_date=today,
            end_date=today + timedelta(days=max(int(campaign.validity_days or 1) - 1, 0)),
            active_flag=True,
            min_order_value=campaign.min_order_value,
            max_discount_amount=campaign.max_discount_amount,
            restricted_to_email=lead.email,
            lead_id=lead.lead_id,
            source='plinko',
        )
        db.session.add(promo)
        try:
            db.session.flush()
            lead.pending_code = code
            return promo
        except IntegrityError:
            db.session.rollback()
            current_app.logger.warning("Plinko code collision on %s, retrying", code)
    raise PlinkoError("Could not issue a code right now. Please try again.", 503)
