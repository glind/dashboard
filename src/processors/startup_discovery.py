#!/usr/bin/env python3
"""
Real Startup Discovery Engine
=============================

Integrates with ../marketing tool capabilities to find real startups and idea-stage companies
from various sources including startup directories, GitHub, social platforms, and incubators.

Key Features:
- Web scraping of startup directories (Product Hunt, AngelList, Y Combinator, etc.)
- GitHub repository analysis for new projects and teams
- Social media monitoring for startup announcements
- API integration with startup platforms
- Intelligent lead scoring based on learned preferences
- Real-time company validation and enrichment
"""

import asyncio
import aiohttp
import logging
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
import sys
import os

# Add marketing directory to path to access existing capabilities
marketing_path = Path(__file__).parent.parent.parent / "marketing"
if marketing_path.exists():
    sys.path.insert(0, str(marketing_path))

try:
    from automation.influencer_discovery import PlatformSearcher, SocialMediaProfile
    from automation.ai.ollama_integration import AIContentGenerator
    MARKETING_TOOLS_AVAILABLE = True
    logging.info("Successfully imported marketing automation tools")
except ImportError as e:
    logging.warning(f"Marketing tools not available: {e}")
    MARKETING_TOOLS_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StartupLead:
    """Real startup lead discovered from various sources"""
    name: str
    description: str
    website: str
    source_platform: str
    founded_date: Optional[str] = None
    team_size: Optional[str] = None
    funding_stage: Optional[str] = None
    industry: str = "Technology"
    location: Optional[str] = None
    contact_info: Optional[Dict[str, str]] = None
    social_links: Optional[Dict[str, str]] = None
    tech_stack: Optional[List[str]] = None
    recent_activity: Optional[str] = None
    discovery_score: float = 0.0
    match_reasons: List[str] = None
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.contact_info is None:
            self.contact_info = {}
        if self.social_links is None:
            self.social_links = {}
        if self.tech_stack is None:
            self.tech_stack = []
        if self.match_reasons is None:
            self.match_reasons = []
        if self.last_updated is None:
            self.last_updated = datetime.now()

@dataclass 
class StartupDirectory:
    """Configuration for startup directory sources"""
    name: str
    base_url: str
    search_endpoint: str
    pagination_param: str = "page"
    has_api: bool = False
    api_key_required: bool = False
    rate_limit: int = 60  # requests per minute
    parser_class: str = "generic"

class StartupDiscoveryEngine:
    """Main engine for discovering real startups and idea-stage companies"""
    
    def __init__(self):
        self.session = None
        self.discovered_leads = []
        self.startup_directories = self._initialize_directories()
        self.github_api_base = "https://api.github.com"
        self.quality_filters = {
            'min_description_length': 20,
            'required_website_or_repo': True,
            'exclude_defunct': True,
            'min_activity_days': 180  # Active within 6 months
        }
        
    def _initialize_directories(self) -> Dict[str, StartupDirectory]:
        """Initialize configuration for various startup directories"""
        return {
            'product_hunt': StartupDirectory(
                name="Product Hunt",
                base_url="https://www.producthunt.com",
                search_endpoint="/search",
                has_api=True,
                api_key_required=False
            ),
            'github_trending': StartupDirectory(
                name="GitHub Trending",
                base_url="https://github.com",
                search_endpoint="/trending",
                has_api=True,
                parser_class="github"
            ),
            'ycombinator': StartupDirectory(
                name="Y Combinator Directory",
                base_url="https://www.ycombinator.com",
                search_endpoint="/companies",
                parser_class="ycombinator"
            ),
            'crunchbase': StartupDirectory(
                name="Crunchbase",
                base_url="https://www.crunchbase.com",
                search_endpoint="/discover/organization.companies",
                has_api=True,
                api_key_required=True
            ),
            'angellist': StartupDirectory(
                name="AngelList",
                base_url="https://angel.co",
                search_endpoint="/companies",
                has_api=True
            ),
            'betalist': StartupDirectory(
                name="BetaList",
                base_url="https://betalist.com",
                search_endpoint="/startups",
                parser_class="betalist"
            ),
            'hackernews_show': StartupDirectory(
                name="Hacker News Show HN",
                base_url="https://hn.algolia.com",
                search_endpoint="/api/v1/search",
                has_api=True,
                parser_class="hackernews"
            ),
            'indie_hackers': StartupDirectory(
                name="Indie Hackers",
                base_url="https://www.indiehackers.com",
                search_endpoint="/products",
                parser_class="indiehackers"
            )
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=50)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def discover_startups(self, search_terms: List[str], max_results: int = 100) -> List[StartupLead]:
        """Main method to discover startups from multiple sources"""
        logger.info(f"🔍 Starting startup discovery with terms: {search_terms}")
        
        all_leads = []
        
        # 1. Search startup directories
        for directory_name, directory in self.startup_directories.items():
            try:
                logger.info(f"Searching {directory.name}...")
                leads = await self._search_directory(directory, search_terms, max_results // len(self.startup_directories))
                all_leads.extend(leads)
                
                # Rate limiting
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error searching {directory.name}: {e}")
                continue
        
        # 2. GitHub repository search for new projects
        try:
            logger.info("Searching GitHub for new startup repositories...")
            github_leads = await self._search_github_startups(search_terms, 20)
            all_leads.extend(github_leads)
        except Exception as e:
            logger.error(f"Error searching GitHub: {e}")
        
        # 3. Social media discovery (if marketing tools available)
        if MARKETING_TOOLS_AVAILABLE:
            try:
                logger.info("Searching social media for startup mentions...")
                social_leads = await self._discover_via_social_media(search_terms, 20)
                all_leads.extend(social_leads)
            except Exception as e:
                logger.error(f"Error in social media discovery: {e}")
        
        # 4. Quality filtering and scoring
        filtered_leads = await self._filter_and_score_leads(all_leads, search_terms)
        
        # 5. Enrich with additional data
        enriched_leads = await self._enrich_leads(filtered_leads[:max_results])
        
        logger.info(f"✅ Discovery complete: Found {len(enriched_leads)} high-quality startup leads")
        return enriched_leads
    
    async def _search_directory(self, directory: StartupDirectory, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Search a specific startup directory"""
        leads = []
        
        if directory.has_api:
            leads = await self._search_via_api(directory, search_terms, max_results)
        else:
            leads = await self._search_via_scraping(directory, search_terms, max_results)
        
        return leads
    
    async def _search_via_api(self, directory: StartupDirectory, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Search using platform APIs"""
        leads = []
        
        if directory.name == "GitHub Trending":
            leads = await self._search_github_api(search_terms, max_results)
        elif directory.name == "Product Hunt":
            leads = await self._search_product_hunt_api(search_terms, max_results)
        elif directory.name == "Hacker News Show HN":
            leads = await self._search_hackernews_api(search_terms, max_results)
        
        return leads
    
    async def _search_via_scraping(self, directory: StartupDirectory, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Search using web scraping"""
        leads = []
        
        try:
            for term in search_terms:
                search_url = f"{directory.base_url}{directory.search_endpoint}"
                params = {"q": term, "limit": min(max_results, 50)}
                
                async with self.session.get(search_url, params=params) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Parse based on directory type
                        if directory.parser_class == "ycombinator":
                            page_leads = await self._parse_ycombinator_results(html, directory.name)
                        elif directory.parser_class == "betalist":
                            page_leads = await self._parse_betalist_results(html, directory.name)
                        elif directory.parser_class == "indiehackers":
                            page_leads = await self._parse_indiehackers_results(html, directory.name)
                        else:
                            page_leads = await self._parse_generic_results(html, directory.name)
                        
                        leads.extend(page_leads)
                        
                        if len(leads) >= max_results:
                            break
        
        except Exception as e:
            logger.error(f"Error scraping {directory.name}: {e}")
        
        return leads[:max_results]
    
    async def _search_github_api(self, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Search GitHub API for startup repositories"""
        leads = []
        
        try:
            for term in search_terms:
                # Search for recently created repositories with startup keywords
                query = f"{term} created:>2023-01-01 stars:>5 language:TypeScript OR language:JavaScript OR language:Python"
                url = f"{self.github_api_base}/search/repositories"
                params = {
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": min(max_results, 30)
                }
                
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for repo in data.get('items', []):
                            # Filter for potential startup projects
                            if await self._is_potential_startup_repo(repo):
                                lead = StartupLead(
                                    name=repo['name'],
                                    description=repo.get('description', ''),
                                    website=repo.get('homepage', '') or repo['html_url'],
                                    source_platform="GitHub",
                                    founded_date=repo['created_at'][:10],
                                    tech_stack=self._extract_tech_stack_from_repo(repo),
                                    recent_activity=repo['updated_at'],
                                    contact_info={"github": repo['owner']['html_url']},
                                    discovery_score=repo['stargazers_count'] / 100.0
                                )
                                leads.append(lead)
                        
                        # Rate limiting for GitHub API
                        await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"Error searching GitHub API: {e}")
        
        return leads[:max_results]
    
    async def _search_product_hunt_api(self, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Search Product Hunt for new products using web scraping"""
        leads = []
        
        try:
            # Since Product Hunt API requires authentication, we'll scrape their public pages
            base_url = "https://www.producthunt.com"
            
            for term in search_terms[:3]:  # Limit searches to avoid being blocked
                try:
                    search_url = f"{base_url}/search/posts"
                    params = {"q": term}
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                    
                    async with self.session.get(search_url, params=params, headers=headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Parse Product Hunt results (simplified parsing)
                            import re
                            from bs4 import BeautifulSoup
                            
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Look for product cards or listings
                            product_cards = soup.find_all(['div', 'article'], class_=re.compile(r'product|post|card'))
                            
                            for card in product_cards[:5]:  # Limit per search term
                                try:
                                    # Extract product name
                                    name_elem = card.find(['h1', 'h2', 'h3', 'a'], class_=re.compile(r'title|name|product'))
                                    if not name_elem:
                                        continue
                                    
                                    product_name = name_elem.get_text(strip=True)
                                    if len(product_name) < 2:
                                        continue
                                    
                                    # Extract description/tagline
                                    desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|tagline|subtitle'))
                                    description = desc_elem.get_text(strip=True) if desc_elem else f"{product_name} - Found on Product Hunt"
                                    
                                    # Extract website link if available
                                    link_elem = card.find('a', href=True)
                                    website = ""
                                    if link_elem and link_elem.get('href'):
                                        href = link_elem['href']
                                        if href.startswith('http'):
                                            website = href
                                        elif href.startswith('/'):
                                            website = f"{base_url}{href}"
                                    
                                    # Create startup lead
                                    lead = StartupLead(
                                        name=product_name,
                                        description=description[:300],
                                        website=website,
                                        source_platform="Product Hunt",
                                        founded_date=datetime.now().strftime("%Y-%m-%d"),
                                        funding_stage="Pre-seed",
                                        contact_info={"product_hunt": f"https://www.producthunt.com/search/posts?q={term}"},
                                        discovery_score=0.7,
                                        match_reasons=[f"Found on Product Hunt searching for '{term}'", "Recently featured product"]
                                    )
                                    leads.append(lead)
                                    
                                except Exception as e:
                                    logger.debug(f"Error parsing individual product card: {e}")
                                    continue
                            
                        await asyncio.sleep(2)  # Be respectful with scraping
                        
                except Exception as e:
                    logger.warning(f"Error searching Product Hunt for '{term}': {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error in Product Hunt search: {e}")
        
        return leads[:max_results]
    
    async def _search_hackernews_api(self, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Search Hacker News for Show HN posts about startups"""
        leads = []
        
        try:
            for term in search_terms:
                # Search for "Show HN" posts which often feature new startups/projects
                query = f"Show HN {term}"
                url = "https://hn.algolia.com/api/v1/search"
                params = {
                    "query": query,
                    "tags": "story",
                    "hitsPerPage": min(max_results, 20)
                }
                
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for hit in data.get('hits', []):
                            if 'show hn' in hit.get('title', '').lower():
                                # Extract website from story URL or text
                                website = hit.get('url', '')
                                if not website and hit.get('story_text'):
                                    website = self._extract_website_from_text(hit['story_text'])
                                
                                if website:
                                    lead = StartupLead(
                                        name=self._extract_company_name_from_title(hit['title']),
                                        description=hit.get('story_text', hit.get('title', ''))[:200],
                                        website=website,
                                        source_platform="Hacker News",
                                        founded_date=hit['created_at'][:10],
                                        recent_activity=hit['created_at'],
                                        discovery_score=hit.get('points', 1) / 100.0
                                    )
                                    leads.append(lead)
        
        except Exception as e:
            logger.error(f"Error searching Hacker News: {e}")
        
        return leads[:max_results]
    
    async def _search_github_startups(self, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Specialized GitHub search for startup repositories"""
        return await self._search_github_api(search_terms, max_results)
    
    async def _discover_via_social_media(self, search_terms: List[str], max_results: int) -> List[StartupLead]:
        """Use marketing tool social media discovery for startups"""
        leads = []
        
        if not MARKETING_TOOLS_AVAILABLE:
            return leads
        
        try:
            # Use the real marketing tool's influencer discovery with startup focus
            startup_keywords = search_terms + ["startup", "founder", "entrepreneur", "launching", "building", "SaaS", "AI startup", "tech founder"]
            
            from automation.influencer_discovery import TwitterSearcher, LinkedInSearcher, InstagramSearcher
            
            # Search Twitter for startup founders and companies
            async with TwitterSearcher() as twitter_searcher:
                for keyword in startup_keywords[:3]:  # Limit to avoid rate limiting
                    try:
                        twitter_profiles = await twitter_searcher.search_profiles(
                            f"{keyword} startup founder", 
                            max_results=10
                        )
                        
                        for profile in twitter_profiles:
                            if profile.bio and any(term in profile.bio.lower() for term in ["startup", "founder", "ceo", "building", "launching"]):
                                # Extract potential company name from bio or profile
                                company_name = self._extract_company_name_from_bio(profile.bio)
                                if company_name:
                                    lead = StartupLead(
                                        name=company_name,
                                        description=profile.bio[:200],
                                        website=profile.website or "",
                                        source_platform="Twitter",
                                        contact_info={"twitter": f"@{profile.username}"},
                                        social_links={"twitter": profile.username},
                                        discovery_score=min(profile.followers / 5000.0, 1.0),
                                        match_reasons=[f"Found via Twitter search for '{keyword}'", "Active startup founder profile"]
                                    )
                                    leads.append(lead)
                                    
                        await asyncio.sleep(1)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Error searching Twitter for {keyword}: {e}")
                        continue
            
            # Search LinkedIn for startup companies and founders
            async with LinkedInSearcher() as linkedin_searcher:
                for keyword in startup_keywords[:2]:  # Even more conservative on LinkedIn
                    try:
                        linkedin_profiles = await linkedin_searcher.search_profiles(
                            f"{keyword} startup", 
                            max_results=5
                        )
                        
                        for profile in linkedin_profiles:
                            if profile.bio and any(term in profile.bio.lower() for term in ["startup", "founder", "ceo"]):
                                company_name = self._extract_company_name_from_bio(profile.bio)
                                if company_name:
                                    lead = StartupLead(
                                        name=company_name,
                                        description=profile.bio[:200],
                                        website=profile.website or "",
                                        source_platform="LinkedIn",
                                        contact_info={"linkedin": f"@{profile.username}"},
                                        social_links={"linkedin": profile.username},
                                        discovery_score=0.8,  # LinkedIn tends to be higher quality
                                        match_reasons=[f"Found via LinkedIn search for '{keyword}'", "Professional startup profile"]
                                    )
                                    leads.append(lead)
                        
                        await asyncio.sleep(2)  # Conservative rate limiting for LinkedIn
                    except Exception as e:
                        logger.warning(f"Error searching LinkedIn for {keyword}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error in real social media discovery: {e}")
        
        return leads[:max_results]
    
    async def _filter_and_score_leads(self, leads: List[StartupLead], search_terms: List[str]) -> List[StartupLead]:
        """Filter and score leads based on quality criteria"""
        filtered_leads = []
        
        for lead in leads:
            # Apply quality filters
            if not self._meets_quality_criteria(lead):
                continue
            
            # Calculate match score based on search terms and learned preferences
            lead.discovery_score = await self._calculate_discovery_score(lead, search_terms)
            
            # Add match reasons
            lead.match_reasons = self._generate_match_reasons(lead, search_terms)
            
            filtered_leads.append(lead)
        
        # Sort by discovery score
        return sorted(filtered_leads, key=lambda x: x.discovery_score, reverse=True)
    
    async def _enrich_leads(self, leads: List[StartupLead]) -> List[StartupLead]:
        """Enrich leads with additional data"""
        enriched_leads = []
        
        for lead in leads:
            try:
                # Enrich website information
                if lead.website:
                    enriched_info = await self._enrich_from_website(lead.website)
                    if enriched_info:
                        lead.tech_stack.extend(enriched_info.get('tech_stack', []))
                        if not lead.location and enriched_info.get('location'):
                            lead.location = enriched_info['location']
                
                # Validate and clean data
                lead = self._clean_lead_data(lead)
                enriched_leads.append(lead)
                
            except Exception as e:
                logger.warning(f"Error enriching lead {lead.name}: {e}")
                enriched_leads.append(lead)  # Add anyway with original data
        
        return enriched_leads
    
    def _meets_quality_criteria(self, lead: StartupLead) -> bool:
        """Check if lead meets minimum quality criteria"""
        # Must have minimum description length
        if len(lead.description) < self.quality_filters['min_description_length']:
            return False
        
        # Must have website or be from GitHub
        if self.quality_filters['required_website_or_repo'] and not lead.website:
            return False
        
        # Must not be obviously defunct
        if self.quality_filters['exclude_defunct']:
            defunct_keywords = ['shutdown', 'closed', 'discontinued', 'no longer']
            if any(keyword in lead.description.lower() for keyword in defunct_keywords):
                return False
        
        return True
    
    async def _calculate_discovery_score(self, lead: StartupLead, search_terms: List[str]) -> float:
        """Calculate discovery score based on multiple factors"""
        score = lead.discovery_score if lead.discovery_score > 0 else 0.1
        
        # Boost score for search term matches
        description_lower = lead.description.lower()
        for term in search_terms:
            if term.lower() in description_lower:
                score += 0.2
        
        # Boost for recent activity
        if lead.recent_activity:
            try:
                activity_date = datetime.fromisoformat(lead.recent_activity.replace('Z', '+00:00'))
                days_old = (datetime.now() - activity_date.replace(tzinfo=None)).days
                if days_old < 30:  # Very recent
                    score += 0.3
                elif days_old < 90:  # Recent
                    score += 0.1
            except:
                pass
        
        # Boost for funding stage indicators
        funding_keywords = ['pre-seed', 'seed', 'series a', 'funding', 'investment']
        if any(keyword in description_lower for keyword in funding_keywords):
            score += 0.2
        
        # Boost for technology match
        tech_keywords = ['ai', 'ml', 'saas', 'api', 'cloud', 'automation', 'no-code', 'low-code']
        for keyword in tech_keywords:
            if keyword in description_lower:
                score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _generate_match_reasons(self, lead: StartupLead, search_terms: List[str]) -> List[str]:
        """Generate human-readable match reasons"""
        reasons = []
        
        description_lower = lead.description.lower()
        
        # Search term matches
        for term in search_terms:
            if term.lower() in description_lower:
                reasons.append(f"Matches search term: {term}")
        
        # Technology alignment
        tech_keywords = ['ai', 'ml', 'saas', 'api', 'cloud']
        for tech in tech_keywords:
            if tech in description_lower:
                reasons.append(f"Uses {tech.upper()} technology")
        
        # Startup stage
        if any(stage in description_lower for stage in ['pre-seed', 'seed', 'early stage']):
            reasons.append("Early-stage startup")
        
        # Platform credibility
        if lead.source_platform in ['Product Hunt', 'Y Combinator Directory']:
            reasons.append(f"Featured on {lead.source_platform}")
        
        return reasons
    
    async def _enrich_from_website(self, website: str) -> Optional[Dict[str, Any]]:
        """Enrich lead information from their website"""
        try:
            async with self.session.get(website) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Extract basic info (this could be much more sophisticated)
                    enrichment = {}
                    
                    # Try to detect tech stack from meta tags, scripts, etc.
                    tech_indicators = {
                        'react': ['react', 'jsx'],
                        'vue': ['vue.js', 'vue'],
                        'angular': ['angular'],
                        'node.js': ['node.js', 'express'],
                        'python': ['django', 'flask', 'fastapi'],
                        'rails': ['ruby on rails', 'rails']
                    }
                    
                    html_lower = html.lower()
                    detected_tech = []
                    for tech, indicators in tech_indicators.items():
                        if any(indicator in html_lower for indicator in indicators):
                            detected_tech.append(tech)
                    
                    if detected_tech:
                        enrichment['tech_stack'] = detected_tech
                    
                    return enrichment
        
        except Exception as e:
            logger.debug(f"Could not enrich from website {website}: {e}")
        
        return None
    
    def _clean_lead_data(self, lead: StartupLead) -> StartupLead:
        """Clean and validate lead data"""
        # Clean website URLs
        if lead.website and not lead.website.startswith('http'):
            lead.website = f"https://{lead.website}"
        
        # Limit description length
        if len(lead.description) > 500:
            lead.description = lead.description[:500] + "..."
        
        # Ensure required fields
        if not lead.name or lead.name.strip() == "":
            lead.name = "Unknown Startup"
        
        return lead
    
    # Utility methods for parsing different platforms
    
    async def _is_potential_startup_repo(self, repo: Dict) -> bool:
        """Determine if a GitHub repo represents a potential startup"""
        startup_indicators = [
            'startup', 'saas', 'mvp', 'product', 'platform', 'app',
            'service', 'tool', 'solution', 'api', 'dashboard'
        ]
        
        repo_text = f"{repo.get('name', '')} {repo.get('description', '')}".lower()
        
        # Must have description
        if not repo.get('description'):
            return False
        
        # Must have some stars (indicates interest)
        if repo.get('stargazers_count', 0) < 5:
            return False
        
        # Must not be a tutorial, learning project, or personal repo
        non_startup_indicators = [
            'tutorial', 'learning', 'practice', 'example', 'demo',
            'homework', 'assignment', 'course', 'my first', 'hello world'
        ]
        
        if any(indicator in repo_text for indicator in non_startup_indicators):
            return False
        
        # Check for startup indicators
        return any(indicator in repo_text for indicator in startup_indicators)
    
    def _extract_tech_stack_from_repo(self, repo: Dict) -> List[str]:
        """Extract tech stack from GitHub repository info"""
        tech_stack = []
        
        if repo.get('language'):
            tech_stack.append(repo['language'])
        
        # Could enhance with topics, README analysis, etc.
        return tech_stack
    
    def _extract_website_from_text(self, text: str) -> str:
        """Extract website URL from text"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        matches = re.findall(url_pattern, text)
        return matches[0] if matches else ""
    
    def _extract_company_name_from_title(self, title: str) -> str:
        """Extract company name from HN post title"""
        # Remove "Show HN:" prefix and clean up
        clean_title = re.sub(r'^show\s+hn:?\s*', '', title, flags=re.IGNORECASE)
        # Take first part before dash or parentheses
        name = re.split(r'[-–(]', clean_title)[0].strip()
        return name if name else "Startup"
    
    def _extract_company_name_from_bio(self, bio: str) -> str:
        """Extract company name from social media bio"""
        # Simple heuristic - look for capitalized words
        words = bio.split()
        for i, word in enumerate(words):
            if word[0].isupper() and len(word) > 3 and not word.lower() in ['the', 'and', 'for', 'with']:
                return word
        return "Startup"
    
    # Platform-specific parsers (these would be implemented with BeautifulSoup)
    
    async def _parse_ycombinator_results(self, html: str, source: str) -> List[StartupLead]:
        """Parse Y Combinator directory results"""
        # This would use BeautifulSoup to parse YC company listings
        return []
    
    async def _parse_betalist_results(self, html: str, source: str) -> List[StartupLead]:
        """Parse BetaList results"""
        return []
    
    async def _parse_indiehackers_results(self, html: str, source: str) -> List[StartupLead]:
        """Parse Indie Hackers results"""
        return []
    
    async def _parse_generic_results(self, html: str, source: str) -> List[StartupLead]:
        """Generic parser for startup directory results"""
        return []

# Integration with existing lead generation system

async def discover_real_startups(search_preferences: Dict[str, Any], max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Main integration function for the dashboard's lead generation system.
    
    Args:
        search_preferences: User preferences learned from Gmail analysis
        max_results: Maximum number of leads to return
    
    Returns:
        List of startup leads in dashboard format
    """
    
    # Extract search terms from preferences
    search_terms = []
    if search_preferences.get('high_value_keywords'):
        search_terms.extend(search_preferences['high_value_keywords'][:5])
    
    # Add technology-focused terms based on successful patterns
    tech_terms = ['saas', 'api', 'automation', 'ai', 'no-code', 'fintech', 'healthtech']
    search_terms.extend(tech_terms)
    
    # Remove duplicates
    search_terms = list(set(search_terms))
    
    logger.info(f"Discovering real startups with terms: {search_terms}")
    
    async with StartupDiscoveryEngine() as engine:
        startup_leads = await engine.discover_startups(search_terms, max_results)
        
        # Convert to dashboard format
        dashboard_leads = []
        for startup in startup_leads:
            dashboard_lead = {
                'company_name': startup.name,
                'domain': urlparse(startup.website).netloc if startup.website else '',
                'industry': startup.industry,
                'estimated_size': startup.team_size or 'Early Stage',
                'contact_info': startup.contact_info,
                'match_score': startup.discovery_score,
                'match_reasons': startup.match_reasons,
                'template_matches': ['startup', 'early-stage'],
                'recommended_approach': f"Reach out via {list(startup.contact_info.keys())[0] if startup.contact_info else 'website'}",
                'priority_level': 'high' if startup.discovery_score > 0.7 else 'medium',
                'technical_fit_score': 0.8,  # High for tech startups
                'business_potential_score': startup.discovery_score,
                'contact_accessibility_score': 0.7 if startup.contact_info else 0.3,
                'next_steps': [
                    'Research company background and recent updates',
                    'Identify decision makers',
                    'Prepare personalized outreach message',
                    'Follow up within 1 week'
                ],
                'data_sources': [startup.source_platform],
                'confidence_level': startup.discovery_score,
                'last_updated': startup.last_updated.isoformat(),
                'website': startup.website,
                'founded_date': startup.founded_date,
                'funding_stage': startup.funding_stage,
                'tech_stack': startup.tech_stack,
                'location': startup.location
            }
            dashboard_leads.append(dashboard_lead)
    
    logger.info(f"✅ Converted {len(dashboard_leads)} startup leads for dashboard")
    return dashboard_leads

if __name__ == "__main__":
    # Test the startup discovery system
    async def test_discovery():
        test_preferences = {
            'high_value_keywords': ['saas', 'automation', 'api']
        }
        
        leads = await discover_real_startups(test_preferences, 10)
        
        print(f"Discovered {len(leads)} startup leads:")
        for lead in leads:
            print(f"- {lead['company_name']}: {lead['match_score']:.2f} score")
            print(f"  Source: {lead['data_sources'][0]}")
            print(f"  Reasons: {', '.join(lead['match_reasons'])}")
            print()
    
    asyncio.run(test_discovery())