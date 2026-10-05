from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)

DEFAULT_PERFORMANCE_FILE = "generated/pinterest_performance.json"


class PinterestPerformanceTracker:
    """
    Rastreia e analisa o desempenho histórico de Pins do Pinterest.
    Permite atualizar métricas (impressions, engagements, saves, outbound_clicks),
    ranquear padrões vencedores e sugerir os melhores intents/keywords para novos Pins.
    """

    def __init__(self, storage_path: Path | str | None = None) -> None:
        if storage_path is None:
            self.storage_path = Path(DEFAULT_PERFORMANCE_FILE)
        else:
            self.storage_path = Path(storage_path)

    def _load_data(self) -> dict[str, Any]:
        if not self.storage_path.exists():
            return {"pins": [], "last_updated": None}
        try:
            content = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict) or "pins" not in data or not isinstance(data["pins"], list):
                return {"pins": [], "last_updated": None}
            return data
        except Exception as exc:
            LOG.warning("[PinterestPerformance] Falha ao ler %s (usando padrão vazio): %s", self.storage_path, exc)
            return {"pins": [], "last_updated": None}

    def _save_data(self, data: dict[str, Any]) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data["last_updated"] = datetime.now(timezone.utc).isoformat()
            temp_path = self.storage_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            temp_path.replace(self.storage_path)
        except Exception as exc:
            LOG.error("[PinterestPerformance] Falha ao salvar %s: %s", self.storage_path, exc)

    def record_pin(
        self,
        pin_date: str,
        url: str,
        topic: str,
        tag: str,
        intent: str,
        primary_keyword: str,
        title: str,
        impressions: int = 0,
        engagements: int = 0,
        saves: int = 0,
        outbound_clicks: int = 0,
    ) -> dict[str, Any]:
        """
        Registra um Pin criado ou atualiza seus metadados se já existir.
        Não sobrescreve métricas existentes se as novas forem 0.
        """
        data = self._load_data()
        pins: list[dict[str, Any]] = data.get("pins", [])

        existing = None
        for item in pins:
            if item.get("url") == url or (url and item.get("url", "").endswith(url.split("/")[-1])):
                existing = item
                break

        now_iso = datetime.now(timezone.utc).isoformat()

        if existing:
            existing["topic"] = topic or existing.get("topic", "")
            existing["tag"] = tag or existing.get("tag", "")
            existing["intent"] = intent or existing.get("intent", "")
            existing["primary_keyword"] = primary_keyword or existing.get("primary_keyword", "")
            existing["title"] = title or existing.get("title", "")
            if impressions > 0 or engagements > 0 or saves > 0 or outbound_clicks > 0:
                existing["impressions"] = impressions
                existing["engagements"] = engagements
                existing["saves"] = saves
                existing["outbound_clicks"] = outbound_clicks
            existing["last_updated"] = now_iso
            record = existing
        else:
            record = {
                "date": pin_date,
                "url": url,
                "topic": topic,
                "tag": tag,
                "intent": intent,
                "primary_keyword": primary_keyword,
                "title": title,
                "impressions": int(impressions),
                "engagements": int(engagements),
                "saves": int(saves),
                "outbound_clicks": int(outbound_clicks),
                "created_at": now_iso,
                "last_updated": now_iso,
            }
            pins.append(record)

        data["pins"] = pins
        self._save_data(data)
        LOG.info("[PinterestPerformance] Pin registrado/atualizado: '%s' (intent=%s)", title, intent)
        return record

    def update_metrics(
        self,
        identifier: str,  # URL ou Título
        impressions: int,
        engagements: int,
        saves: int,
        outbound_clicks: int,
    ) -> bool:
        """Atualiza métricas de um Pin buscando por URL ou título."""
        data = self._load_data()
        pins = data.get("pins", [])
        found = False

        identifier_lower = identifier.lower().strip()
        for item in pins:
            url_match = item.get("url", "").lower().strip() == identifier_lower or (
                identifier_lower and item.get("url", "").lower().endswith(identifier_lower.split("/")[-1])
            )
            title_match = item.get("title", "").lower().strip() == identifier_lower

            if url_match or title_match:
                item["impressions"] = int(impressions)
                item["engagements"] = int(engagements)
                item["saves"] = int(saves)
                item["outbound_clicks"] = int(outbound_clicks)
                item["last_updated"] = datetime.now(timezone.utc).isoformat()
                found = True
                break

        if found:
            self._save_data(data)
            LOG.info("[PinterestPerformance] Métricas atualizadas para '%s'", identifier)
        else:
            LOG.warning("[PinterestPerformance] Pin não encontrado para atualização: '%s'", identifier)

        return found

    def update_from_analytics_csv(self, csv_path: Path | str) -> int:
        """
        Importa métricas a partir de um arquivo CSV exportado do Pinterest Analytics.
        Aceita cabeçalhos comuns do Pinterest Analytics (Pin URL, Pin title, Impressions, Saves, Clicks, Engagements).
        """
        path = Path(csv_path)
        if not path.exists():
            LOG.error("[PinterestPerformance] Arquivo CSV de métricas não encontrado: %s", path)
            return 0

        updated_count = 0
        with path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Mapeia cabeçalhos flexíveis
                url = row.get("Link") or row.get("Pin URL") or row.get("Destination URL") or row.get("URL") or ""
                title = row.get("Title") or row.get("Pin title") or ""
                identifier = url or title
                if not identifier:
                    continue

                try:
                    impressions = int(float(row.get("Impressions") or row.get("Total impressions") or 0))
                    engagements = int(float(row.get("Engagements") or row.get("Total engagements") or 0))
                    saves = int(float(row.get("Saves") or row.get("Pin clicks") or row.get("Saves count") or 0))
                    clicks = int(float(row.get("Outbound clicks") or row.get("Clicks") or row.get("Pin outbound clicks") or 0))

                    if self.update_metrics(identifier, impressions, engagements, saves, clicks):
                        updated_count += 1
                except (ValueError, TypeError) as exc:
                    LOG.debug("[PinterestPerformance] Linha CSV ignorada (%s): %s", identifier, exc)

        LOG.info("[PinterestPerformance] Importação concluída. %d pins atualizados via CSV.", updated_count)
        return updated_count

    @staticmethod
    def calculate_pin_score(pin: dict[str, Any]) -> float:
        """
        Score simples ponderado para ranquear Pins:
        - Saves (peso 3.0): sinal forte de intenção e valor
        - Outbound clicks (peso 2.5): tráfego direto para o site
        - Engagements (peso 1.0): interações gerais
        - Impressions (peso 0.005): alcance base
        """
        saves = float(pin.get("saves", 0))
        clicks = float(pin.get("outbound_clicks", 0))
        engagements = float(pin.get("engagements", 0))
        impressions = float(pin.get("impressions", 0))

        return (saves * 3.0) + (clicks * 2.5) + (engagements * 1.0) + (impressions * 0.005)

    def calculate_pattern_scores(self) -> dict[str, Any]:
        """
        Agrega e calcula a performance por intent, tag, topic e primary_keyword.
        """
        data = self._load_data()
        pins = data.get("pins", [])

        by_intent: dict[str, dict[str, float]] = {}
        by_tag: dict[str, dict[str, float]] = {}
        by_topic: dict[str, dict[str, float]] = {}

        for pin in pins:
            score = self.calculate_pin_score(pin)
            intent = pin.get("intent") or "guide"
            tag = pin.get("tag") or "health"
            topic = pin.get("topic") or "General"
            saves = float(pin.get("saves", 0))
            clicks = float(pin.get("outbound_clicks", 0))
            impressions = float(pin.get("impressions", 0))

            for group_dict, key in [(by_intent, intent), (by_tag, tag), (by_topic, topic)]:
                if key not in group_dict:
                    group_dict[key] = {
                        "count": 0,
                        "total_score": 0.0,
                        "total_saves": 0.0,
                        "total_clicks": 0.0,
                        "total_impressions": 0.0,
                    }
                group_dict[key]["count"] += 1
                group_dict[key]["total_score"] += score
                group_dict[key]["total_saves"] += saves
                group_dict[key]["total_clicks"] += clicks
                group_dict[key]["total_impressions"] += impressions

        def _format_ranking(group_dict: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
            result = []
            for k, metrics in group_dict.items():
                count = metrics["count"]
                avg_score = metrics["total_score"] / count if count > 0 else 0.0
                result.append(
                    {
                        "name": k,
                        "count": count,
                        "avg_score": round(avg_score, 2),
                        "total_score": round(metrics["total_score"], 2),
                        "total_saves": int(metrics["total_saves"]),
                        "total_clicks": int(metrics["total_clicks"]),
                        "total_impressions": int(metrics["total_impressions"]),
                    }
                )
            result.sort(key=lambda x: (x["avg_score"], x["total_score"]), reverse=True)
            return result

        return {
            "total_pins": len(pins),
            "ranked_intents": _format_ranking(by_intent),
            "ranked_tags": _format_ranking(by_tag),
            "ranked_topics": _format_ranking(by_topic),
        }

    def get_best_intent_for_tag(self, tag: str, min_samples: int = 2) -> str | None:
        """
        Retorna o search intent com melhor pontuação histórica para uma tag específica,
        caso haja dados suficientes (ao menos `min_samples` amostras).
        """
        data = self._load_data()
        pins = data.get("pins", [])

        matching_pins = [p for p in pins if (p.get("tag") == tag) and (p.get("intent"))]
        if len(matching_pins) < min_samples:
            return None

        intent_scores: dict[str, list[float]] = {}
        for pin in matching_pins:
            intent = pin["intent"]
            score = self.calculate_pin_score(pin)
            # Apenas considera se o pin teve algum sinal de interação ou visualização
            if score > 0:
                intent_scores.setdefault(intent, []).append(score)

        if not intent_scores:
            return None

        ranked = []
        for intent, scores in intent_scores.items():
            if len(scores) >= min_samples:
                avg = sum(scores) / len(scores)
                ranked.append((intent, avg, len(scores)))

        if not ranked:
            return None

        ranked.sort(key=lambda item: item[1], reverse=True)
        best_intent, best_avg, _ = ranked[0]
        LOG.info("[PinterestPerformance] Intent vencedor sugerido para tag '%s': %s (avg_score=%.2f)", tag, best_intent, best_avg)
        return best_intent
