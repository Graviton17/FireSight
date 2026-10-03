from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FireSight API"
    app_version: str = "0.1.0"
    api_key: str = "dev-only-change-me"
    database_url: str = "sqlite+aiosqlite:///./data/firesight.db"
    data_dir: str = "./data"
    cors_origins: str = "http://localhost:5173"
    camera_mode: str = "blank"
    camera_url: str = ""
    detector: str = "stub"
    model_path: str = "./models/fire_smoke.pt"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
