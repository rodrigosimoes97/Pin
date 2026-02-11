from datetime import datetime

from pinterest_health_auto.scheduler import PinScheduler
from pinterest_health_auto.seo import SeoOptimizer


def test_seo_board_selection() -> None:
    seo = SeoOptimizer()
    assert seo.choose_board("vitamin d and supplement routine") == "Supplements & Vitamins"


def test_scheduler_respects_daily_limits() -> None:
    scheduler = PinScheduler()
    slots = scheduler.schedule_batch(100, start=datetime.now())
    assert len(slots) <= 10
    assert slots == sorted(slots)
