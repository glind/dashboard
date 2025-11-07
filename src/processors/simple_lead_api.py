#!/usr/bin/env python3
"""
Simple Real Lead API Endpoint
=============================

Direct integration of the real startup discovery system with the dashboard
that bypasses the template system temporarily for testing.
"""

import asyncio
import json
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from startup_discovery import discover_real_startups

async def simple_generate_real_leads(target_count: int = 10, filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Simple lead generation that directly uses startup discovery.
    
    Returns:
        Dictionary with leads and statistics in dashboard format
    """
    
    # Create search preferences
    search_preferences = {
        'high_value_keywords': ['saas', 'automation', 'api', 'ai', 'fintech', 'healthtech', 'no-code'],
        'preferred_industries': ['Technology', 'Software Development', 'SaaS']
    }
    
    # Add filter-specific keywords
    if filters:
        if filters.get('industry'):
            search_preferences['high_value_keywords'].append(filters['industry'].lower())
    
    try:
        # Discover real startups
        leads = await discover_real_startups(search_preferences, target_count)
        
        # Calculate statistics
        total_leads = len(leads)
        high_quality = sum(1 for lead in leads if lead['match_score'] > 0.7)
        avg_score = sum(lead['match_score'] for lead in leads) / total_leads if total_leads > 0 else 0
        
        return {
            "success": True,
            "leads": leads,
            "statistics": {
                "total_leads": total_leads,
                "high_quality_leads": high_quality,
                "average_score": round(avg_score, 2),
                "sources_used": len(set(source for lead in leads for source in lead['data_sources']))
            },
            "templates_used": ["real-startup-discovery"],
            "total_generated": total_leads
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "leads": [],
            "statistics": {"total_leads": 0},
            "templates_used": [],
            "total_generated": 0
        }

if __name__ == "__main__":
    # Test the simple lead generation
    async def test():
        result = await simple_generate_real_leads(5)
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())