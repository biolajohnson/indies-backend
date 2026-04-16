from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Campaign, CampaignUpdate, Filmmaker

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/api/campaigns")


@campaigns_bp.route("/", methods=["GET"])
def list_campaigns():
    """
    Return all active campaigns.
    Optional query params:
      ?status=active|draft|funded|closed  (default: active)
      ?genre=sci-fi
      ?filmmaker_id=1
    """
    status = request.args.get("status", Campaign.STATUS_ACTIVE)
    genre = request.args.get("genre")
    filmmaker_id = request.args.get("filmmaker_id", type=int)

    query = Campaign.query

    if status:
        query = query.filter_by(status=status)
    if genre:
        query = query.filter(Campaign.genre.ilike(f"%{genre}%"))
    if filmmaker_id:
        query = query.filter_by(filmmaker_id=filmmaker_id)

    campaigns = query.order_by(Campaign.created_at.desc()).all()
    return jsonify([c.to_dict() for c in campaigns]), 200


@campaigns_bp.route("/<int:campaign_id>", methods=["GET"])
def get_campaign(campaign_id):
    """Return a single campaign with donations and updates."""
    campaign = db.session.get(Campaign, campaign_id)

    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    return jsonify(campaign.to_dict(include_donations=True, include_updates=True)), 200


@campaigns_bp.route("/", methods=["POST"])
@jwt_required()
def create_campaign():
    """Create a new campaign. Requires authentication."""
    filmmaker_id = int(get_jwt_identity())
    filmmaker = db.session.get(Filmmaker, filmmaker_id)

    if not filmmaker:
        return jsonify({"error": "Filmmaker not found"}), 404

    data = request.get_json()

    required = ["title", "description", "goal_amount"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        goal = float(data["goal_amount"])
        if goal <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "goal_amount must be a positive number"}), 400

    campaign = Campaign(
        filmmaker_id=filmmaker_id,
        title=data["title"],
        description=data["description"],
        short_description=data.get("short_description"),
        goal_amount=goal,
        video_url=data.get("video_url"),
        thumbnail_url=data.get("thumbnail_url"),
        genre=data.get("genre"),
        tags=data.get("tags", []),
        status=Campaign.STATUS_DRAFT,
    )

    if data.get("deadline"):
        from datetime import datetime
        try:
            campaign.deadline = datetime.fromisoformat(data["deadline"])
        except ValueError:
            return jsonify({"error": "deadline must be an ISO 8601 date string"}), 400

    db.session.add(campaign)
    db.session.commit()

    return jsonify(campaign.to_dict()), 201


@campaigns_bp.route("/<int:campaign_id>", methods=["PATCH"])
@jwt_required()
def update_campaign(campaign_id):
    """Update a campaign. Only the owning filmmaker can edit."""
    filmmaker_id = int(get_jwt_identity())
    campaign = db.session.get(Campaign, campaign_id)

    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if campaign.filmmaker_id != filmmaker_id:
        return jsonify({"error": "You do not have permission to edit this campaign"}), 403

    data = request.get_json()
    allowed_fields = [
        "title", "description", "short_description", "goal_amount",
        "video_url", "thumbnail_url", "genre", "tags", "status", "deadline",
    ]

    if "status" in data and data["status"] not in Campaign.VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {Campaign.VALID_STATUSES}"}), 400

    for field in allowed_fields:
        if field in data:
            setattr(campaign, field, data[field])

    db.session.commit()
    return jsonify(campaign.to_dict()), 200


@campaigns_bp.route("/<int:campaign_id>", methods=["DELETE"])
@jwt_required()
def delete_campaign(campaign_id):
    """Delete a campaign (only drafts can be deleted)."""
    filmmaker_id = int(get_jwt_identity())
    campaign = db.session.get(Campaign, campaign_id)

    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if campaign.filmmaker_id != filmmaker_id:
        return jsonify({"error": "You do not have permission to delete this campaign"}), 403

    if campaign.status != Campaign.STATUS_DRAFT:
        return jsonify({"error": "Only draft campaigns can be deleted"}), 400

    db.session.delete(campaign)
    db.session.commit()
    return jsonify({"message": "Campaign deleted"}), 200


# --- Campaign Updates ---

@campaigns_bp.route("/<int:campaign_id>/updates", methods=["POST"])
@jwt_required()
def post_update(campaign_id):
    """Post an update to a campaign. Only the owning filmmaker can post."""
    filmmaker_id = int(get_jwt_identity())
    campaign = db.session.get(Campaign, campaign_id)

    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404

    if campaign.filmmaker_id != filmmaker_id:
        return jsonify({"error": "You do not have permission to post updates for this campaign"}), 403

    data = request.get_json()
    if not data.get("title") or not data.get("body"):
        return jsonify({"error": "title and body are required"}), 400

    update = CampaignUpdate(
        campaign_id=campaign_id,
        title=data["title"],
        body=data["body"],
    )
    db.session.add(update)
    db.session.commit()

    return jsonify(update.to_dict()), 201
