from __future__ import annotations

from datetime import datetime

from .affiliate import IHerbAffiliateLinker
from .content_generation import ContentGenerator
from .database import Database
from .image_generation import ImageGenerator
from .models import PinDraft, Topic
from .publishing import PinterestPublisher, PublishPayload
from .scheduler import PinScheduler
from .seo import SeoOptimizer
from .topic_discovery import TopicDiscovery


class Pipeline:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.discovery = TopicDiscovery()
        self.generator = ContentGenerator()
        self.images = ImageGenerator()
        self.seo = SeoOptimizer()
        self.linker = IHerbAffiliateLinker()
        self.scheduler = PinScheduler()
        self.publisher = PinterestPublisher()

    def seed_topics(self, limit: int = 10) -> list[int]:
        topic_ids = []
        for item in self.discovery.fetch_trending_topics(limit=limit):
            topic_id = self.db.insert_topic(
                Topic(id=None, name=item.name, source=item.source, trend_score=item.trend_score)
            )
            topic_ids.append(topic_id)
        return topic_ids

    def generate_pins_for_topic(self, topic_id: int, topic_name: str, idea_count: int = 5) -> list[int]:
        ideas = self.generator.generate_pin_ideas(topic_name, count=idea_count)
        schedule = self.scheduler.schedule_batch(len(ideas), start=datetime.now())
        pin_ids: list[int] = []
        for idea, publish_at in zip(ideas, schedule):
            seo = self.seo.enrich_tags(topic_name, idea.tags)
            affiliate_link = self.linker.build_link(topic_name)
            image_path = self.images.generate_pin_image(topic_name)
            pin_ids.append(
                self.db.insert_pin(
                    PinDraft(
                        id=None,
                        topic_id=topic_id,
                        board_name=seo.board_name,
                        title=idea.title,
                        description=idea.description,
                        alt_text=idea.alt_text,
                        keyword_tags=seo.tags,
                        affiliate_link=affiliate_link,
                        image_path=image_path,
                        publish_at=publish_at,
                        status="scheduled",
                    )
                )
            )
        return pin_ids

    def publish_due(self) -> list[tuple[int, str, str]]:
        due = self.db.list_due_pins(datetime.utcnow())
        results: list[tuple[int, str, str]] = []
        for row in due:
            payload = PublishPayload(
                title=row["title"],
                description=row["description"],
                board_name=row["board_name"],
                link=row["affiliate_link"],
                image_path=row["image_path"],
                alt_text=row["alt_text"],
                tags=row["keyword_tags"].split(","),
            )
            status, message = self.publisher.publish_or_export(payload)
            external_id = message if status == "published" else None
            normalized_status = "published" if status == "published" else "exported"
            self.db.update_pin_publish_status(row["id"], normalized_status, external_id, message)
            results.append((row["id"], normalized_status, message))
        return results
