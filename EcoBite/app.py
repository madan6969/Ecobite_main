import os
from dotenv import load_dotenv
from flask import Flask, send_from_directory

from routes_pages import register_pages
from routes_api import register_api_routes
from routes_claims import register_claim_routes

load_dotenv()

# Folder where uploaded images are stored (relative to project root)
UPLOAD_FOLDER = "uploads"


def create_app():
    # Point to your existing folders
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Secret key from .env or a fallback for local dev
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

    # Ensure uploads folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

    # Register route groups
    register_pages(app)
    register_api_routes(app)
    register_claim_routes(app)

    # Serve uploaded files (e.g. images)
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    return app


# WSGI entrypoint
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
