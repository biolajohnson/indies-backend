import stripe
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Filmmaker, Campaign, Donation

stripe_bp = Blueprint("stripe", __name__, url_prefix="/api/stripe")


def get_stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    return stripe


# ---------------------------------------------------------------------------
# Filmmaker onboarding — creates a Stripe Connect Express account
# ---------------------------------------------------------------------------

@stripe_bp.route("/onboard", methods=["POST"])
@jwt_required()
def onboard():
    filmmaker_id = int(get_jwt_identity())
    filmmaker = db.session.get(Filmmaker, filmmaker_id)
    if not filmmaker:
        return jsonify({"error": "Filmmaker not found"}), 404

    s = get_stripe()

    # Create a Connect Express account if the filmmaker doesn't have one yet
    if not filmmaker.stripe_account_id:
        account = s.Account.create(
            type="express",
            email=filmmaker.email,
            capabilities={"transfers": {"requested": True}},
        )
        filmmaker.stripe_account_id = account.id
        db.session.commit()

    # Generate an onboarding link (expires after use or 24 hours)
    link = s.AccountLink.create(
        account=filmmaker.stripe_account_id,
        refresh_url=f"{current_app.config['FRONTEND_URL']}/onboard/refresh",
        return_url=f"{current_app.config['FRONTEND_URL']}/onboard/complete",
        type="account_onboarding",
    )

    return jsonify({"url": link.url}), 200


@stripe_bp.route("/onboard/status", methods=["GET"])
@jwt_required()
def onboard_status():
    filmmaker_id = int(get_jwt_identity())
    filmmaker = db.session.get(Filmmaker, filmmaker_id)
    if not filmmaker or not filmmaker.stripe_account_id:
        return jsonify({"onboarded": False}), 200

    s = get_stripe()
    account = s.Account.retrieve(filmmaker.stripe_account_id)
    onboarded = account.details_submitted

    if onboarded and not filmmaker.stripe_onboarded:
        filmmaker.stripe_onboarded = True
        db.session.commit()

    return jsonify({"onboarded": onboarded}), 200


# ---------------------------------------------------------------------------
# Create a PaymentIntent — called by the frontend before rendering Stripe Elements
# ---------------------------------------------------------------------------

@stripe_bp.route("/create-payment-intent", methods=["POST"])
def create_payment_intent():
    data = request.get_json()

    required = ["campaign_id", "amount"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    campaign = db.session.get(Campaign, data["campaign_id"])
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if campaign.status != Campaign.STATUS_ACTIVE:
        return jsonify({"error": "This campaign is not currently accepting donations"}), 400

    filmmaker = db.session.get(Filmmaker, campaign.filmmaker_id)
    if not filmmaker or not filmmaker.stripe_onboarded or not filmmaker.stripe_account_id:
        return jsonify({"error": "This filmmaker has not completed Stripe onboarding"}), 400

    try:
        amount_dollars = float(data["amount"])
        if amount_dollars < 1.00:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be at least $1.00"}), 400

    amount_cents = int(amount_dollars * 100)
    fee_percent = current_app.config.get("PLATFORM_FEE_PERCENT", 7.0)
    platform_fee_cents = int(amount_cents * fee_percent / 100)

    s = get_stripe()
    intent = s.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        application_fee_amount=platform_fee_cents,
        transfer_data={"destination": filmmaker.stripe_account_id},
        metadata={
            "campaign_id": campaign.id,
            "donor_email": data.get("donor_email", ""),
            "donor_name": data.get("donor_name", ""),
            "message": data.get("message", ""),
            "is_anonymous": str(data.get("is_anonymous", False)),
        },
    )

    return jsonify({"client_secret": intent.client_secret}), 200


# ---------------------------------------------------------------------------
# Webhook — Stripe calls this when payment_intent.succeeded fires
# ---------------------------------------------------------------------------

@stripe_bp.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")

    s = get_stripe()

    if webhook_secret and webhook_secret != "whsec_...":
        try:
            event = s.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            return jsonify({"error": str(e)}), 400
    else:
        # No webhook secret configured — accept without verification (dev only)
        import json
        event = json.loads(payload)

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        _handle_payment_succeeded(intent)

    return jsonify({"status": "ok"}), 200


def _handle_payment_succeeded(intent):
    meta = intent.get("metadata", {})
    campaign_id = meta.get("campaign_id")
    if not campaign_id:
        return

    campaign = db.session.get(Campaign, int(campaign_id))
    if not campaign:
        return

    # Idempotency: skip if we already recorded this payment
    existing = Donation.query.filter_by(stripe_payment_intent_id=intent["id"]).first()
    if existing:
        return

    amount_dollars = intent["amount"] / 100

    donation = Donation(
        campaign_id=campaign.id,
        donor_email=meta.get("donor_email", "unknown@example.com"),
        donor_name=meta.get("donor_name") or None,
        amount=amount_dollars,
        message=meta.get("message") or None,
        is_anonymous=meta.get("is_anonymous", "False") == "True",
        stripe_payment_intent_id=intent["id"],
    )

    campaign.current_amount = float(campaign.current_amount) + amount_dollars
    if float(campaign.current_amount) >= float(campaign.goal_amount):
        campaign.status = Campaign.STATUS_FUNDED

    db.session.add(donation)
    db.session.commit()
