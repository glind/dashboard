"""
SSL Helper utilities to fix certificate verification issues on macOS
"""

import ssl
import logging
import os
from typing import Optional

try:
    import certifi
    CERTIFI_AVAILABLE = True
except ImportError:
    CERTIFI_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True  
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


def create_ssl_context() -> ssl.SSLContext:
    """Create a properly configured SSL context using certifi certificates."""
    try:
        if CERTIFI_AVAILABLE:
            # Use certifi certificate bundle
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            logger.debug(f"Created SSL context using certifi: {certifi.where()}")
            return ssl_context
        else:
            # Fallback to default context
            logger.warning("Certifi not available, using default SSL context")
            return ssl.create_default_context()
    except Exception as e:
        logger.error(f"Error creating SSL context: {e}")
        # Last resort: create unverified context (not recommended for production)
        logger.warning("Using unverified SSL context as fallback")
        return ssl._create_unverified_context()


def configure_ssl_globally():
    """Configure SSL globally by setting environment variables."""
    try:
        if CERTIFI_AVAILABLE:
            cert_path = certifi.where()
            os.environ['SSL_CERT_FILE'] = cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = cert_path
            os.environ['CURL_CA_BUNDLE'] = cert_path
            logger.info(f"SSL configured globally using certifi: {cert_path}")
            return True
        else:
            logger.warning("Certifi not available for global SSL configuration")
            return False
    except Exception as e:
        logger.error(f"Error configuring SSL globally: {e}")
        return False


def get_aiohttp_connector() -> Optional:
    """Get aiohttp connector with proper SSL configuration."""
    if not AIOHTTP_AVAILABLE:
        return None
        
    try:
        ssl_context = create_ssl_context()
        return aiohttp.TCPConnector(ssl=ssl_context)
    except Exception as e:
        logger.error(f"Error creating aiohttp connector: {e}")
        return None


def get_httpx_client_kwargs() -> dict:
    """Get httpx client kwargs with proper SSL configuration."""
    try:
        if CERTIFI_AVAILABLE:
            return {"verify": certifi.where()}
        else:
            return {}
    except Exception as e:
        logger.error(f"Error configuring httpx SSL: {e}")
        return {}


def test_ssl_configuration():
    """Test SSL configuration by making a simple request."""
    import asyncio
    import sys
    
    async def test_aiohttp():
        if not AIOHTTP_AVAILABLE:
            return False, "aiohttp not available"
            
        try:
            connector = get_aiohttp_connector()
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get('https://httpbin.org/get', timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return True, "aiohttp SSL working"
                    else:
                        return False, f"aiohttp returned status {response.status}"
        except Exception as e:
            return False, f"aiohttp SSL error: {e}"
    
    async def test_httpx():
        if not HTTPX_AVAILABLE:
            return False, "httpx not available"
            
        try:
            client_kwargs = get_httpx_client_kwargs()
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get('https://httpbin.org/get', timeout=10)
                if response.status_code == 200:
                    return True, "httpx SSL working"
                else:
                    return False, f"httpx returned status {response.status_code}"
        except Exception as e:
            return False, f"httpx SSL error: {e}"
    
    async def run_tests():
        print("Testing SSL configuration...")
        
        # Test certifi availability
        if CERTIFI_AVAILABLE:
            print(f"✅ Certifi available: {certifi.where()}")
        else:
            print("❌ Certifi not available")
        
        # Test aiohttp
        aiohttp_ok, aiohttp_msg = await test_aiohttp()
        print(f"{'✅' if aiohttp_ok else '❌'} aiohttp: {aiohttp_msg}")
        
        # Test httpx  
        httpx_ok, httpx_msg = await test_httpx()
        print(f"{'✅' if httpx_ok else '❌'} httpx: {httpx_msg}")
        
        return aiohttp_ok or httpx_ok
    
    return asyncio.run(run_tests())


if __name__ == "__main__":
    # Configure SSL globally
    configure_ssl_globally()
    
    # Run tests
    test_ssl_configuration()