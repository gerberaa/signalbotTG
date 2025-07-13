import aiohttp
import asyncio
from typing import Optional, Dict
from config import COINGECKO_API_URL, PRICE_CHECK_DELAY

class CryptoAPI:
    def __init__(self):
        self.base_url = COINGECKO_API_URL
        self.session = None
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_coin_price(self, coin_ticker: str) -> Optional[float]:
        """Get current price for a coin by ticker, with Binance fallback and 5s timeout for CoinGecko"""
        try:
            session = await self.get_session()
            coin_id = await self._get_coin_id(coin_ticker)
            if not coin_id:
                price = await self._get_binance_price(coin_ticker)
                if price is not None:
                    print(f"[BINANCE] Price for {coin_ticker}: {price}")
                return price
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd'
            }
            try:
                async def coingecko_request():
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if coin_id in data and 'usd' in data[coin_id]:
                                return data[coin_id]['usd']
                        if response.status == 429:
                            await asyncio.sleep(PRICE_CHECK_DELAY)
                            return await self.get_coin_price(coin_ticker)
                        return None
                price = await asyncio.wait_for(coingecko_request(), timeout=5)
                if price is not None:
                    return price
            except asyncio.TimeoutError:
                print(f"[GECKO] Timeout for {coin_ticker}, trying Binance...")
            except Exception as e:
                print(f"[GECKO] Error for {coin_ticker}: {e}")
            price = await self._get_binance_price(coin_ticker)
            if price is not None:
                print(f"[BINANCE] Price for {coin_ticker}: {price}")
            return price
        except Exception as e:
            print(f"Error getting price for {coin_ticker}: {e}")
            price = await self._get_binance_price(coin_ticker)
            if price is not None:
                print(f"[BINANCE] Price for {coin_ticker}: {price}")
            return price
    
    async def _get_coin_id(self, coin_ticker: str) -> Optional[str]:
        """Get CoinGecko coin ID from ticker symbol"""
        try:
            session = await self.get_session()
            
            # Common coin mappings
            coin_mappings = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'USDT': 'tether',
                'BNB': 'binancecoin',
                'SOL': 'solana',
                'ADA': 'cardano',
                'XRP': 'ripple',
                'DOT': 'polkadot',
                'DOGE': 'dogecoin',
                'AVAX': 'avalanche-2',
                'MATIC': 'matic-network',
                'LINK': 'chainlink',
                'UNI': 'uniswap',
                'ATOM': 'cosmos',
                'LTC': 'litecoin',
                'BCH': 'bitcoin-cash',
                'XLM': 'stellar',
                'ALGO': 'algorand',
                'VET': 'vechain',
                'ICP': 'internet-computer'
            }
            
            # Check direct mapping first
            if coin_ticker.upper() in coin_mappings:
                return coin_mappings[coin_ticker.upper()]
            
            # Search API for other coins
            url = f"{self.base_url}/search"
            params = {'query': coin_ticker}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'coins' in data and len(data['coins']) > 0:
                        # Return the first (most relevant) result
                        return data['coins'][0]['id']
                
                return None
                
        except Exception as e:
            print(f"Error getting coin ID for {coin_ticker}: {e}")
            return None
    
    async def _get_binance_price(self, coin_ticker: str) -> Optional[float]:
        """Get price from Binance public API (USDT pairs only)"""
        try:
            session = await self.get_session()
            symbol = coin_ticker.upper() + 'USDT'
            url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}'
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'price' in data:
                        return float(data['price'])
            return None
        except Exception as e:
            print(f"[BINANCE] Error for {coin_ticker}: {e}")
            return None

    async def get_multiple_prices(self, coin_tickers: list) -> Dict[str, float]:
        """Get prices for multiple coins efficiently, with Binance fallback and 5s timeout for CoinGecko"""
        prices = {}
        for ticker in coin_tickers:
            price = await self.get_coin_price(ticker)
            if price is not None:
                prices[ticker.upper()] = price
            await asyncio.sleep(1)
        return prices 