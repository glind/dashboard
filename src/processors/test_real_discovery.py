#!/usr/bin/env python3
"""
Standalone Real Lead Discovery Test
==================================

Test the startup discovery system independently to validate it works
before integrating with the main dashboard system.
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from startup_discovery import discover_real_startups

async def test_real_lead_discovery():
    """Test the real startup discovery system"""
    print("🚀 Testing Real Startup Discovery System")
    print("=" * 50)
    
    # Test with technology-focused search terms
    test_preferences = {
        'high_value_keywords': ['saas', 'automation', 'api', 'ai', 'fintech'],
        'preferred_industries': ['Technology', 'Software Development']
    }
    
    try:
        print("Discovering real startups...")
        leads = await discover_real_startups(test_preferences, 10)
        
        print(f"\n✅ Successfully discovered {len(leads)} startup leads!")
        print("\nTop Leads Found:")
        print("-" * 30)
        
        for i, lead in enumerate(leads[:5], 1):
            print(f"{i}. {lead['company_name']}")
            print(f"   Score: {lead['match_score']:.2f}")
            print(f"   Source: {', '.join(lead['data_sources'])}")
            print(f"   Industry: {lead['industry']}")
            if lead['website']:
                print(f"   Website: {lead['website']}")
            print(f"   Reasons: {', '.join(lead['match_reasons'][:2])}")
            print()
        
        # Test statistics
        high_quality = sum(1 for lead in leads if lead['match_score'] > 0.7)
        avg_score = sum(lead['match_score'] for lead in leads) / len(leads) if leads else 0
        
        print(f"📊 Discovery Statistics:")
        print(f"   Total leads: {len(leads)}")
        print(f"   High-quality leads (>0.7): {high_quality}")
        print(f"   Average score: {avg_score:.2f}")
        print(f"   Unique sources: {len(set(source for lead in leads for source in lead['data_sources']))}")
        
    except Exception as e:
        print(f"❌ Error during discovery: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_lead_discovery())