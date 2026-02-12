from pinterest_health_auto.content_generation import ContentGenerator


def test_generate_pin_ideas_range_and_shape() -> None:
    generator = ContentGenerator()
    ideas = generator.generate_pin_ideas("metabolism boosters", count=12)

    assert len(ideas) == 12
    for idea in ideas:
        assert idea.title
        assert idea.description
        assert len(idea.tags) == 10
        assert idea.alt_text
