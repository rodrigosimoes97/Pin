from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    database_url: str = os.getenv("PHA_DATABASE_URL", "sqlite:///pinterest_health_auto.db")
    pinterest_access_token: str = os.getenv("PINTEREST_ACCESS_TOKEN", "")
    pinterest_ad_account_id: str = os.getenv("PINTEREST_AD_ACCOUNT_ID", "")
    iherb_affiliate_base_url: str = os.getenv(
        "IHERB_AFFILIATE_BASE_URL", "https://www.iherb.com"
    )
    iherb_affiliate_code: str = os.getenv("IHERB_AFFILIATE_CODE", "")
    daily_pin_limit: int = int(os.getenv("DAILY_PIN_LIMIT", "10"))
    timezone: str = os.getenv("US_TIMEZONE", "America/New_York")
    templates_dir: Path = Path(os.getenv("TEMPLATES_DIR", "templates"))
    image_output_dir: Path = Path(os.getenv("IMAGE_OUTPUT_DIR", "generated_images"))


settings = Settings()
