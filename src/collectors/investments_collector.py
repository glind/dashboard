"""
Investment tracking collector for stocks, crypto, and currencies.
"""

import asyncio
import logging
import json
import aiohttp
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from database import DatabaseManager

logger = logging.getLogger(__name__)


class InvestmentsCollector:
    """Collects investment data from various sources."""
    
    def __init__(self, settings=None):
        """Initialize investments collector."""
        self.settings = settings
        self.db = DatabaseManager()
        
        # API endpoints
        self.local_api_base = "http://127.0.0.1:5003"
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.coinapi_key = os.getenv("COINAPI_KEY")
        
    async def collect_data(self) -> Dict[str, Any]:
        """Collect all investment data."""
        try:
            # Get tracked investments from database
            tracked_investments = self.db.get_tracked_investments()
            
            # Collect data from different sources
            local_data = await self.collect_local_api_data()
            stock_data = await self.collect_stock_data(tracked_investments)
            crypto_data = await self.collect_crypto_data(tracked_investments)
            
            # Combine all data
            all_investments = []
            all_investments.extend(local_data)
            all_investments.extend(stock_data)
            all_investments.extend(crypto_data)
            
            # Calculate portfolio summary
            portfolio_summary = self.calculate_portfolio_summary(all_investments)
            
            return {
                "investments": all_investments,
                "portfolio_summary": portfolio_summary,
                "local_api_available": len(local_data) > 0,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error collecting investment data: {e}")
            return {
                "investments": [],
                "portfolio_summary": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def collect_local_api_data(self) -> List[Dict[str, Any]]:
        """Collect data from local API at port 5003."""
        investments = []
        try:
            async with aiohttp.ClientSession() as session:
                # Try different endpoints that might exist on the local API
                endpoints = [
                    "/api/investments",
                    "/api/portfolio", 
                    "/api/stocks",
                    "/api/crypto",
                    "/investments",
                    "/portfolio"
                ]
                
                for endpoint in endpoints:
                    try:
                        url = f"{self.local_api_base}{endpoint}"
                        async with session.get(url, timeout=5) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.info(f"Successfully fetched data from {url}")
                                
                                # Process the data based on structure
                                if isinstance(data, list):
                                    investments.extend(self.process_local_api_data(data, endpoint))
                                elif isinstance(data, dict) and 'investments' in data:
                                    investments.extend(self.process_local_api_data(data['investments'], endpoint))
                                elif isinstance(data, dict) and 'data' in data:
                                    investments.extend(self.process_local_api_data(data['data'], endpoint))
                                
                                break  # Use first successful endpoint
                                
                    except Exception as e:
                        logger.debug(f"Endpoint {endpoint} failed: {e}")
                        continue
                        
        except Exception as e:
            logger.warning(f"Local API not available: {e}")
            
        return investments

    def process_local_api_data(self, data: List[Dict], endpoint: str) -> List[Dict[str, Any]]:
        """Process data from local API into standard format."""
        processed = []
        for item in data:
            try:
                investment = {
                    "symbol": item.get("symbol", item.get("ticker", "UNKNOWN")),
                    "name": item.get("name", item.get("company_name", "")),
                    "type": self.determine_investment_type(item),
                    "current_price": float(item.get("price", item.get("current_price", 0))),
                    "previous_price": float(item.get("previous_close", item.get("prev_price", 0))),
                    "change_percent": float(item.get("change_percent", item.get("change_pct", 0))),
                    "market_cap": item.get("market_cap"),
                    "volume": item.get("volume"),
                    "source": "local_api_5003",
                    "external_id": item.get("id"),
                    "external_url": f"{self.local_api_base}/details/{item.get('id', item.get('symbol'))}",
                    "last_updated": datetime.now().isoformat()
                }
                
                # Save to database
                self.db.save_investment_data(
                    symbol=investment["symbol"],
                    name=investment["name"],
                    inv_type=investment["type"],
                    data=investment
                )
                
                processed.append(investment)
                
            except Exception as e:
                logger.error(f"Error processing local API item: {e}")
                continue
                
        return processed

    def determine_investment_type(self, item: Dict) -> str:
        """Determine investment type from API data."""
        if "crypto" in str(item).lower() or "btc" in str(item.get("symbol", "")).lower():
            return "crypto"
        elif "currency" in str(item).lower() or "forex" in str(item).lower():
            return "currency"
        else:
            return "stock"

    async def collect_stock_data(self, tracked_investments: List[Dict]) -> List[Dict[str, Any]]:
        """Collect stock data using Alpha Vantage API."""
        stocks = []
        
        if not self.alpha_vantage_key:
            logger.warning("Alpha Vantage API key not found")
            return stocks
            
        stock_symbols = [inv for inv in tracked_investments if inv['type'] == 'stock']
        
        try:
            async with aiohttp.ClientSession() as session:
                for investment in stock_symbols[:5]:  # Limit to avoid API rate limits
                    try:
                        symbol = investment['symbol']
                        url = f"https://www.alphavantage.co/query"
                        params = {
                            "function": "GLOBAL_QUOTE",
                            "symbol": symbol,
                            "apikey": self.alpha_vantage_key
                        }
                        
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                if "Global Quote" in data:
                                    quote = data["Global Quote"]
                                    stock = {
                                        "symbol": symbol,
                                        "name": investment.get('name', symbol),
                                        "type": "stock",
                                        "current_price": float(quote.get("05. price", 0)),
                                        "previous_price": float(quote.get("08. previous close", 0)),
                                        "change_percent": float(quote.get("10. change percent", "0").replace("%", "")),
                                        "volume": int(quote.get("06. volume", 0)),
                                        "source": "alpha_vantage",
                                        "last_updated": datetime.now().isoformat()
                                    }
                                    stocks.append(stock)
                                    
                    except Exception as e:
                        logger.error(f"Error fetching stock data for {symbol}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in stock data collection: {e}")
            
        return stocks

    async def collect_crypto_data(self, tracked_investments: List[Dict]) -> List[Dict[str, Any]]:
        """Collect cryptocurrency data."""
        crypto = []
        
        crypto_symbols = [inv for inv in tracked_investments if inv['type'] == 'crypto']
        
        try:
            # Use free CoinGecko API
            async with aiohttp.ClientSession() as session:
                symbols = [inv['symbol'].lower() for inv in crypto_symbols[:10]]  # Limit requests
                if symbols:
                    url = "https://api.coingecko.com/api/v3/simple/price"
                    params = {
                        "ids": ",".join(symbols),
                        "vs_currencies": "usd",
                        "include_24hr_change": "true",
                        "include_market_cap": "true",
                        "include_24hr_vol": "true"
                    }
                    
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            for symbol, info in data.items():
                                crypto_item = {
                                    "symbol": symbol.upper(),
                                    "name": symbol.title(),
                                    "type": "crypto",
                                    "current_price": info.get("usd", 0),
                                    "change_percent": info.get("usd_24h_change", 0),
                                    "market_cap": info.get("usd_market_cap"),
                                    "volume": info.get("usd_24h_vol"),
                                    "source": "coingecko",
                                    "last_updated": datetime.now().isoformat()
                                }
                                crypto.append(crypto_item)
                                
        except Exception as e:
            logger.error(f"Error in crypto data collection: {e}")
            
        return crypto

    def calculate_portfolio_summary(self, investments: List[Dict]) -> Dict[str, Any]:
        """Calculate portfolio summary statistics."""
        try:
            total_value = sum(inv.get("current_price", 0) for inv in investments)
            gainers = len([inv for inv in investments if inv.get("change_percent", 0) > 0])
            losers = len([inv for inv in investments if inv.get("change_percent", 0) < 0])
            
            by_type = {}
            for inv in investments:
                inv_type = inv.get("type", "unknown")
                if inv_type not in by_type:
                    by_type[inv_type] = {"count": 0, "total_value": 0}
                by_type[inv_type]["count"] += 1
                by_type[inv_type]["total_value"] += inv.get("current_price", 0)
            
            return {
                "total_investments": len(investments),
                "total_estimated_value": total_value,
                "gainers": gainers,
                "losers": losers,
                "by_type": by_type,
                "top_performers": sorted(investments, key=lambda x: x.get("change_percent", 0), reverse=True)[:5],
                "worst_performers": sorted(investments, key=lambda x: x.get("change_percent", 0))[:5]
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio summary: {e}")
            return {}

    async def add_investment_to_tracking(self, symbol: str, name: str, inv_type: str) -> bool:
        """Add a new investment to tracking."""
        try:
            # Check if already exists
            existing = self.db.get_tracked_investments()
            if any(inv['symbol'].lower() == symbol.lower() for inv in existing):
                return False
                
            # Add to database
            self.db.save_investment_data(symbol, name, inv_type, {
                "source": "manual",
                "current_price": 0,
                "is_tracked": True
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding investment to tracking: {e}")
            return False