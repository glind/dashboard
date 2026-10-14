#!/usr/bin/env python3
"""
Test script to manually run vanity alerts collection and see results.
Usage: python3 scripts/test_vanity_alerts.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from collectors.vanity_alerts_collector import VanityAlertsCollector
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Test vanity alerts collection."""
    print("=" * 80)
    print("VANITY ALERTS COLLECTION TEST")
    print("=" * 80)
    
    collector = VanityAlertsCollector()
    
    # Show search terms being used
    print("\n📝 Search Terms Configuration:")
    print("-" * 80)
    for category, terms in collector.search_terms.items():
        if terms:
            print(f"\n{category.upper()} ({len(terms)} terms):")
            for term in terms[:5]:  # Show first 5 terms per category
                print(f"  • {term}")
            if len(terms) > 5:
                print(f"  ... and {len(terms) - 5} more")
    
    print("\n\n🔍 Collecting alerts from all sources...")
    print("-" * 80)
    
    # Collect alerts
    alerts = await collector.collect_all_alerts()
    
    print(f"\n✅ Collection complete!")
    print(f"   Total alerts found: {len(alerts)}")
    
    # Filter by confidence
    high_conf = [a for a in alerts if a.confidence_score > 0.5]
    med_conf = [a for a in alerts if 0.3 <= a.confidence_score <= 0.5]
    low_conf = [a for a in alerts if a.confidence_score < 0.3]
    
    print(f"   High confidence (>0.5): {len(high_conf)}")
    print(f"   Medium confidence (0.3-0.5): {len(med_conf)}")
    print(f"   Low confidence (<0.3): {len(low_conf)}")
    
    # Show top 10 alerts
    if alerts:
        print("\n\n🏆 Top 10 Alerts:")
        print("-" * 80)
        
        for i, alert in enumerate(alerts[:10], 1):
            print(f"\n{i}. {alert.title}")
            print(f"   Source: {alert.source}")
            print(f"   Search Term: {alert.search_term}")
            print(f"   Confidence: {alert.confidence_score:.2f}")
            print(f"   URL: {alert.url}")
            if alert.snippet:
                print(f"   Snippet: {alert.snippet[:150]}...")
        
        # Save to database
        print("\n\n💾 Saving alerts to database...")
        collector.save_alerts_to_database(alerts)
        print(f"   ✅ Saved {len(alerts)} alerts to database")
    else:
        print("\n⚠️  No alerts found. Check your search terms and try again.")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
