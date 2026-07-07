from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_path: str = "/data/baller.db"
    image_cache_dir: str = "/data/images"
    tm_api_base_url: str = "http://transfermarkt-api:8000"
    # Politeness throttle toward the scraper API (it hits transfermarkt.de per request).
    tm_min_request_interval: float = 2.5
    # The image CDN is not the scraped site; a lighter throttle is enough.
    tm_cdn_min_request_interval: float = 0.5
    ingest_config: str = "/app/app/ingest/config/competitions.yml"
    daily_salt: str = "baller-connections"
    daily_refresh_hour_utc: int = 4


settings = Settings()
