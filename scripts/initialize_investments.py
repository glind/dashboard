#!/usr/bin/env python3
"""
Initialize default investments for tracking.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager

def initialize_default_investments():
    """Initialize default investments for tracking."""
    db = DatabaseManager()
    
    # Default investments to track
    default_investments = [
        # Stocks
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "stock"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "stock"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "stock"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "type": "stock"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "stock"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "stock"},
        
        # Crypto
        {"symbol": "BTC", "name": "Bitcoin", "type": "crypto"},
        {"symbol": "ETH", "name": "Ethereum", "type": "crypto"},
        {"symbol": "ADA", "name": "Cardano", "type": "crypto"},
        {"symbol": "DOT", "name": "Polkadot", "type": "crypto"},
        
        # Currencies
        {"symbol": "EUR/USD", "name": "Euro to US Dollar", "type": "currency"},
        {"symbol": "GBP/USD", "name": "British Pound to US Dollar", "type": "currency"},
    ]
    
    print("Initializing default investments...")
    
    # Get existing investments to avoid duplicates
    existing_investments = db.get_tracked_investments()
    existing_symbols = {inv['symbol'] for inv in existing_investments}
    
    added_count = 0
    for investment in default_investments:
        if investment['symbol'] not in existing_symbols:
            try:
                db.save_investment_data(
                    symbol=investment['symbol'],
                    name=investment['name'],
                    inv_type=investment['type'],
                    data={
                        "source": "default",
                        "current_price": 0,
                        "is_tracked": True
                    }
                )
                print(f"✅ Added: {investment['symbol']} ({investment['name']})")
                added_count += 1
            except Exception as e:
                print(f"❌ Failed to add {investment['symbol']}: {e}")
        else:
            print(f"⏭️  Skipped: {investment['symbol']} (already exists)")
    
    print(f"\n🎉 Added {added_count} new investments")
    print(f"💰 Total tracked: {len(db.get_tracked_investments())}")

if __name__ == "__main__":
    initialize_default_investments()