from flask import Flask

from flask_api.config import Config
from flask_api.extensions import db
from flask_api.api import api_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # endpointy pod /api/...
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
