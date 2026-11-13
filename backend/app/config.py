"""
App settings, read from environment variables (or a .env file).

Every setting lives here so the rest of the code never calls os.environ
directly. To change a value, edit your .env file - see .env.example.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ folder. Used to build default paths for data files.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Look for .env in backend/ first, then the repo root.
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    # --- Gnani (speech) ---
    gnani_api_key: str = ""
    tts_voice: str = "Shivani"  # any Timbre v3.0 voice works for kn-IN, hi-IN and en-IN
    tts_speed: float = 0.9  # Gnani allows 0.85 to 1.15; slightly slow suits elderly listeners
    gnani_credit_budget: int = 5000  # credits we were given for the challenge

    # --- Gemini (vision + reasoning) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"  # fast, and read all our samples correctly
    # Comma-separated. Tried in order if the main model fails. Free-tier quotas are
    # per model, so each extra model adds more free requests per day.
    gemini_fallback_models: str = "gemini-3.1-flash-lite,gemini-3-flash-preview,gemini-3.6-flash"

    # --- Local storage ---
    data_dir: Path = BACKEND_DIR / "data"  # SQLite DB + cached audio live here

    # Frontend dev server address, allowed by CORS.
    frontend_origin: str = "http://localhost:5173"

    def gemini_models(self) -> list[str]:
        """The main model followed by the fallbacks, without blanks or repeats."""
        names = [self.gemini_model, *self.gemini_fallback_models.split(",")]
        return list(dict.fromkeys(n.strip() for n in names if n.strip()))


# One shared settings object, imported everywhere as `from app.config import settings`.
settings = Settings()
