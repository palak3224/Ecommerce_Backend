"""The storefront lead-capture game.

The load-bearing assertion in this file is that the full coupon code does not leave the
server until the phone number arrives. Everything else — the funnel, the dedupe, the
ceiling — is protecting revenue; that one is protecting the premise of the feature.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app import create_app
from common.database import db


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _mk_campaign(active=True, ceiling=500, min_order=None, cap=None, validity_days=1):
    from models.plinko import PlinkoCampaign, PlinkoPrize

    campaign = PlinkoCampaign(
        name="Launch Week",
        is_active=active,
        headline="Tap to drop",
        terms_text="Valid on today's order only.",
        coupon_prefix="PLK",
        validity_days=validity_days,
        min_order_value=Decimal(min_order) if min_order else None,
        max_discount_amount=Decimal(cap) if cap else None,
        daily_mint_ceiling=ceiling,
    )
    db.session.add(campaign)
    db.session.flush()

    slots = [
        ("15% back", "coupon", "percentage", "15.00", 10, 0),
        ("Try again", "decoy", None, None, 0, 1),
        ("Free gift", "decoy", None, None, 0, 2),
        ("10% back", "coupon", "percentage", "10.00", 30, 3),
        ("5% back", "coupon", "percentage", "5.00", 60, 4),
    ]
    for label, kind, dtype, value, weight, order in slots:
        db.session.add(PlinkoPrize(
            campaign_id=campaign.campaign_id, label=label, slot_kind=kind,
            discount_type=dtype,
            discount_value=Decimal(value) if value else None,
            weight=weight, display_order=order,
        ))
    db.session.commit()
    return campaign


def _play(client):
    r = client.post('/api/plinko/play', json={'source_page': '/'})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


# --------------------------------------------------------------------------- #

def test_campaign_config_never_leaks_the_draw_weights(app, client):
    """A visitor who can read the weights knows exactly how the board is rigged."""
    _mk_campaign()
    body = client.get('/api/plinko/campaign').get_json()

    assert body['active'] is True
    assert body['headline'] == 'Tap to drop'
    assert len(body['prizes']) == 5
    for prize in body['prizes']:
        assert 'weight' not in prize
        assert 'discount_value' not in prize


def test_no_active_campaign_reports_inactive_rather_than_erroring(app, client):
    _mk_campaign(active=False)
    assert client.get('/api/plinko/campaign').get_json() == {'active': False}


def test_play_returns_a_slot_but_never_a_code(app, client):
    from models.promotion import Promotion

    _mk_campaign()
    body = _play(client)

    assert 'session_token' in body
    assert isinstance(body['slot_index'], int)
    assert 'code' not in body
    assert 'pending_code' not in body
    assert 'masked_code' not in body
    # And nothing has been minted yet — playing costs nothing.
    assert Promotion.query.count() == 0


def test_everyone_wins_a_real_coupon_slot(app, client):
    """Decoy slots are rendered but never drawn, which is what makes the promise true."""
    from models.plinko import PlinkoLead

    _mk_campaign()
    # Under the per-IP daily play cap, which is exercised separately below.
    for _ in range(15):
        body = _play(client)
        lead = PlinkoLead.query.filter_by(session_token=body['session_token']).first()
        assert lead.prize.slot_kind == 'coupon'
        assert lead.prize.discount_value is not None


def test_email_reveals_only_half_the_code(app, client):
    from models.plinko import PlinkoLead
    from models.promotion import Promotion

    _mk_campaign()
    played = _play(client)

    r = client.post('/api/plinko/reveal', json={
        'session_token': played['session_token'], 'email': 'Lead@Example.com',
    })
    assert r.status_code == 200
    masked = r.get_json()['masked_code']

    lead = PlinkoLead.query.filter_by(session_token=played['session_token']).first()
    real = lead.pending_code

    # Half shown, half hidden, and the hidden half is genuinely absent from the payload.
    shown = len(real) // 2
    assert masked.startswith(real[:shown])
    assert masked.count('•') == len(real) - shown
    assert real not in masked
    assert real[shown:] not in masked
    # Email is normalised, and still no coupon exists.
    assert lead.email == 'lead@example.com'
    assert Promotion.query.count() == 0


def test_phone_mints_the_coupon_with_the_campaign_rules(app, client):
    from models.promotion import Promotion
    from services.promotion_service import business_today

    _mk_campaign(min_order="500.00", cap="200.00")
    played = _play(client)
    client.post('/api/plinko/reveal', json={
        'session_token': played['session_token'], 'email': 'lead@example.com'})

    r = client.post('/api/plinko/claim', json={
        'session_token': played['session_token'], 'phone': '98765 43210'})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()

    promo = Promotion.query.one()
    assert body['code'] == promo.code
    assert '•' not in body['code']
    assert body['terms'] == "Valid on today's order only."
    # Rules come from the campaign, never from the request.
    assert promo.min_order_value == Decimal("500.00")
    assert promo.max_discount_amount == Decimal("200.00")
    assert promo.restricted_to_email == 'lead@example.com'
    assert promo.source == 'plinko'
    # validity_days=1 means today only.
    assert promo.start_date == business_today()
    assert promo.end_date == business_today()


def test_claim_without_an_email_is_refused(app, client):
    _mk_campaign()
    played = _play(client)
    r = client.post('/api/plinko/claim', json={
        'session_token': played['session_token'], 'phone': '9876543210'})
    assert r.status_code == 400
    assert 'email' in r.get_json()['error'].lower()


def test_a_bad_phone_number_is_refused(app, client):
    _mk_campaign()
    played = _play(client)
    client.post('/api/plinko/reveal', json={
        'session_token': played['session_token'], 'email': 'lead@example.com'})
    r = client.post('/api/plinko/claim', json={
        'session_token': played['session_token'], 'phone': '12345'})
    assert r.status_code == 400


def test_a_forged_session_token_gets_nothing(app, client):
    _mk_campaign()
    r = client.post('/api/plinko/reveal', json={
        'session_token': 'not-a-real-token', 'email': 'lead@example.com'})
    assert r.status_code == 404


def test_replaying_the_claim_returns_the_same_coupon(app, client):
    """Idempotent, not an error — a refresh must not mint a second code."""
    from models.promotion import Promotion

    _mk_campaign()
    played = _play(client)
    client.post('/api/plinko/reveal', json={
        'session_token': played['session_token'], 'email': 'lead@example.com'})

    first = client.post('/api/plinko/claim', json={
        'session_token': played['session_token'], 'phone': '9876543210'}).get_json()
    second = client.post('/api/plinko/claim', json={
        'session_token': played['session_token'], 'phone': '9876543210'}).get_json()

    assert first['code'] == second['code']
    assert Promotion.query.count() == 1


def test_the_same_email_cannot_farm_a_second_coupon(app, client):
    from models.promotion import Promotion

    _mk_campaign()
    for _ in range(2):
        played = _play(client)
        client.post('/api/plinko/reveal', json={
            'session_token': played['session_token'], 'email': 'repeat@example.com'})
        r = client.post('/api/plinko/claim', json={
            'session_token': played['session_token'], 'phone': '9876543210'})
        assert r.status_code == 200, r.get_json()

    # Second attempt handed back the first code rather than minting another.
    assert Promotion.query.count() == 1


def test_the_daily_mint_ceiling_bounds_the_liability(app, client):
    """The circuit breaker: worst-case daily cost is ceiling x max discount, agreed
    in advance rather than discovered."""
    from models.promotion import Promotion

    _mk_campaign(ceiling=1)

    for i, email in enumerate(['a@example.com', 'b@example.com']):
        played = _play(client)
        client.post('/api/plinko/reveal', json={
            'session_token': played['session_token'], 'email': email})
        r = client.post('/api/plinko/claim', json={
            'session_token': played['session_token'],
            'phone': f'98765432{i}0'})
        if i == 0:
            assert r.status_code == 200
        else:
            assert r.status_code == 429
            assert 'tomorrow' in r.get_json()['error'].lower()

    assert Promotion.query.count() == 1


def test_the_minted_coupon_actually_works_at_checkout(app, client):
    """The end of the funnel: a code the game issued must price a real basket."""
    from services.promotion_service import resolve_promotion
    from models.promotion import Promotion

    _mk_campaign(min_order="100.00")
    played = _play(client)
    client.post('/api/plinko/reveal', json={
        'session_token': played['session_token'], 'email': 'buyer@example.com'})
    code = client.post('/api/plinko/claim', json={
        'session_token': played['session_token'], 'phone': '9876543210'}).get_json()['code']

    class _U:
        email = 'buyer@example.com'

    ok = resolve_promotion(code, user=_U(), basket_total_inclusive=Decimal("500.00"))
    assert ok.ok is True

    # And the campaign minimum is enforced on the way in.
    too_small = resolve_promotion(code, user=_U(), basket_total_inclusive=Decimal("50.00"))
    assert too_small.reason_code == 'BELOW_MIN_ORDER'


def test_per_ip_play_cap_holds_without_redis(app, client):
    """@rate_limit silently no-ops when Redis is down, so the real cap is a DB count.
    This suite runs with no Redis, which is the point."""
    from controllers.plinko_controller import PLAYS_PER_IP_PER_DAY

    _mk_campaign()
    for _ in range(PLAYS_PER_IP_PER_DAY):
        assert client.post('/api/plinko/play', json={}).status_code == 201

    blocked = client.post('/api/plinko/play', json={})
    assert blocked.status_code == 429


# --------------------------------------------------------------------------- #
# superadmin campaign editing
#
# These enable SQLite's foreign key enforcement explicitly. It is off by default,
# which is exactly why the delete-and-recreate bug below reached production: the
# suite passed while MySQL rejected every save.
# --------------------------------------------------------------------------- #

def _enforce_foreign_keys():
    db.session.execute(db.text('PRAGMA foreign_keys=ON'))


def test_campaign_saves_after_someone_has_played(app):
    """The regression: plinko_leads.prize_id references the prize rows, so wiping
    and re-inserting them made every save fail once the game had been played."""
    from controllers.superadmin.plinko_admin_controller import PlinkoAdminController
    from models.plinko import PlinkoCampaign, PlinkoLead, PlinkoPrize

    campaign = _mk_campaign()
    _enforce_foreign_keys()

    prize = PlinkoPrize.query.filter_by(campaign_id=campaign.campaign_id).first()
    db.session.add(PlinkoLead(campaign_id=campaign.campaign_id, prize_id=prize.prize_id,
                              session_token='tok-played', status='played'))
    db.session.commit()

    payload = campaign.serialize(include_weights=True)
    payload['headline'] = 'Tap to drop!'
    saved = PlinkoAdminController.save_campaign(payload, campaign_id=campaign.campaign_id)

    assert saved['headline'] == 'Tap to drop!'
    assert PlinkoCampaign.query.count() == 1


def test_editing_prizes_updates_them_in_place(app):
    """Prize ids must be stable across a save, or every past lead loses its prize."""
    from controllers.superadmin.plinko_admin_controller import PlinkoAdminController
    from models.plinko import PlinkoPrize

    campaign = _mk_campaign()
    _enforce_foreign_keys()
    before = {p.prize_id for p in PlinkoPrize.query.filter_by(
        campaign_id=campaign.campaign_id).all()}

    payload = campaign.serialize(include_weights=True)
    payload['prizes'][0]['label'] = '25% back'
    payload['prizes'][0]['discount_value'] = 25
    PlinkoAdminController.save_campaign(payload, campaign_id=campaign.campaign_id)

    after = {p.prize_id for p in PlinkoPrize.query.filter_by(
        campaign_id=campaign.campaign_id).all()}
    assert after == before

    updated = PlinkoPrize.query.get(payload['prizes'][0]['prize_id'])
    assert updated.label == '25% back'
    assert updated.discount_value == Decimal('25')


def test_removing_a_slot_deactivates_rather_than_deletes(app):
    """A removed slot has to survive as a row: leads point at it, and the leads panel
    reports which prize each one won."""
    from controllers.superadmin.plinko_admin_controller import PlinkoAdminController
    from models.plinko import PlinkoLead, PlinkoPrize

    campaign = _mk_campaign()
    _enforce_foreign_keys()

    doomed = PlinkoPrize.query.filter_by(
        campaign_id=campaign.campaign_id, label='5% back').first()
    db.session.add(PlinkoLead(campaign_id=campaign.campaign_id, prize_id=doomed.prize_id,
                              session_token='tok-old', status='completed'))
    db.session.commit()
    doomed_id = doomed.prize_id

    payload = campaign.serialize(include_weights=True)
    payload['prizes'] = [p for p in payload['prizes'] if p['label'] != '5% back']
    PlinkoAdminController.save_campaign(payload, campaign_id=campaign.campaign_id)

    still_there = PlinkoPrize.query.get(doomed_id)
    assert still_there is not None
    assert still_there.is_active is False

    # Gone from the storefront, and the old lead still resolves its prize.
    labels = [p['label'] for p in campaign.serialize()['prizes']]
    assert '5% back' not in labels
    lead = PlinkoLead.query.filter_by(session_token='tok-old').first()
    assert lead.prize.label == '5% back'


def test_a_new_slot_is_added_without_touching_the_others(app):
    from controllers.superadmin.plinko_admin_controller import PlinkoAdminController
    from models.plinko import PlinkoPrize

    campaign = _mk_campaign()
    _enforce_foreign_keys()
    before = PlinkoPrize.query.filter_by(campaign_id=campaign.campaign_id).count()

    payload = campaign.serialize(include_weights=True)
    payload['prizes'].append({
        'label': '20% back', 'slot_kind': 'coupon', 'discount_type': 'percentage',
        'discount_value': 20, 'weight': 5, 'display_order': 9, 'is_active': True,
    })
    PlinkoAdminController.save_campaign(payload, campaign_id=campaign.campaign_id)

    assert PlinkoPrize.query.filter_by(campaign_id=campaign.campaign_id).count() == before + 1
    added = PlinkoPrize.query.filter_by(label='20% back').first()
    assert added.discount_value == Decimal('20')
