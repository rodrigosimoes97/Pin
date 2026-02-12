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
            image_path="generated_images/test.jpg",
            publish_at=datetime.utcnow(),
            status="scheduled",
        )
    )
    assert pin_id > 0


def test_image_generation_downloads_from_web(tmp_path, monkeypatch) -> None:
    from pinterest_health_auto import config

    class MockResp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b"fake-image-bytes"

    def fake_urlopen(*args, **kwargs):
        return MockResp()

    monkeypatch.setattr(config.settings, "image_output_dir", tmp_path)
    monkeypatch.setattr("pinterest_health_auto.image_generation.urlopen", fake_urlopen)

    generator = ImageGenerator()
    path = generator.generate_pin_image("Simple Gut Health Tips")
    assert tmp_path.joinpath(path.split("/")[-1]).read_bytes() == b"fake-image-bytes"
