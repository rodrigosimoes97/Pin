from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from .config import settings
from .database import Database
from .metrics import MetricsTracker
from .pipeline import Pipeline

app = typer.Typer(help="PinterestHealthAuto CLI")
console = Console()


def _db() -> Database:
    db = Database(settings.database_url)
    db.init_schema()
    return db


@app.command()
def init_db() -> None:
    """Initialize SQLite schema."""
    _db()
    console.print("[green]Database initialized[/green]")


@app.command()
def quick_run(limit_topics: int = 3, pins_per_topic: int = 5, publish_now: bool = True) -> None:
    """Fluxo simples: descobre tópicos, gera pins e publica/exporta."""
    db = _db()
    pipeline = Pipeline(db)

    pipeline.seed_topics(limit=limit_topics)
    topics = db.list_topics(limit=limit_topics)

    total = 0
    for topic in topics:
        total += len(
            pipeline.generate_pins_for_topic(
                topic_id=topic["id"], topic_name=topic["name"], idea_count=pins_per_topic
            )
        )

    if publish_now:
        published = pipeline.publish_due()
        console.print(f"[green]Pins processados para publicação: {len(published)}[/green]")

    console.print(f"[green]Quick run concluído. Pins gerados: {total}[/green]")


@app.command()
def discover_topics(limit: int = 10) -> None:
    db = _db()
    pipeline = Pipeline(db)
    ids = pipeline.seed_topics(limit=limit)
    console.print(f"[green]Inserted {len(ids)} topics[/green]")


@app.command()
def generate_pins(topic_id: int, topic_name: str, count: int = 8) -> None:
    db = _db()
    pipeline = Pipeline(db)
    pin_ids = pipeline.generate_pins_for_topic(topic_id=topic_id, topic_name=topic_name, idea_count=count)
    console.print(f"[green]Generated {len(pin_ids)} pins[/green]")


@app.command()
def publish_due() -> None:
    db = _db()
    pipeline = Pipeline(db)
    results = pipeline.publish_due()
    for pin_id, status, msg in results:
        console.print(f"Pin {pin_id}: {status} -> {msg}")


@app.command()
def log_click(pin_id: int, clicks: float = 1) -> None:
    db = _db()
    tracker = MetricsTracker(db)
    event_id = tracker.log_click(pin_id, clicks)
    console.print(f"Logged click event id {event_id}")


@app.command()
def log_conversion(pin_id: int, conversions: float = 1) -> None:
    db = _db()
    tracker = MetricsTracker(db)
    event_id = tracker.log_conversion(pin_id, conversions)
    console.print(f"Logged conversion event id {event_id}")


@app.command()
def logs(limit: int = 25) -> None:
    db = _db()
    rows = db.get_pin_summary(limit=limit)
    table = Table(title="Pin Performance")
    for col in ["ID", "Title", "Status", "Board", "Clicks", "Views", "Conversions"]:
        table.add_column(col)
    for r in rows:
        table.add_row(
            str(r["id"]),
            r["title"][:45],
            r["status"],
            r["board_name"],
            str(r["clicks"]),
            str(r["views"]),
            str(r["conversions"]),
        )
    console.print(table)


@app.command()
def list_topics(limit: int = 20) -> None:
    db = _db()
    rows = db.list_topics(limit=limit)
    table = Table(title="Topics")
    table.add_column("ID")
    table.add_column("Topic")
    table.add_column("Score")
    table.add_column("Source")
    for row in rows:
        table.add_row(str(row["id"]), row["name"], str(row["trend_score"]), row["source"])
    console.print(table)


if __name__ == "__main__":
    app()
