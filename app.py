import os
from flask import Flask, send_file, Response, jsonify
from config import config
from extensions import db, migrate, jwt, cors


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # Register blueprints
    from routes.auth import auth_bp
    from routes.filmmakers import filmmakers_bp
    from routes.campaigns import campaigns_bp
    from routes.donations import donations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(filmmakers_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(donations_bp)

    # --- Legacy video routes (kept for compatibility) ---
    def generate():
        video_path = "data/sample.mp4"
        with open(video_path, "rb") as video_file:
            while chunk := video_file.read(4096):
                yield chunk

    @app.route("/api/video")
    def get_video():
        video_path = "data/sample.mp4"
        return send_file(video_path, mimetype="video/mp4")

    @app.route("/api/video/stream")
    def stream_video():
        return Response(generate(), mimetype="video/mp4")

    # --- Health check ---
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "env": config_name}), 200

    # --- JWT error handlers ---
    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        return jsonify({"error": "Authorization token is missing or invalid"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired. Please log in again."}), 401

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
