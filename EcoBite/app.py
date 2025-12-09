# app.py

import os
from dotenv import load_dotenv
from flask import Flask

# Our route modules expose register_* functions, not blueprints
from routes_pages import register_pages
from routes_api import register_api_routes
from routes_claims import register_claim_routes

load_dotenv()


def create_app():
    app = Flask(__name__)

    # Secret key from env (Render/Railway) or fallback for local dev
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

    # Register all routes on this app
    register_pages(app)
    register_api_routes(app)
    register_claim_routes(app)

    return app


# For Render / Gunicorn entry point
app = create_app()

if __name__ == "__main__":
    # Local dev
    app.run(debug=True)
