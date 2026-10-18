"""Peanuts daily comic collector (GoComics)"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import re
from typing import Optional, Dict, Any

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Safari/537.36'

class PeanutsCollector:
    """Fetches Peanuts daily comic image from gocomics.com."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def _build_url(self, date: Optional[datetime] = None) -> str:
        d = date or datetime.now()
        return f"https://www.gocomics.com/peanuts/{d.year:04d}/{d.month:02d}/{d.day:02d}"

    def _extract_image_url(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        # Prefer images hosted on featureassets.gocomics.com
        # Try common patterns on GC comic pages
        # 1) Look for img with srcset containing featureassets
        img = soup.select_one('img[src*="featureassets.gocomics.com"], picture img')
        if img:
            # Prefer highest-res srcset if present
            srcset = img.get('srcset') or ''
            if 'featureassets.gocomics.com' in srcset:
                # Take last candidate (usually highest width)
                parts = [p.strip() for p in srcset.split(',') if p.strip()]
                if parts:
                    last = parts[-1]
                    url = last.split(' ')[0]
                    return url
            # Fallback to src
            src = img.get('src')
            if src and 'featureassets.gocomics.com' in src:
                return src
        # Regex fallback in entire HTML
        m = re.search(r'https://featureassets\.gocomics\.com/assets/[a-f0-9]+\?[^"\s>]+', html)
        if m:
            return m.group(0)
        return None

    async def get_comic(self, date: Optional[datetime] = None, save: bool = False) -> Dict[str, Any]:
        url = self._build_url(date)
        async with httpx.AsyncClient(timeout=self.timeout, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9'}) as client:
            r = await client.get(url, follow_redirects=True)
            r.raise_for_status()
            image_url = self._extract_image_url(r.text)
            result = {
                'success': bool(image_url),
                'date': (date or datetime.now()).strftime('%Y-%m-%d'),
                'page_url': url,
                'image_url': image_url
            }
            if save and image_url:
                await self._save_image(client, image_url, result['date'])
                result['saved'] = True
            return result

    async def _save_image(self, client: httpx.AsyncClient, image_url: str, date_str: str) -> None:
        data_dir = Path('data/peanuts')
        data_dir.mkdir(parents=True, exist_ok=True)
        # Choose extension based on URL parameters (usually jpg or png)
        ext = '.jpg'
        if '.png' in image_url:
            ext = '.png'
        out = data_dir / f'{date_str}{ext}'
        resp = await client.get(image_url)
        resp.raise_for_status()
        out.write_bytes(resp.content)

if __name__ == '__main__':
    async def _test():
        c = PeanutsCollector()
        print(await c.get_comic(save=False))
    asyncio.run(_test())
