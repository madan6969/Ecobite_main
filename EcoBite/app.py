import os
from flask import Flask

from routes_pages import register_pages
from routes_claims import register_claim_routes
from routes_api import register_api_routes

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

    # Register all route groups
    register_pages(app)
    register_claim_routes(app)
    register_api_routes(app)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

