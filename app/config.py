from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///phy_analyzer.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
    RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "api-football-v1.p.rapidapi.com")
    API_FOOTBALL_BASE = os.getenv(
        "API_FOOTBALL_BASE", "https://api-football-v1.p.rapidapi.com/v3"
    )

    TIMEZONE = os.getenv("TIMEZONE", "Africa/Lagos")
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.62"))
    MAX_DAILY_PICKS = int(os.getenv("MAX_DAILY_PICKS", "5"))
    MAX_COMBINED_ODDS = float(os.getenv("MAX_COMBINED_ODDS", "5.0"))

    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

    # Phase 5 scheduler: off by default so `flask run --debug` reloads and
    # pytest runs don't accidentally hit RapidAPI. Flip to 1 in production.
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "0") == "1"
