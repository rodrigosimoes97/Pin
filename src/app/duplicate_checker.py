import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer, util
import torch

LOG = logging.getLogger(__name__)

class DuplicateChecker:
    def __init__(self, index_path: Path, model_name: str = 'all-MiniLM-L6-v2'):
        self.index_path = index_path
        # Use GPU if available, else CPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.index = self._load_index()

    def _load_index(self):
        """Loads the content index from a JSON file."""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                LOG.error(f"Error loading index from {self.index_path}: {e}")
                return []
        return []

    def _save_index(self):
        """Saves the content index to a JSON file."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            LOG.error(f"Error saving index to {self.index_path}: {e}")

    def _strip_html(self, html_content: str) -> str:
        """Strips HTML tags and returns clean text content."""
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove scripts, styles and other irrelevant tags
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        return soup.get_text(separator=' ', strip=True)

    def check_similarity(self, title: str, meta_description: str, html_content: str) -> tuple[str, float]:
        """
        Compares new content against the index using semantic similarity.
        Returns (status, similarity_score).
        """
        if not self.index:
            return "ALLOW", 0.0

        text_to_embed = f"{title} {meta_description} {self._strip_html(html_content)}"
        new_embedding = self.model.encode(text_to_embed, convert_to_tensor=True)

        # Prepare all existing embeddings in a tensor for batch comparison
        try:
            embeddings_list = [item['embedding'] for item in self.index]
            existing_embeddings = torch.tensor(embeddings_list).to(new_embedding.device)
            
            # Calculate cosine similarity in batch
            similarities = util.cos_sim(new_embedding, existing_embeddings)[0]
            max_similarity = torch.max(similarities).item()
        except Exception as e:
            LOG.error(f"Error during similarity comparison: {e}")
            return "ALLOW", 0.0

        if max_similarity > 0.85:
            return "BLOCK", max_similarity
        elif max_similarity > 0.70:
            return "REWRITE", max_similarity
        
        return "ALLOW", max_similarity

    def add_to_index(self, title: str, slug: str, meta_description: str, html_content: str, keywords: list[str] = None):
        """Adds new content to the index and persists it."""
        text_to_embed = f"{title} {meta_description} {self._strip_html(html_content)}"
        embedding = self.model.encode(text_to_embed).tolist()
        
        self.index.append({
            "title": title,
            "slug": slug,
            "keywords": keywords or [],
            "embedding": embedding
        })
        self._save_index()
        LOG.info(f"Indexed post: {slug} (Total: {len(self.index)})")
