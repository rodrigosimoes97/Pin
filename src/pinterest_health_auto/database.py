from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import MetricEvent, PinDraft, Topic


class Database:
    def __init__(self, db_path: str = "pinterest_health_auto.db") -> None:
        self.db_path = db_path.replace("sqlite:///", "")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    trend_score REAL NOT NULL,
                    locale TEXT NOT NULL DEFAULT 'en-US',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS affiliate_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_keyword TEXT NOT NULL UNIQUE,
                    destination_url TEXT NOT NULL,
                    affiliate_url TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS pins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL,
                    board_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    alt_text TEXT NOT NULL,
                    keyword_tags TEXT NOT NULL,
                    affiliate_link TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    publish_at TEXT,
                    published_at TEXT,
                    publish_external_id TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(topic_id) REFERENCES topics(id)
                );

                CREATE TABLE IF NOT EXISTS pin_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pin_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(pin_id) REFERENCES pins(id)
                );

                CREATE TABLE IF NOT EXISTS publish_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pin_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(pin_id) REFERENCES pins(id)
                );
                """
            )

    def insert_topic(self, topic: Topic) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO topics(name, source, trend_score, locale) VALUES (?, ?, ?, ?)",
                (topic.name, topic.source, topic.trend_score, topic.locale),
            )
            return int(cur.lastrowid)

    def list_topics(self, limit: int = 20) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM topics ORDER BY trend_score DESC, created_at DESC LIMIT ?", (limit,)
            )
            return cur.fetchall()

    def insert_pin(self, pin: PinDraft) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO pins(
                    topic_id, board_name, title, description, alt_text, keyword_tags,
                    affiliate_link, image_path, publish_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pin.topic_id,
                    pin.board_name,
                    pin.title,
                    pin.description,
                    pin.alt_text,
                    ",".join(pin.keyword_tags),
                    pin.affiliate_link,
                    pin.image_path,
                    pin.publish_at.isoformat() if pin.publish_at else None,
                    pin.status,
                ),
            )
            return int(cur.lastrowid)

    def list_due_pins(self, now: datetime) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM pins
                WHERE status IN ('draft', 'scheduled')
                  AND (publish_at IS NULL OR publish_at <= ?)
                ORDER BY publish_at ASC
                """,
                (now.isoformat(),),
            )
            return cur.fetchall()

    def update_pin_publish_status(
        self, pin_id: int, status: str, external_id: str | None = None, message: str = ""
    ) -> None:
        with self.connect() as conn:
            published_at = datetime.utcnow().isoformat() if status == "published" else None
            conn.execute(
                """
                UPDATE pins SET status=?, publish_external_id=?, published_at=COALESCE(?, published_at)
                WHERE id=?
                """,
                (status, external_id, published_at, pin_id),
            )
            conn.execute(
                "INSERT INTO publish_logs(pin_id, status, message) VALUES (?, ?, ?)",
                (pin_id, status, message),
            )

    def insert_metric(self, event: MetricEvent) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO pin_metrics(pin_id, event_type, value, occurred_at) VALUES (?, ?, ?, ?)",
                (
                    event.pin_id,
                    event.event_type,
                    event.value,
                    (event.occurred_at or datetime.utcnow()).isoformat(),
                ),
            )
            return int(cur.lastrowid)

    def get_pin_summary(self, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT p.id, p.title, p.status, p.board_name, p.publish_at, p.published_at,
                       COALESCE(SUM(CASE WHEN m.event_type='click' THEN m.value ELSE 0 END), 0) as clicks,
                       COALESCE(SUM(CASE WHEN m.event_type='view' THEN m.value ELSE 0 END), 0) as views,
                       COALESCE(SUM(CASE WHEN m.event_type='conversion' THEN m.value ELSE 0 END), 0) as conversions
                FROM pins p
                LEFT JOIN pin_metrics m ON m.pin_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cur.fetchall()
