from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass
class Settings:
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", "").strip())
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./data/codemri.db")
    )
    github_api_base: str = "https://api.github.com"
    npm_registry_base: str = "https://registry.npmjs.org"
    osv_api_base: str = "https://api.osv.dev"

    max_repo_size_mb: int = field(default_factory=lambda: _int("MAX_REPO_SIZE_MB", 150))
    max_files: int = field(default_factory=lambda: _int("MAX_FILES", 20000))
    max_file_size_kb: int = field(default_factory=lambda: _int("MAX_FILE_SIZE_KB", 1024))
    max_extracted_bytes: int = 1_000_000_000
    analyzer_timeout_s: int = 120
    scan_timeout_s: int = 600

    @property
    def data_dir(self) -> Path:
        return REPO_ROOT / "data"

    @property
    def scans_dir(self) -> Path:
        return self.data_dir / "scans"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def db_path(self) -> Path:
        """Absolute path for the SQLite file when DATABASE_URL is a relative sqlite URL."""
        url = self.database_url
        prefix = "sqlite:///"
        if url.startswith(prefix):
            raw = url[len(prefix) :]
            if raw and not raw.startswith("/") and not Path(raw).is_absolute():
                return (REPO_ROOT / "services" / "analyzer" / raw).resolve()
        return Path(raw) if url.startswith(prefix) and raw else Path(url)


settings = Settings()
