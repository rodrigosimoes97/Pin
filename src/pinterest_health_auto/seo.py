from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SeoPackage:
    board_name: str
    tags: list[str]


class SeoOptimizer:
    board_rules = {
        "weight": "Weight Loss Motivation",
        "recipe": "Healthy Recipes",
        "supplement": "Supplements & Vitamins",
        "vitamin": "Supplements & Vitamins",
        "gut": "Gut Health & Digestion",
        "metabolism": "Metabolism Boosting Tips",
    }

    def choose_board(self, topic: str) -> str:
        lower = topic.lower()
        for keyword, board in self.board_rules.items():
            if keyword in lower:
                return board
        return "Health & Wellness Tips"

    def enrich_tags(self, topic: str, existing_tags: list[str]) -> SeoPackage:
        board = self.choose_board(topic)
        us_tags = ["usa", "pinterest-us", "wellness-journey", "healthy-habits"]
        final = []
        for tag in existing_tags + us_tags:
            if tag not in final:
                final.append(tag)
        return SeoPackage(board_name=board, tags=final[:10])
