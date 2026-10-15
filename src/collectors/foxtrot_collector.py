#!/usr/bin/env python3
"""
FoxTrot Comic Collector

Fetches FoxTrot comics from GoComics.com
- FoxTrot is Sunday-only (weekly strip)
- Archive support with caching
"""

import os
import json
import requests
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class FoxTrotCollector:
    """Collector for FoxTrot comics from GoComics."""
    
    BASE_URL = "https://www.gocomics.com/foxtrot"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    def __init__(self, cache_dir: str = None):
        # Use absolute paths based on project root
        project_root = Path(__file__).parent.parent.parent
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = project_root / "data" / "comics" / "foxtrot"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = project_root / "data" / "foxtrot_archive.json"
        self._load_cache()
    
    def _load_cache(self):
        """Load cached comic metadata."""
        if self.cache_file.exists():
            with open(self.cache_file, 'r') as f:
                self.cache = json.load(f)
        else:
            self.cache = {"comics": [], "last_updated": None}
    
    def _save_cache(self):
        """Save comic metadata to cache."""
        self.cache["last_updated"] = datetime.now().isoformat()
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _fetch_comic_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single comic page."""
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch {url}: {resp.status_code}")
                return None
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # First try to find the comic image from featureassets
            image_url = None
            
            # Look for featureassets URL in page content
            featureassets_match = re.search(r'https://featureassets\.gocomics\.com/assets/[a-f0-9]+', resp.text)
            if featureassets_match:
                image_url = featureassets_match.group(0)
            
            # Fallback: try og:image meta tag
            if not image_url:
                og_image = soup.select_one('meta[property="og:image"]')
                if og_image and og_image.get('content'):
                    image_url = og_image['content']
                    # Skip placeholder images
                    if 'GC_Social' in image_url or 'staging-assets' in image_url:
                        image_url = None
            
            # Check for challenge/block
            if not image_url or 'challenge.svg' in str(image_url):
                logger.warning(f"Blocked or no image for {url}")
                return None
            
            # Get title
            og_title = soup.select_one('meta[property="og:title"]')
            title = og_title['content'] if og_title and og_title.get('content') else "FoxTrot"
            
            # Get canonical link
            canonical = soup.find('link', rel='canonical')
            link = canonical['href'] if canonical and canonical.get('href') else url
            
            # Parse date from URL or canonical link
            parse_url = link if link else url
            parts = parse_url.rstrip('/').split('/')
            comic_id = datetime.now().strftime("%Y-%m-%d")
            if len(parts) >= 3:
                try:
                    y, m, d = parts[-3], parts[-2], parts[-1]
                    if y.isdigit() and len(y) == 4:
                        comic_id = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                except:
                    pass
            
            return {
                "id": comic_id,
                "series": "foxtrot",
                "title": title,
                "date": comic_id,
                "image_url": image_url,
                "link": link,
                "attribution": "© Bill Amend / GoComics"
            }
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _find_last_sunday(self, from_date: datetime = None) -> datetime:
        """Find the most recent Sunday (FoxTrot is Sunday-only)."""
        if from_date is None:
            from_date = datetime.now()
        days_since_sunday = from_date.weekday() + 1  # Monday is 0, Sunday is 6
        if days_since_sunday == 7:
            days_since_sunday = 0  # Today is Sunday
        return from_date - timedelta(days=days_since_sunday)
    
    def get_daily(self) -> Dict[str, Any]:
        """Get most recent FoxTrot comic (Sunday strip)."""
        # Find last Sunday
        last_sunday = self._find_last_sunday()
        comic = self.get_by_date(last_sunday)
        if comic:
            self._add_to_cache(comic)
            return {"success": True, "comic": comic}
        
        # Try previous Sunday if this one isn't available
        prev_sunday = last_sunday - timedelta(days=7)
        comic = self.get_by_date(prev_sunday)
        if comic:
            self._add_to_cache(comic)
            return {"success": True, "comic": comic}
        
        return {"success": False, "error": "Failed to fetch FoxTrot comic"}
    
    def _add_to_cache(self, comic: Dict[str, Any]):
        """Add comic to cache if not already present."""
        existing_ids = {c.get('id') or c.get('date') for c in self.cache.get('comics', [])}
        if comic['id'] not in existing_ids:
            self.cache['comics'].append(comic)
            self._save_cache()
    
    def get_by_date(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Get comic for a specific date."""
        url = f"{self.BASE_URL}/{date.year}/{date.month}/{date.day}"
        return self._fetch_comic_page(url)
    
    def download_image(self, image_url: str, comic_id: str) -> Optional[str]:
        """Download and cache comic image."""
        try:
            ext = "gif"
            if ".png" in image_url.lower():
                ext = "png"
            elif ".jpg" in image_url.lower() or ".jpeg" in image_url.lower():
                ext = "jpg"
            
            filename = f"{comic_id}.{ext}"
            filepath = self.cache_dir / filename
            
            if filepath.exists():
                return str(filepath)
            
            resp = requests.get(image_url, headers=self.HEADERS, timeout=30)
            if resp.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                logger.info(f"Downloaded FoxTrot: {filename}")
                return str(filepath)
            else:
                logger.warning(f"Failed to download {image_url}: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error downloading {image_url}: {e}")
            return None
    
    def get_random(self) -> Dict[str, Any]:
        """Get a random comic from the cache or daily."""
        import random
        if not self.cache.get('comics'):
            return self.get_daily()
        
        comic = random.choice(self.cache['comics'])
        return {"success": True, "comic": comic}
    
    def get_archive_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of cached comics sorted by date."""
        # Also scan directory for downloaded images
        self._scan_directory_for_archive()
        comics = sorted(self.cache.get('comics', []), key=lambda x: x['date'], reverse=True)
        return comics[:limit]
    
    def _scan_directory_for_archive(self):
        """Scan the comics directory and add any missing files to the cache."""
        # Support both 'id' and 'date' keys for backwards compatibility
        existing_ids = {c.get('id') or c.get('date') for c in self.cache.get('comics', [])}
        
        for filepath in self.cache_dir.glob("*.gif"):
            comic_id = filepath.stem  # e.g., "2025-12-21"
            if comic_id not in existing_ids:
                # Add to cache with local file reference
                self.cache['comics'].append({
                    "id": comic_id,
                    "series": "foxtrot",
                    "title": f"FoxTrot - {comic_id}",
                    "date": comic_id,
                    "image_url": f"/data/comics/foxtrot/{filepath.name}",
                    "link": f"https://www.gocomics.com/foxtrot/{comic_id.replace('-', '/')}",
                    "attribution": "© Bill Amend / GoComics"
                })
        
        self._save_cache()
