import os
import uuid
import threading
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Campaign, CampaignUpdate, Filmmaker
from transcoding import worker as transcoding_worker

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'avi'}

def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

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


@campaigns_bp.route("/<int:campaign_id>/video", methods=["PATCH"])
@jwt_required()
def upload_video(campaign_id):
    filmmaker_id = int(get_jwt_identity())
    campaign = db.session.get(Campaign, campaign_id)

    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    if campaign.filmmaker_id != filmmaker_id:
        return jsonify({"error": "You do not have permission to upload video for this campaign"}), 403

    file = request.files.get("video")
    if not file:
        return jsonify({"error": "No video file provided"}), 400
    if not allowed_video(file.filename):
        return jsonify({"error": "Unsupported file type. Use mp4, mov, webm, or avi."}), 400

    # Save the raw upload to a temp location — worker deletes it after transcoding.
    upload_dir = os.path.join(current_app.root_path, "uploads", "videos")
    os.makedirs(upload_dir, exist_ok=True)

    slug = uuid.uuid4().hex
    ext = file.filename.rsplit('.', 1)[1].lower()
    raw_path = os.path.join(upload_dir, f"{slug}_raw.{ext}")
    hls_dir = os.path.join(upload_dir, slug)
    file.save(raw_path)

    # Mark processing immediately so the frontend can start polling.
    campaign.video_url = None
    campaign.video_status = Campaign.VIDEO_STATUS_PROCESSING
    db.session.commit()

    # Kick off the transcoding pipeline in a background thread.
    # The thread needs the Flask app object to push an app context —
    # current_app is a proxy and can't be passed directly.
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=transcoding_worker.run,
        args=(app, campaign_id, raw_path, hls_dir),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": Campaign.VIDEO_STATUS_PROCESSING}), 202


@campaigns_bp.route("/<int:campaign_id>/video/status", methods=["GET"])
def video_status(campaign_id):
    campaign = db.session.get(Campaign, campaign_id)
    if not campaign:
        return jsonify({"error": "Campaign not found"}), 404
    return jsonify({
        "status": campaign.video_status,
        "video_url": campaign.video_url,
    }), 200


@campaigns_bp.route("/videos/<path:filename>", methods=["GET"])
def serve_video(filename):
    upload_dir = os.path.join(current_app.root_path, "uploads", "videos")
    return send_from_directory(upload_dir, filename)
