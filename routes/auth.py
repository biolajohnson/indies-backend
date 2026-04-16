from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from extensions import db
from models import Filmmaker

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new filmmaker account."""
    data = request.get_json()

    required = ["name", "email", "password"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    if Filmmaker.query.filter_by(email=data["email"].lower()).first():
        return jsonify({"error": "An account with that email already exists"}), 409

    filmmaker = Filmmaker(
        name=data["name"],
        email=data["email"].lower(),
        bio=data.get("bio"),
        nationality=data.get("nationality"),
        website=data.get("website"),
        social_links=data.get("social_links", {}),
    )
    filmmaker.set_password(data["password"])

    db.session.add(filmmaker)
    db.session.commit()

    access_token = create_access_token(identity=str(filmmaker.id))

    return jsonify({
        "message": "Account created successfully",
        "access_token": access_token,
        "filmmaker": filmmaker.to_dict(include_private=True),
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Log in and receive a JWT."""
    data = request.get_json()

    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password are required"}), 400

    filmmaker = Filmmaker.query.filter_by(email=data["email"].lower()).first()

    if not filmmaker or not filmmaker.check_password(data["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    access_token = create_access_token(identity=str(filmmaker.id))

    return jsonify({
        "access_token": access_token,
        "filmmaker": filmmaker.to_dict(include_private=True),
    }), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Return the currently authenticated filmmaker's profile."""
    filmmaker_id = int(get_jwt_identity())
    filmmaker = db.session.get(Filmmaker, filmmaker_id)

    if not filmmaker:
        return jsonify({"error": "Filmmaker not found"}), 404

    return jsonify(filmmaker.to_dict(include_private=True)), 200


@auth_bp.route("/me", methods=["PATCH"])
@jwt_required()
def update_profile():
    """Update the authenticated filmmaker's profile."""
    filmmaker_id = int(get_jwt_identity())
    filmmaker = db.session.get(Filmmaker, filmmaker_id)

    if not filmmaker:
        return jsonify({"error": "Filmmaker not found"}), 404

    data = request.get_json()
    allowed_fields = ["name", "bio", "avatar_url", "nationality", "website", "social_links"]

    for field in allowed_fields:
        if field in data:
            setattr(filmmaker, field, data[field])

    db.session.commit()
    return jsonify(filmmaker.to_dict(include_private=True)), 200
