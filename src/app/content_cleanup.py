import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup

LOG = logging.getLogger(__name__)

class ContentCleanup:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.docs_dir = repo_root / "docs"
        self.generated_dir = repo_root / "generated"

    def sync_posts_json(self, valid_slugs: set[str]):
        """Removes entries from posts.json that don't have a corresponding HTML file."""
        posts_path = self.docs_dir / "posts.json"
        if not posts_path.exists():
            return
            
        posts = json.loads(posts_path.read_text(encoding='utf-8'))
        initial_count = len(posts)
        filtered_posts = [p for p in posts if p.get('slug') in valid_slugs]
        
        if len(filtered_posts) < initial_count:
            posts_path.write_text(json.dumps(filtered_posts, indent=2), encoding='utf-8')
            LOG.info(f"Sync posts.json: Removed {initial_count - len(filtered_posts)} orphaned entries.")

    def clean_orphaned_assets(self, valid_slugs: set[str]):
        """Removes images in assets/ that are no longer referenced by any post."""
        assets_dir = self.docs_dir / "assets"
        if not assets_dir.exists():
            return
            
        # Standard assets to keep
        keep = {"style.css", "logo.png", "favicon.ico"}
        
        removed_count = 0
        for f in assets_dir.glob("*"):
            if f.name in keep:
                continue
            
            # Check if filename contains any valid slug
            is_referenced = False
            for slug in valid_slugs:
                if slug in f.name:
                    is_referenced = True
                    break
            
            if not is_referenced:
                try:
                    f.unlink()
                    removed_count += 1
                except Exception as e:
                    LOG.error(f"Failed to delete orphaned asset {f.name}: {e}")
                    
        if removed_count > 0:
            LOG.info(f"Cleaned {removed_count} orphaned assets.")

    def remove_duplicates_by_slug(self, dry_run: bool = True):
        """Removes duplicate HTML files based on slug patterns (e.g. slug-0311-2.html)."""
        html_files = list(self.docs_dir.glob("*.html"))
        ignored = {"index.html", "about.html", "404.html", "google6133bcf6ce3a132f.html"}
        
        # Identify duplicates: slug.html and slug-MMDD-X.html
        slug_map = {}
        to_delete = []
        
        for f in html_files:
            if f.name in ignored:
                continue
                
            # Basic slug extraction: remove date/slot suffix if present
            # Pattern: slug-MMDD-X.html
            match = re.search(r'(.+)-\d{4}-\d\.html$', f.name)
            base_slug = match.group(1) if match else f.stem
            
            if base_slug not in slug_map:
                slug_map[base_slug] = f
            else:
                # If we have a choice, keep the one without the suffix (original/cleanest)
                # or the newest one. Here we keep the first one found or the clean one.
                existing = slug_map[base_slug]
                if '-' not in f.stem and '-' in existing.stem:
                    to_delete.append(existing)
                    slug_map[base_slug] = f
                else:
                    to_delete.append(f)

        removed_files = []
        if not dry_run:
            for f in to_delete:
                try:
                    f.unlink()
                    removed_files.append(f.name)
                    LOG.info(f"Deleted duplicate HTML: {f.name}")
                except Exception as e:
                    LOG.error(f"Error deleting {f.name}: {e}")
        
        valid_slugs = {f.stem for f in self.docs_dir.glob("*.html") if f.name not in ignored}
        return valid_slugs, removed_files

    def run(self, dry_run: bool = True):
        LOG.info(f"Starting cleanup in {self.docs_dir}")
        
        valid_slugs, removed = self.remove_duplicates_by_slug(dry_run)
        
        if not dry_run:
            self.sync_posts_json(valid_slugs)
            self.clean_orphaned_assets(valid_slugs)
            
        return {
            "valid_posts": len(valid_slugs),
            "removed_count": len(removed),
            "dry_run": dry_run
        }

import re
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
    repo_path = Path(".")
    cleaner = ContentCleanup(repo_path)
    is_dry = "--commit" not in sys.argv
    res = cleaner.run(dry_run=is_dry)
    print(json.dumps(res, indent=2))
