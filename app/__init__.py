from __future__ import annotations

from flask import Flask, jsonify

from .config import Config
from .extensions import cors, db, migrate


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    from .api.analyzer import bp as analyzer_bp
    from .api.selections import bp as selections_bp
    from .api.history import bp as history_bp

    app.register_blueprint(analyzer_bp, url_prefix="/api/v1")
    app.register_blueprint(selections_bp, url_prefix="/api/v1")
    app.register_blueprint(history_bp, url_prefix="/api/v1")

    # ensure models are imported so metadata is populated for create_all
    from . import models  # noqa: F401
    from . import cli as _cli
    _cli.register(app)

    # Phase 5: start scheduler only when explicitly enabled (prod).
    from .jobs.scheduler import init_scheduler
    init_scheduler(app)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    return app
