from datetime import datetime

from pinterest_health_auto.database import Database
from pinterest_health_auto.image_generation import ImageGenerator
from pinterest_health_auto.models import PinDraft, Topic


def test_database_topic_and_pin_insert(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    db.init_schema()

    topic_id = db.insert_topic(Topic(id=None, name="gut health", source="test", trend_score=90.0))
    assert topic_id > 0

    pin_id = db.insert_pin(
        PinDraft(
            id=None,
            topic_id=topic_id,
            board_name="Gut Health & Digestion",
            title="Gut Health Tips",
            description="desc",
            alt_text="alt",
            keyword_tags=["gut-health"] * 10,
            affiliate_link="https://example.com",
            image_path="generated_images/test.svg",
            publish_at=datetime.utcnow(),
            status="scheduled",
        )
    )
    assert pin_id > 0


def test_image_generation_creates_vertical_svg(tmp_path, monkeypatch) -> None:
    from pinterest_health_auto import config

    monkeypatch.setattr(config.settings, "image_output_dir", tmp_path)
    generator = ImageGenerator()
    path = generator.generate_pin_image("Simple Gut Health Tips")
    text = tmp_path.joinpath(path.split("/")[-1]).read_text(encoding="utf-8")
    assert "width='1000'" in text
    assert "height='1500'" in text
