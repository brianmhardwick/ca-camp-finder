from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    pushover_user_key: str = ""
    pushover_api_token: str = ""
    database_url: str = "sqlite:////data/campfinder.db"
    default_check_interval: int = 60  # minutes
    peak_window_interval: int = 15  # minutes during peak cancellation windows
    log_level: str = "INFO"
    # How many days ahead to scan for Fri/Sat/Sun availability
    scan_days_ahead: int = 90


settings = Settings()
