from flask import Blueprint, jsonify
from extensions import db
from models import Campaign, Donation

donations_bp = Blueprint("donations", __name__, url_prefix="/api/donations")


@donations_bp.route("/campaign/<int:campaign_id>", methods=["GET"])
def get_campaign_donations(campaign_id):
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
