#!/usr/bin/env python3
"""
Nightly cleanup script for dashboard content.
Removes unliked content and preserves liked content for personality training.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from database import DatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'logs' / f'nightly_cleanup_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class NightlyCleanupManager:
    """Manages nightly cleanup of dashboard content."""
    
    def __init__(self):
        """Initialize cleanup manager."""
        self.db = DatabaseManager()
        
    def run_cleanup(self):
        """Run the nightly cleanup process."""
        logger.info("Starting nightly cleanup process...")
        
        try:
            # Run content cleanup
            cleanup_stats = self.db.cleanup_unliked_content()
            
            # Generate personality profile update
            personality_profile = self.db.get_personality_profile()
            liked_content = self.db.get_liked_content_summary()
            
            # Log results
            logger.info(f"Cleanup completed successfully:")
            logger.info(f"  - News articles removed: {cleanup_stats['news']}")
            logger.info(f"  - Music content removed: {cleanup_stats['music']}")
            logger.info(f"  - Vanity alerts removed: {cleanup_stats['vanity_alerts']}")
            logger.info(f"  - Total items preserved: {cleanup_stats['preserved']}")
            logger.info(f"  - Total liked items in profile: {liked_content['total_count']}")
            
            # Save personality profile to file for AI training
            self._save_personality_profile(personality_profile, liked_content)
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Error during nightly cleanup: {e}")
            raise

    def _save_personality_profile(self, personality_profile: dict, liked_content: dict):
        """Save personality profile to file for AI training."""
        try:
            profile_dir = project_root / 'data' / 'personality_profiles'
            profile_dir.mkdir(parents=True, exist_ok=True)
            
            # Save current profile
            profile_file = profile_dir / 'current_personality_profile.json'
            with open(profile_file, 'w') as f:
                import json
                json.dump({
                    'personality_profile': personality_profile,
                    'liked_content_summary': liked_content,
                    'generated_at': datetime.now().isoformat()
                }, f, indent=2)
            
            # Save historical profile with timestamp
            historical_file = profile_dir / f'personality_profile_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(historical_file, 'w') as f:
                json.dump({
                    'personality_profile': personality_profile,
                    'liked_content_summary': liked_content,
                    'generated_at': datetime.now().isoformat()
                }, f, indent=2)
            
            logger.info(f"Personality profile saved to {profile_file}")
            
        except Exception as e:
            logger.error(f"Error saving personality profile: {e}")


def main():
    """Main entry point for nightly cleanup."""
    cleanup_manager = NightlyCleanupManager()
    
    try:
        stats = cleanup_manager.run_cleanup()
        print(f"Nightly cleanup completed successfully: {stats}")
        return 0
    except Exception as e:
        print(f"Nightly cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
