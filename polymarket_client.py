"""
Polymarket API client for trade monitoring and execution.
"""
import requests
import time
from typing import List, Dict, Optional, Any
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from logger import get_logger

logger = get_logger(__name__)


class PolymarketClient:
    """Client for interacting with Polymarket CLOB API."""
    
    def __init__(self, api_url: str, chain_id: int = 137):
        """
        Initialize Polymarket client.
        
        Args:
            api_url: Polymarket CLOB API URL
            chain_id: Polygon chain ID (default: 137 for mainnet)
        """
        self.api_url = api_url.rstrip('/')
        self.chain_id = chain_id
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        logger.info(f"Initialized Polymarket client with API URL: {api_url}")
    
    def get_trades(self, wallet_address: str, since_timestamp: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get trades for a specific wallet address.
        
        Args:
            wallet_address: Wallet address to query
            since_timestamp: Unix timestamp to filter trades from
            
        Returns:
            List of trade dictionaries
        """
        try:
            params = {'maker': wallet_address}
            if since_timestamp:
                params['after'] = since_timestamp
            
            url = f"{self.api_url}/trades"
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            trades = response.json()
            logger.debug(f"Retrieved {len(trades)} trades for wallet {wallet_address[:8]}...")
            return trades
            
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []
    
    def get_market(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Get market details by ID.
        
        Args:
            market_id: Market condition ID
            
        Returns:
            Market details dictionary or None
        """
        try:
            url = f"{self.api_url}/markets/{market_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            market = response.json()
            logger.debug(f"Retrieved market {market_id}")
            return market
            
        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return None
    
    def get_order_book(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order book for a token.
        
        Args:
            token_id: Token ID
            
        Returns:
            Order book data or None
        """
        try:
            url = f"{self.api_url}/book"
            params = {'token_id': token_id}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching order book for token {token_id}: {e}")
            return None
    
    def get_tick_size(self, token_id: str) -> float:
        """
        Get tick size for a token (minimum price increment).
        
        Args:
            token_id: Token ID
            
        Returns:
            Tick size as float (default: 0.01)
        """
        # Polymarket typically uses 0.01 as tick size
        return 0.01
    
    def get_min_order_size(self, token_id: str) -> float:
        """
        Get minimum order size for a token.
        
        Args:
            token_id: Token ID
            
        Returns:
            Minimum order size in USDC
        """
        # Polymarket typically has a $1 minimum
        return 1.0


class PolymarketExecutor:
    """Client for executing trades on Polymarket."""
    
    def __init__(self, private_key: str, chain_id: int = 137, host: str = "https://clob.polymarket.com"):
        """
        Initialize Polymarket trade executor.
        
        Args:
            private_key: Private key for signing transactions
            chain_id: Polygon chain ID
            host: Polymarket CLOB API host
        """
        self.chain_id = chain_id
        self.host = host
        try:
            # Initialize py-clob-client
            self.client = ClobClient(
                host=host,
                key=private_key,
                chain_id=chain_id
            )
            logger.info("Initialized Polymarket executor")
        except Exception as e:
            logger.error(f"Failed to initialize Polymarket executor: {e}")
            raise
    
    def place_market_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        slippage_tolerance: float = 0.02
    ) -> Optional[Dict[str, Any]]:
        """
        Place a market order.
        
        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            amount: Amount in USDC
            slippage_tolerance: Maximum slippage (default: 2%)
            
        Returns:
            Order result dictionary or None
        """
        try:
            logger.info(f"Placing market order: {side} {amount} USDC of token {token_id}")
            
            # Use py-clob-client to place market order
            order_args = OrderArgs(
                token_id=token_id,
                amount=amount,
                side=BUY if side.upper() == 'BUY' else SELL
            )
            
            result = self.client.create_market_order(order_args)
            logger.info(f"Market order placed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None
    
    def place_limit_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Place a limit order.
        
        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            amount: Amount in shares
            price: Limit price
            
        Returns:
            Order result dictionary or None
        """
        try:
            logger.info(f"Placing limit order: {side} {amount} shares of token {token_id} at ${price}")
            
            order_args = OrderArgs(
                token_id=token_id,
                amount=amount,
                price=price,
                side=BUY if side.upper() == 'BUY' else SELL
            )
            
            result = self.client.create_order(order_args)
            logger.info(f"Limit order placed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.client.cancel_order(order_id)
            logger.info(f"Order {order_id} cancelled successfully")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_balance(self, asset: str = "USDC") -> float:
        """
        Get balance for an asset.
        
        Args:
            asset: Asset symbol (default: USDC)
            
        Returns:
            Balance as float
        """
        try:
            # Get balance from the client
            balances = self.client.get_balance()
            return float(balances.get(asset, 0))
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current open positions.
        
        Returns:
            List of position dictionaries
        """
        try:
            positions = self.client.get_positions()
            return positions
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
