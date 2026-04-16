from flask import Blueprint, jsonify
from extensions import db
from models import Filmmaker

filmmakers_bp = Blueprint("filmmakers", __name__, url_prefix="/api/filmmakers")


@filmmakers_bp.route("/", methods=["GET"])
def list_filmmakers():
    """Return all filmmaker profiles (public info only)."""
    filmmakers = Filmmaker.query.order_by(Filmmaker.created_at.desc()).all()
    return jsonify([f.to_dict() for f in filmmakers]), 200


@filmmakers_bp.route("/<int:filmmaker_id>", methods=["GET"])
def get_filmmaker(filmmaker_id):
    """Return a single filmmaker profile with their campaigns."""
    filmmaker = db.session.get(Filmmaker, filmmaker_id)

    if not filmmaker:
        return jsonify({"error": "Filmmaker not found"}), 404

    return jsonify(filmmaker.to_dict()), 200
