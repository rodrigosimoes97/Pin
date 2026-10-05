import tempfile
from pathlib import Path
from datetime import date
from src.app.topics import Topic
from src.app.pinterest_seo import (
    generate_pinterest_seo,
    detect_search_intent,
    generate_search_keywords,
    build_pinterest_title,
    build_pinterest_description,
)
from src.app.pinterest_performance import PinterestPerformanceTracker
from src.app.pinterest_drafts import write_draft_pack


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
PASS = "✅"
FAIL = "❌"

def check(condition: bool, msg: str) -> None:
    icon = PASS if condition else FAIL
    print(f"  {icon} {msg}")
    if not condition:
        raise AssertionError(f"FAILED: {msg}")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1: SEARCH INTENT DETECTION
# ──────────────────────────────────────────────────────────────────────────────
def test_intents():
    print("\n=== TEST 1: SEARCH INTENT DETECTION ===")
    cases = [
        ("How to Sleep Better Tonight Naturally", "Sleep Quality", "sleep", "how_to"),
        ("8 Common Food Additives Linked to High Blood Pressure", "Food Additives", "healthy-habits", "mistakes"),
        ("Fix a Hidden Compound in Healthy Foods May Worsen IBD", "IBD and Diet", "gut", "mistakes"),
        ("10 Anti-Inflammatory Foods You Should Eat Daily", "Anti Inflammatory Diet", "anti-inflammatory", "list"),
        ("Daily Gut Health Habits Checklist", "Gut Health Checklist", "gut", "checklist"),
        ("Top Stress Relief Tips for Busy Days", "Stress Relief", "stress", "tips"),
        ("The Complete Longevity Science Guide for Adults", "Longevity", "longevity", "guide"),
        ("Simple Morning Workout Routine for Beginners", "Home Workouts", "home-workouts", "routine"),
        ("5 Calcium Myths That May Hurt Your Bone Health", "Calcium Myths", "healthy-habits", "mistakes"),
        ("Ultra-Processed Foods Linked to Hidden Muscle Fat", "Ultra Processed Foods", "weight", "mistakes"),
    ]

    for title, topic_name, tag, expected in cases:
        detected = detect_search_intent(title, topic_name, tag)
        ok = detected == expected
        print(f"  {'✅' if ok else '❌'} [{detected:10} / expected {expected:10}] {title[:55]}")
        assert ok, f"Intent mismatch: got '{detected}', expected '{expected}'"

    print(f"  → Todos os 10 intents corretos!")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2: LONG-TAIL KEYWORDS
# ──────────────────────────────────────────────────────────────────────────────
def test_keywords():
    print("\n=== TEST 2: LONG-TAIL KEYWORDS ===")
    cases = [
        ("food additives harm", "healthy-habits", "mistakes"),
        ("sleep quality improvement", "sleep", "routine"),
        ("gut microbiome diet", "gut", "tips"),
        ("anti inflammatory foods", "anti-inflammatory", "list"),
    ]

    for primary_kw, tag, intent in cases:
        kws = generate_search_keywords(
            topic_name=primary_kw,
            title=primary_kw,
            tag=tag,
            intent=intent,
            primary_keyword=primary_kw,
        )
        print(f"\n  Topic: {primary_kw} | Tag: {tag} | Intent: {intent}")
        for kw in kws:
            n_words = len(kw.split())
            ok_len = n_words >= 2
            print(f"    {'✅' if ok_len else '❌'} ({n_words}w) '{kw}'")
            assert ok_len, f"Single-word keyword found: '{kw}'"

        check(5 <= len(kws) <= 8, f"Quantidade de keywords: {len(kws)} (esperado: 5-8)")

        # Verifica unicidade
        check(len(kws) == len(set(kws)), "Keywords sem duplicatas")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3: TITLE & DESCRIPTION QUALITY
# ──────────────────────────────────────────────────────────────────────────────
def test_titles_and_descriptions():
    print("\n=== TEST 3: TITLES E DESCRIPTIONS ===")
    test_cases = [
        {
            "article": {
                "title": "8 Common Food Additives Linked to High Blood Pressure and Heart Disease",
                "tag": "healthy-habits",
                "meta_description": "Discover food additives in packaged foods that raise blood pressure and learn easy whole-food swaps.",
                "html": "<p>Food additives harm health.</p>",
                "pin_title": "8 Food Additives Harming Your Heart Health",  # bom - 42 chars
                "pin_description": "",
            },
            "topic": Topic(slug="food-additives", name="Food Additives Blood Pressure", angle="", tag="healthy-habits"),
        },
        {
            "article": {
                "title": "Ultra-Processed Foods Linked to Hidden Muscle Fat That May Threaten Your Knees",
                "tag": "weight",
                "meta_description": "Ultra processed foods are linked to hidden muscle fat that threatens knee joints.",
                "html": "<p>Ultra-processed foods content.</p>",
                "pin_title": "Build a Better Week With ultra processed foods",  # ruim - fallback genérico
                "pin_description": "",
            },
            "topic": Topic(slug="ultra-processed", name="Ultra-Processed Foods Muscle Fat", angle="", tag="weight"),
        },
        {
            "article": {
                "title": "How I Finally Made Home Workouts Stick After Years of Failure",
                "tag": "home-workouts",
                "meta_description": "A practical personal guide to building a sustainable home workout habit.",
                "html": "<p>Home workouts content.</p>",
                "pin_title": "",  # sem título do Gemini
                "pin_description": "",
            },
            "topic": Topic(slug="home-workouts", name="Home Workout Routine", angle="", tag="home-workouts"),
        },
    ]

    for tc in test_cases:
        seo = generate_pinterest_seo(tc["topic"], tc["article"])
        title = seo["pin_title"]
        desc = seo["pin_description"]
        intent = seo["intent"]
        print(f"\n  Article: '{tc['article']['title'][:55]}'")
        print(f"  Intent: {intent}")
        print(f"  Pin Title ({len(title)}): '{title}'")
        print(f"  Pin Desc  ({len(desc)}): '{desc[:80]}...'")

        check(40 <= len(title) <= 70, f"pin_title length: {len(title)} chars (need 40-70)")
        check(140 <= len(desc) <= 260, f"pin_description length: {len(desc)} chars (need 140-260)")
        check(intent in ["how_to", "list", "checklist", "tips", "mistakes", "guide", "routine"], f"Intent válido: {intent}")

    # Verifica que título do Gemini válido é preservado
    seo_1 = generate_pinterest_seo(test_cases[0]["topic"], test_cases[0]["article"])
    check(
        seo_1["pin_title"] == "8 Food Additives Harming Your Heart Health",
        f"Título do Gemini válido preservado: '{seo_1['pin_title']}'"
    )

    # Verifica que título genérico de fallback é substituído
    seo_2 = generate_pinterest_seo(test_cases[1]["topic"], test_cases[1]["article"])
    check(
        not seo_2["pin_title"].lower().startswith("build a better week with"),
        f"Título genérico de fallback foi substituído: '{seo_2['pin_title']}'"
    )


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4: PERFORMANCE TRACKER & LEARNING
# ──────────────────────────────────────────────────────────────────────────────
def test_performance_tracker():
    print("\n=== TEST 4: PERFORMANCE TRACKER & LEARNING ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "perf.json"
        tracker = PinterestPerformanceTracker(tmp_path)

        # Registra pins
        tracker.record_pin("2026-10-05", "https://health-ptg.pages.dev/post1.html",
                           "Food Additives", "healthy-habits", "mistakes",
                           "food additives heart health", "8 Food Additives Harming Your Heart")
        tracker.record_pin("2026-10-05", "https://health-ptg.pages.dev/post2.html",
                           "Sleep Tips", "sleep", "routine",
                           "bedtime sleep routine", "Simple Bedtime Routine for Adults")
        tracker.record_pin("2026-10-05", "https://health-ptg.pages.dev/post3.html",
                           "Anti-Inflammatory", "anti-inflammatory", "list",
                           "anti inflammatory foods", "Best Anti-Inflammatory Foods List")

        check(tmp_path.exists(), "Arquivo de performance criado")

        # Atualiza métricas
        ok1 = tracker.update_metrics("https://health-ptg.pages.dev/post1.html",
                                     impressions=5000, engagements=250, saves=120, outbound_clicks=80)
        ok2 = tracker.update_metrics("https://health-ptg.pages.dev/post2.html",
                                     impressions=800, engagements=10, saves=5, outbound_clicks=2)
        ok3 = tracker.update_metrics("https://health-ptg.pages.dev/post3.html",
                                     impressions=2000, engagements=70, saves=45, outbound_clicks=30)

        check(ok1 and ok2 and ok3, "Métricas atualizadas com sucesso")

        # Calcula scores
        scores = tracker.calculate_pattern_scores()
        check(scores["total_pins"] == 3, f"total_pins = {scores['total_pins']}")

        intents_ranked = scores["ranked_intents"]
        best_intent = intents_ranked[0]["name"]
        print(f"  Intent com melhor score: {best_intent}")
        print(f"  Ranking completo de intents: {[(i['name'], i['avg_score']) for i in intents_ranked]}")
        check(best_intent == "mistakes", f"Mistakes deve ser o melhor intent (scores altos)")

        # Recomendação por tag
        best = tracker.get_best_intent_for_tag("healthy-habits", min_samples=1)
        check(best == "mistakes", f"Melhor intent para healthy-habits: {best}")

        # Fallback sem dados suficientes
        best_unknown = tracker.get_best_intent_for_tag("sleep", min_samples=10)
        check(best_unknown is None, f"Retorna None sem amostras suficientes (retornou: {best_unknown})")

        # Sem quebrar quando arquivo não existe
        tracker2 = PinterestPerformanceTracker(Path(tmp_dir) / "inexistente.json")
        result = tracker2.calculate_pattern_scores()
        check(result["total_pins"] == 0, "Funciona sem dados pré-existentes")

        # CSV import (simula um export do Pinterest Analytics)
        import csv
        csv_path = Path(tmp_dir) / "analytics_export.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Link", "Title", "Impressions", "Engagements", "Saves", "Outbound clicks"])
            writer.writeheader()
            writer.writerow({
                "Link": "https://health-ptg.pages.dev/post1.html",
                "Title": "8 Food Additives Harming Your Heart",
                "Impressions": "9999",
                "Engagements": "500",
                "Saves": "300",
                "Outbound clicks": "200",
            })
        n_updated = tracker.update_from_analytics_csv(csv_path)
        check(n_updated == 1, f"CSV import: {n_updated} pins atualizados")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 5: DRAFT PACK — CSV + JSON com campos extras
# ──────────────────────────────────────────────────────────────────────────────
def test_draft_pack():
    print("\n=== TEST 5: DRAFT PACK CSV & JSON ===")
    topic = Topic(slug="food-additives", name="Food Additives Blood Pressure", angle="", tag="healthy-habits")
    article = {
        "title": "8 Common Food Additives Linked to High Blood Pressure",
        "tag": "healthy-habits",
        "meta_description": "Learn which food additives harm blood pressure.",
        "html": "<p>Test content.</p>",
        "pin_title": "8 Food Additives Harming Your Heart Health",
        "pin_description": "",
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        seo = generate_pinterest_seo(topic, article)
        out_dir = Path(tmp_dir) / "drafts"

        csv_file, json_file = write_draft_pack(
            out_dir=out_dir,
            run_date=date(2026, 10, 5),
            pin_title=seo["pin_title"],
            pin_description=seo["pin_description"],
            link="https://health-ptg.pages.dev/test.html",
            image_path="assets/2026-10-05_test.jpeg",
            tag="healthy-habits",
            slot_index=0,
            keywords=seo["keywords"],
            intent=seo["intent"],
            primary_keyword=seo["primary_keyword"],
        )

        check(csv_file.exists(), "CSV gerado")
        check(json_file.exists(), "JSON gerado")

        csv_content = csv_file.read_text(encoding="utf-8")
        check("Title,Media URL,Pinterest board,Thumbnail,Description,Link,Publish date,Keywords" in csv_content,
              "CSV tem cabeçalho correto (sem aspas no header)")
        check("health-ptg.pages.dev" in csv_content, "CSV tem URL pública correta")
        check("T10:00:00" in csv_content, "CSV tem horário de publicação")

        # Verifica keywords no CSV
        kws_in_csv = seo["keywords"]
        all_single_word = all(len(kw.strip().split()) <= 1 for kw in kws_in_csv.split(","))
        check(not all_single_word, "Keywords não são palavras soltas (todas têm 2+ palavras)")

        print(f"\n  CSV Preview:")
        for line in csv_content.splitlines()[:3]:
            print(f"    {line[:120]}")

        print(f"\n  Keywords geradas: {seo['keywords'][:100]}...")
        print(f"  Quantidade: {len(seo['keywords_list'])} frases")


# ──────────────────────────────────────────────────────────────────────────────
# RUN ALL
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        test_intents()
        test_keywords()
        test_titles_and_descriptions()
        test_performance_tracker()
        test_draft_pack()
        print("\n" + "="*60)
        print("✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ FALHA: {e}")
        raise SystemExit(1)
