#!/usr/bin/env python3
"""
Hourly vanity alerts monitor script.
This script runs every hour to collect vanity alerts about Gregory Lind, Buildly, music, and book.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from collectors.vanity_alerts_collector import VanityAlertsCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vanity_alerts.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def run_vanity_alerts_collection():
    """Run the vanity alerts collection process."""
    logger.info("Starting vanity alerts collection...")
    
    try:
        collector = VanityAlertsCollector()
        
        # Collect new alerts
        alerts = await collector.collect_all_alerts()
        
        if alerts:
            # Save to database
            collector.save_alerts_to_database(alerts)
            
            # Log summary
            high_confidence_alerts = [a for a in alerts if a.confidence_score > 0.5]
            logger.info(f"Collection complete: {len(alerts)} total alerts, {len(high_confidence_alerts)} high confidence")
            
            # Log top alerts for review
            for alert in alerts[:3]:  # Top 3 alerts
                logger.info(f"Top alert: {alert.title} (confidence: {alert.confidence_score:.2f}, source: {alert.source})")
        else:
            logger.info("No new alerts found this run")
            
    except Exception as e:
        logger.error(f"Error during vanity alerts collection: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    logger.info("Vanity alerts monitor started")
    
    try:
        # Run the collection
        asyncio.run(run_vanity_alerts_collection())
        logger.info("Vanity alerts monitor completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Vanity alerts monitor interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in vanity alerts monitor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
