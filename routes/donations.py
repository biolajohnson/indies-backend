from flask import Blueprint, request, jsonify, current_app
from extensions import db
from models import Campaign, Donation

donations_bp = Blueprint("donations", __name__, url_prefix="/api/donations")


@donations_bp.route("/", methods=["POST"])
def create_donation():
    """
    Create a donation for a campaign.
    For now: records the donation directly (no real payment yet).
    Phase 2 will replace this with Stripe PaymentIntent creation.
    """
    data = request.get_json()

    required = ["campaign_id", "donor_email", "amount"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    campaign = db.session.get(Campaign, data["campaign_id"])
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if campaign.status != Campaign.STATUS_ACTIVE:
        return jsonify({"error": "This campaign is not currently accepting donations"}), 400

    try:
        amount = float(data["amount"])
        if amount < 1.00:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be at least $1.00"}), 400

    donation = Donation(
        campaign_id=campaign.id,
        donor_email=data["donor_email"].lower(),
        donor_name=data.get("donor_name"),
        amount=amount,
        message=data.get("message"),
        is_anonymous=data.get("is_anonymous", False),
    )

    # Update campaign total
    campaign.current_amount = float(campaign.current_amount) + amount

    # Auto-mark as funded if goal is reached
    if float(campaign.current_amount) >= float(campaign.goal_amount):
        campaign.status = Campaign.STATUS_FUNDED

    db.session.add(donation)
    db.session.commit()

    return jsonify({
        "message": "Thank you for your donation!",
        "donation": donation.to_dict(),
        "campaign": campaign.to_dict(),
    }), 201


@donations_bp.route("/campaign/<int:campaign_id>", methods=["GET"])
def get_campaign_donations(campaign_id):
    """Return public donation list for a campaign."""
    campaign = db.session.get(Campaign, campaign_id)

    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    donations = (
        Donation.query
        .filter_by(campaign_id=campaign_id)
        .order_by(Donation.created_at.desc())
        .all()
    )

    return jsonify([d.to_dict() for d in donations]), 200
