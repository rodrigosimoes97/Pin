from __future__ import annotations

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from src.app.content import ensure_scientific_links, validate_article_quality
from src.app.pinterest_seo import generate_triple_pins
from src.app.topics import Topic
from src.app.validate_links import validate_links


class TestSEOAndQuality(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.docs_dir = self.repo_root / "docs"
        self.posts_json_path = self.docs_dir / "posts.json"
        self.sitemap_path = self.docs_dir / "sitemap.xml"
        self.robots_path = self.docs_dir / "robots.txt"
        self.headers_path = self.docs_dir / "_headers"

    def test_1_and_2_sitemap_validity_and_absence_of_html(self) -> None:
        """Verifica se o sitemap é um XML válido e NÃO contém URLs terminadas em .html."""
        self.assertTrue(self.sitemap_path.exists(), "sitemap.xml não encontrado")
        content = self.sitemap_path.read_text(encoding="utf-8")

        tree = ET.parse(self.sitemap_path)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith("urlset"), "Tag raiz do sitemap deve ser <urlset>")

        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("ns:url", ns)
        self.assertGreater(len(urls), 10, "Sitemap deve conter dezenas de páginas ativas")

        loc_tags = root.findall("ns:url/ns:loc", ns)
        for loc in loc_tags:
            url_str = str(loc.text).strip()
            self.assertFalse(
                url_str.endswith(".html"),
                f"Sitemap NUNCA deve conter URLs terminadas em .html: {url_str}",
            )
            self.assertTrue(
                url_str.startswith("https://health-ptg.pages.dev"),
                f"URL fora do domínio canônico: {url_str}",
            )

    def test_3_canonical_urls_map_to_200_physical_files(self) -> None:
        """Verifica se cada URL canônica do sitemap corresponde a um arquivo físico em docs/ (status 200 no Cloudflare Pages)."""
        tree = ET.parse(self.sitemap_path)
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = tree.findall("ns:url/ns:loc", ns)

        for loc in locs:
            url_str = str(loc.text).strip()
            rel = url_str.replace("https://health-ptg.pages.dev", "").strip("/")

            if rel == "":
                target_file = self.docs_dir / "index.html"
            elif rel.startswith("tag/"):
                tag_name = rel.replace("tag/", "").strip()
                target_file = self.docs_dir / "tag" / f"{tag_name}.html"
            else:
                target_file = self.docs_dir / f"{rel}.html"

            self.assertTrue(
                target_file.exists(),
                f"URL canônica do sitemap {url_str} não possui arquivo físico {target_file.name} (resultaria em 404)",
            )

    def test_4_headers_no_conflicting_canonical_or_redirect_loops(self) -> None:
        """Verifica se _headers NÃO possui a regra quebrada de Link: rel='canonical' apontando para .html."""
        if not self.headers_path.exists():
            return
        headers_content = self.headers_path.read_text(encoding="utf-8")
        self.assertNotIn(
            ":splat.html",
            headers_content,
            "Regra conflitante :splat.html encontrada em _headers!",
        )
        self.assertNotIn(
            'rel="canonical"',
            headers_content,
            "Headers HTTP não devem injetar canonical genérico conflitante com o HTML",
        )

    def test_5_internal_links_integrity(self) -> None:
        """Verifica integridade de todos os links internos no docs/."""
        errors = validate_links(self.docs_dir)
        self.assertEqual(errors, [], f"Erros de links internos encontrados: {errors}")

    def test_6_robots_txt_allows_pages_and_declares_sitemap(self) -> None:
        """Verifica se robots.txt permite rastreamento e declara o sitemap oficial."""
        self.assertTrue(self.robots_path.exists(), "robots.txt não encontrado")
        content = self.robots_path.read_text(encoding="utf-8")

        self.assertIn("User-agent: *", content)
        self.assertIn("Allow: /", content)
        self.assertIn("Sitemap: https://health-ptg.pages.dev/sitemap.xml", content)
        self.assertNotIn("Disallow: /", [line.strip() for line in content.splitlines()])

    def test_7_metadata_uniqueness_no_duplicates(self) -> None:
        """Verifica ausência de títulos e slugs duplicados em posts.json."""
        self.assertTrue(self.posts_json_path.exists(), "posts.json não encontrado")
        posts = json.loads(self.posts_json_path.read_text(encoding="utf-8"))

        slugs = [p.get("slug") for p in posts if p.get("slug")]
        titles = [p.get("title") for p in posts if p.get("title")]

        self.assertEqual(len(slugs), len(set(slugs)), "Slugs duplicados detectados em posts.json")
        self.assertEqual(len(titles), len(set(titles)), "Títulos duplicados detectados em posts.json")

    def test_8_article_canonical_matches_clean_url(self) -> None:
        """Verifica se as páginas HTML dos posts têm canonical absoluto apontando para sua própria URL definitiva sem .html."""
        posts = json.loads(self.posts_json_path.read_text(encoding="utf-8"))
        sample_posts = posts[:15]

        for p in sample_posts:
            slug = p["slug"]
            html_file = self.docs_dir / f"{slug}.html"
            if not html_file.exists():
                continue
            html_text = html_file.read_text(encoding="utf-8")

            canonical_match = re.search(r"<link\s+rel=['\"]canonical['\"]\s+href=['\"]([^'\"]+)['\"]", html_text)
            self.assertTrue(canonical_match, f"Canonical ausente em {slug}.html")
            canonical_url = canonical_match.group(1)

            # Canonical não pode ter .html e deve terminar com o slug
            self.assertFalse(
                canonical_url.endswith(".html"),
                f"Canonical com .html detectado em {slug}.html: {canonical_url}",
            )
            self.assertTrue(
                canonical_url.endswith(f"/{slug}") or canonical_url.endswith(slug),
                f"Canonical incorreto em {slug}.html: {canonical_url}",
            )

    def test_9_editorial_and_scientific_quality_validation(self) -> None:
        """Testa o motor de validação editorial para detectar conteúdo superficial, promessas de cura ou sem fontes."""
        # Caso 1: Artigo com qualidade científica (deve passar)
        good_article = {
            "title": "Evidence-Based Magnesium Habits for Deeper Rest",
            "slug": "evidence-based-magnesium-habits-rest",
            "html": (
                "<p>Sleep quality relies on intricate neurological balance and circadian rhythm regulation. "
                "Recent clinical research published in peer-reviewed journals shows that dietary magnesium "
                "serves as an essential cofactor for neurotransmitter signaling and muscle relaxation.</p>"
                "<h2>What the Clinical Evidence Shows</h2>"
                "<p>In randomized clinical trials reviewed by the National Institutes of Health (NIH), "
                "investigators observed measurable improvements in subjective sleep latency and morning alertness. "
                "Researchers differentiated between daily nutritional habits and acute high-dose interventions, "
                "noting that consistent intake of leafy greens, nuts, and whole grains yields sustainable benefits.</p>"
                "<h2>Scientific Consensus vs. Hypotheses</h2>"
                "<p>While preliminary evidence suggested high dosage benefits, current clinical trials "
                "recommend adhering to daily recommended dietary allowances established by public health agencies. "
                "Understanding bioavailability is critical when evaluating supplemental forms such as glycinate versus oxide. "
                "Peer-reviewed studies emphasize that mineral absorption improves when paired with balanced meals "
                "rather than taken in isolation on an empty stomach.</p>"
                "<h2>Practical Lifestyle Implementation</h2>"
                "<p>Rather than relying solely on supplements, health professionals suggest incorporating nutrient-dense "
                "whole foods into evening meals. Pumpkin seeds, almonds, dark chocolate, and cooked spinach offer naturally "
                "occurring magnesium along with synergistic micronutrients like potassium and fiber. Creating a predictable "
                "wind-down routine further reinforces the biological cues necessary for melatonin synthesis.</p>"
                "<h2>Circadian Rhythm Alignment and Environmental Factors</h2>"
                "<p>Nutritional strategies yield optimal results when aligned with fundamental sleep hygiene practices. "
                "Limiting evening blue spectrum light exposure from electronic devices prevents the phase delay of endogenous "
                "melatonin secretion. Furthermore, maintaining a cool ambient bedroom temperature supports the core body "
                "temperature drop required for transitioning into restorative slow-wave sleep stages. Establishing regular "
                "wake times stabilizes peripheral circadian clocks across metabolic tissues.</p>"
                "<h2>Evaluating Individual Bioavailability and Tolerance</h2>"
                "<p>Different chemical chelation forms display varying gastrointestinal tolerability profiles in clinical settings. "
                "Magnesium citrate and carbonate exhibit distinct osmotic effects compared to amino acid chelates like bisglycinate. "
                "Clinical investigators advise gradual titration when adjusting dietary intake to evaluate individual digestive comfort. "
                "Consulting a primary care provider ensures appropriate assessment of renal clearance and prevents potential "
                "pharmacological interactions with prescription medications.</p>"
                "<h2>Long-Term Health Outcomes and Preventive Strategies</h2>"
                "<p>Epidemiological surveillance cohorts monitored by national cardiovascular organizations highlight inverse correlations "
                "between adequate mineral consumption and systemic arterial stiffness. Sustained cellular homeostasis assists enzymatic "
                "reactions governing glucose transport and vascular tone regulation. Adopting a diverse culinary approach rich in legumes, "
                "avocados, and minimally processed seeds provides broad micronutrient density without excessive reliance on synthetic compounds. "
                "Consistency across weekly nutritional routines remains the cornerstone of chronic metabolic resilience.</p>"
                "<h2>Conclusions and Practical Takeaways for Daily Wellness</h2>"
                "<p>Scientific evidence indicates that micronutrient density forms an indispensable pillar of preventative healthcare. "
                "By emphasizing whole-food foundations and respecting biological rhythms, individuals establish sustainable recovery habits. "
                "Translating laboratory discoveries into manageable kitchen behaviors bridges clinical research and daily vitality.</p>"
                "<section class='scientific-sources'><h2>Scientific References & Sources</h2>"
                "<ul><li><a href='https://pubmed.ncbi.nlm.nih.gov/30062032/' target='_blank' rel='noopener noreferrer'>NIH Office of Dietary Supplements clinical review on magnesium</a></li>"
                "<li><a href='https://pubmed.ncbi.nlm.nih.gov/23853635/' target='_blank' rel='noopener noreferrer'>Journal of Sleep Research meta-analysis on micronutrients and sleep architecture</a></li>"
                "<li><a href='https://www.cdc.gov/nutrition/index.html' target='_blank' rel='noopener noreferrer'>CDC public health guidelines for adult nutritional health and chronic disease prevention</a></li></ul></section>"
            ),
            "faq": [
                {"question": "How does magnesium support rest?", "answer": "It acts as an enzymatic cofactor in cellular relaxation pathways and GABA regulation."},
                {"question": "What does clinical research recommend?", "answer": "Prioritizing dietary whole-food sources and adhering to standard allowances supported by NIH guidelines."},
            ],
        }
        is_valid, reason = validate_article_quality(good_article, "Magnesium Habits for Deeper Rest")
        self.assertTrue(is_valid, f"Artigo científico legítimo foi rejeitado indevidamente: {reason}")

        # Caso 2: Artigo com promessa de cura perigosa (deve falhar)
        cure_article = dict(good_article)
        cure_article["html"] = good_article["html"] + "<p>This is a miracle cure that cures diabetes instantly!</p>"
        is_valid, reason = validate_article_quality(cure_article, "Magnesium")
        self.assertFalse(is_valid, "Validação deve barrar promessas de cura perigosas")
        self.assertIn("promessa de cura", reason)

        # Caso 3: Artigo com anedota pessoal fictícia em 1ª pessoa (deve falhar)
        fake_story_article = dict(good_article)
        fake_story_article["html"] = "<p>When I was diagnosed with insomnia, in my personal experience I suffered...</p>" + good_article["html"]
        is_valid, reason = validate_article_quality(fake_story_article, "Magnesium")
        self.assertFalse(is_valid, "Validação deve barrar relatos em 1ª pessoa fabricados")
        self.assertIn("1ª pessoa proibido", reason)

        # Caso 4: Artigo muito curto / superficial (deve falhar)
        short_article = dict(good_article)
        short_article["html"] = "<p>Short article with too few words.</p>"
        is_valid, reason = validate_article_quality(short_article, "Magnesium")
        self.assertFalse(is_valid, "Validação deve barrar artigos superficiais e curtos")
        self.assertIn("superficial", reason)

        # Caso 5: Artigo sem links diretos para artigos científicos clicáveis (deve falhar)
        no_links_article = dict(good_article)
        no_links_article["html"] = re.sub(r"<a [^>]+>(.*?)</a>", r"\1", good_article["html"])
        is_valid, reason = validate_article_quality(no_links_article, "Magnesium")
        self.assertFalse(is_valid, "Validação deve exigir links científicos clicáveis")
        self.assertIn("link direto e clicável", reason)

        # Caso 6: Helper ensure_scientific_links deve enriquecer artigos sem link com PubMed/Europe PMC/Cochrane
        fixed_html = ensure_scientific_links(no_links_article["html"], "Magnesium Habits", "sleep")
        no_links_article["html"] = fixed_html
        is_valid, reason = validate_article_quality(no_links_article, "Magnesium")
        self.assertTrue(is_valid, f"ensure_scientific_links deveria ter corrigido os links científicos: {reason}")
        self.assertIn("pubmed.ncbi.nlm.nih.gov", fixed_html)
        self.assertIn("europepmc.org", fixed_html)
        self.assertIn("cochranelibrary.com", fixed_html)

        # Caso 7: Artigos com fontes Europe PMC e Cochrane Library são validados com sucesso
        cochrane_article = dict(good_article)
        cochrane_article["html"] = (
            good_article["html"] +
            "<section class='scientific-sources'><h2>Scientific References & Sources</h2><ul>"
            "<li><a href='https://europepmc.org/article/MED/1234567'>Europe PMC Systematic Review on Micronutrients</a></li>"
            "<li><a href='https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD000000'>Cochrane Database of Systematic Reviews</a></li>"
            "</ul></section>"
        )
        is_valid, reason = validate_article_quality(cochrane_article, "Magnesium")
        self.assertTrue(is_valid, f"Fontes da Europe PMC e Cochrane Library devem ser aceitas: {reason}")

    def test_10_triple_pins_generation(self) -> None:
        """Testa a geração dos 3 pins estratégicos por post: Educacional, Problema/Solução e SEO/Buscas."""
        topic = Topic(slug="magnesium-sleep", name="Magnesium Sleep Habits", angle="evidence-based bedtime guide", tag="sleep")
        article_data = {
            "title": "Evidence-Based Magnesium Habits for Deeper Rest",
            "slug": "magnesium-sleep",
            "meta_description": "Discover how clinical magnesium habits improve sleep architecture and circadian rhythm naturally.",
            "html": "<p>Scientific evidence on magnesium and sleep latency.</p>",
            "tag": "sleep",
            "pin_educational": {
                "pin_title": "The Science-Backed Magnesium Guide for Rest",
                "pin_description": "Discover the biological mechanisms of magnesium for deep sleep recovery. Save this research-backed breakdown!",
                "pin_keywords": "magnesium for sleep, sleep science tips, bedtime routine guide",
            },
            "pin_problem_solution": {
                "pin_title": "Common Magnesium Mistakes Ruining Your Sleep",
                "pin_description": "Are you taking the wrong type of magnesium at night? Learn what to avoid and what actually works for rest.",
                "pin_keywords": "sleep mistakes to avoid, magnesium timing tips, natural sleep remedies",
            },
            "pin_seo_search": {
                "pin_title": "Top Bedtime Magnesium Habits for Deep Sleep",
                "pin_description": "Explore the most popular nighttime magnesium habits and routines. Save this pin to reset your sleep tonight!",
                "pin_keywords": "how to sleep better naturally, bedtime routine for adults, natural sleep remedies",
            },
        }

        pins = generate_triple_pins(topic, article_data)
        self.assertEqual(len(pins), 3, "Deve gerar exatamente 3 pins distintos por post")

        pin_types = [p["pin_type"] for p in pins]
        self.assertEqual(pin_types, ["educational", "problem_solution", "seo_search"])

        utms = [p["utm_content"] for p in pins]
        self.assertEqual(utms, ["pin_educational", "pin_problem_solution", "pin_seo_search"])

        # Verifica slots de horário (distribuídos no dia)
        slots = [p["slot_index"] for p in pins]
        self.assertEqual(slots, [0, 2, 4])

        # Verifica requisitos de tamanho de título e descrição de cada pin
        for p in pins:
            self.assertTrue(40 <= len(p["pin_title"]) <= 70, f"Título fora dos limites: '{p['pin_title']}' ({len(p['pin_title'])})")
            self.assertTrue(140 <= len(p["pin_description"]) <= 260, f"Descrição fora dos limites: '{p['pin_description']}' ({len(p['pin_description'])})")
            self.assertGreaterEqual(len(p["keywords_list"]), 5, "Cada pin deve conter pelo menos 5 keywords")

    def test_11_google_indexing_removed_and_clean_configuration(self) -> None:
        """Verifica que o Google Indexing API foi completamente removido da configuração e das dependências."""
        from src.app.config import Settings
        import dataclasses
        field_names = [f.name for f in dataclasses.fields(Settings)]
        self.assertNotIn(
            "google_indexing_json_path",
            field_names,
            "google_indexing_json_path deve ser removido de Settings",
        )


if __name__ == "__main__":
    unittest.main()
