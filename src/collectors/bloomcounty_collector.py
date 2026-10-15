#!/usr/bin/env python3
"""
Bloom County Comic Collector

Fetches Bloom County comics from GoComics.com
- Daily fetching for current comic
- Archive download for historical comics
"""

import os
import json
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class BloomCountyCollector:
    """Collector for Bloom County comics from GoComics."""
    
    BASE_URL = "https://www.gocomics.com/bloomcounty"
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
            self.cache_dir = project_root / "data" / "comics" / "bloomcounty"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = project_root / "data" / "bloomcounty_archive.json"
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
            import re
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
            title = og_title['content'] if og_title and og_title.get('content') else "Bloom County"
            
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
                "series": "bloomcounty",
                "title": title,
                "date": comic_id,
                "image_url": image_url,
                "link": link,
                "attribution": "© Berkeley Breathed / GoComics"
            }
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _add_to_cache(self, comic: Dict[str, Any]):
        """Add comic to cache if not already present."""
        existing_ids = {c.get('id') or c.get('date') for c in self.cache.get('comics', [])}
        if comic['id'] not in existing_ids:
            self.cache['comics'].append(comic)
            self._save_cache()
    
    def get_daily(self) -> Dict[str, Any]:
        """Get today's Bloom County comic and cache it."""
        # Use today's date in URL format to get actual comic (not base URL which may be blocked)
        today = datetime.now()
        comic = self.get_by_date(today)
        if comic:
            self._add_to_cache(comic)
            return {"success": True, "comic": comic}
        # Try yesterday if today's not available yet
        yesterday = today - timedelta(days=1)
        comic = self.get_by_date(yesterday)
        if comic:
            self._add_to_cache(comic)
            return {"success": True, "comic": comic}
        return {"success": False, "error": "Failed to fetch daily comic"}
    
    def get_by_date(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Get comic for a specific date."""
        url = f"{self.BASE_URL}/{date.year}/{date.month}/{date.day}"
        return self._fetch_comic_page(url)
    
    def download_image(self, image_url: str, comic_id: str) -> Optional[str]:
        """Download and cache comic image."""
        try:
            # Determine file extension
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
                logger.info(f"Downloaded: {filename}")
                return str(filepath)
            else:
                logger.warning(f"Failed to download {image_url}: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error downloading {image_url}: {e}")
            return None
    
    def download_archive(self, years: int = 5, save_images: bool = True) -> Dict[str, Any]:
        """Download comics from the last N years."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        downloaded = 0
        failed = 0
        skipped = 0
        
        # Get existing comic IDs
        existing_ids = {c.get('id') or c.get('date') for c in self.cache.get('comics', [])}
        
        current_date = end_date
        while current_date >= start_date:
            comic_id = current_date.strftime("%Y-%m-%d")
            
            # Skip if already have it
            if comic_id in existing_ids:
                skipped += 1
                current_date -= timedelta(days=1)
                continue
            
            comic = self.get_by_date(current_date)
            if comic:
                if save_images:
                    local_path = self.download_image(comic['image_url'], comic_id)
                    if local_path:
                        comic['local_path'] = local_path
                
                self.cache['comics'].append(comic)
                existing_ids.add(comic_id)
                downloaded += 1
                
                # Save periodically
                if downloaded % 50 == 0:
                    self._save_cache()
                    logger.info(f"Progress: {downloaded} downloaded, {failed} failed, {skipped} skipped")
            else:
                failed += 1
            
            current_date -= timedelta(days=1)
            
            # Be nice to the server
            import time
            time.sleep(0.5)
        
        # Final save
        self._save_cache()
        
        return {
            "success": True,
            "downloaded": downloaded,
            "failed": failed,
            "skipped": skipped,
            "total_cached": len(self.cache['comics'])
        }
    
    def get_random(self) -> Dict[str, Any]:
        """Get a random comic from the cache."""
        import random
        if not self.cache.get('comics'):
            return self.get_daily()
        
        comic = random.choice(self.cache['comics'])
        return {"success": True, "comic": comic}
    
    def get_archive_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of cached comics sorted by date."""
        comics = sorted(self.cache.get('comics', []), key=lambda x: x['date'], reverse=True)
        return comics[:limit]


def main():
    """CLI to download Bloom County archive."""
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='Download Bloom County comics from GoComics')
    parser.add_argument('--years', type=int, default=5, help='Number of years to download (default: 5)')
    parser.add_argument('--no-images', action='store_true', help='Skip downloading images')
    parser.add_argument('--daily', action='store_true', help='Just fetch today\'s comic')
    args = parser.parse_args()
    
    collector = BloomCountyCollector()
    
    if args.daily:
        result = collector.get_daily()
        print(json.dumps(result, indent=2))
    else:
        print(f"Downloading Bloom County comics from the last {args.years} years...")
        print("This may take a while. Progress will be logged.")
        result = collector.download_archive(years=args.years, save_images=not args.no_images)
        print(f"\nComplete!")
        print(f"  Downloaded: {result['downloaded']}")
        print(f"  Failed: {result['failed']}")
        print(f"  Skipped (already cached): {result['skipped']}")
        print(f"  Total in cache: {result['total_cached']}")


if __name__ == "__main__":
    main()
