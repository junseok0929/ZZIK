from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', case_sensitive=False)
    database_url: str = 'postgresql+psycopg://moacut:moacut@localhost:5432/moacut'
    storage_backend: str = 'local'
    storage_root: str = './data/storage'
    face_analysis_provider: str = 'fixture'
    fixture_manifest: str = './backend/fixtures/manifest.json'
    demo_enabled: bool = True
    session_cookie: str = 'moacut_session'
    session_days: int = 14
    cookie_secure: bool = False
    allowed_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080'
    max_upload_bytes: int = 25 * 1024 * 1024
    max_image_pixels: int = 50_000_000
    aws_region: str = 'ap-northeast-2'
    s3_bucket: str = ''
    s3_prefix: str = 'moacut/'
    rekognition_similarity_threshold: float = 90.0
    rekognition_candidate_margin: float = 5.0
    rekognition_collection_prefix: str = 'moacut-'
    worker_concurrency: int = 2
    worker_max_attempts: int = 3
    worker_lease_seconds: int = 120
    worker_poll_seconds: float = 2.0
    aws_timeout_seconds: int = 20
    geocoding_url: str = ''
    geocoding_user_agent: str = 'MoaCut/1.0'

settings = Settings()
