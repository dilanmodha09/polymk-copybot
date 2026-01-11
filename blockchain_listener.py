"""
On-chain event listener for Polymarket trades on Polygon.
"""
from web3 import Web3
from web3.middleware import geth_poa_middleware
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import time
from logger import get_logger

logger = get_logger(__name__)


# Polymarket CTF Exchange contract address on Polygon
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# Simplified ABI for order events
CTF_EXCHANGE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": False, "name": "orderHash", "type": "bytes32"},
            {"indexed": False, "name": "tokenId", "type": "uint256"},
            {"indexed": False, "name": "makerAmount", "type": "uint256"},
            {"indexed": False, "name": "takerAmount", "type": "uint256"},
            {"indexed": False, "name": "side", "type": "uint8"}
        ],
        "name": "OrderFilled",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": False, "name": "orderHash", "type": "bytes32"}
        ],
        "name": "OrderCancelled",
        "type": "event"
    }
]


class PolygonListener:
    """Listen to on-chain events on Polygon for Polymarket trades."""
    
    def __init__(self, rpc_url: str, contract_address: str = CTF_EXCHANGE_ADDRESS):
        """
        Initialize Polygon event listener.
        
        Args:
            rpc_url: Polygon RPC endpoint URL
            contract_address: Polymarket CTF Exchange contract address
        """
        self.rpc_url = rpc_url
        self.contract_address = Web3.to_checksum_address(contract_address)
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        # Inject POA middleware for Polygon
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Polygon RPC: {rpc_url}")
        
        # Initialize contract
        self.contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=CTF_EXCHANGE_ABI
        )
        
        logger.info(f"Initialized Polygon listener connected to {rpc_url}")
        logger.info(f"Monitoring contract: {self.contract_address}")
    
    def get_latest_block(self) -> int:
        """Get the latest block number."""
        try:
            return self.w3.eth.block_number
        except Exception as e:
            logger.error(f"Error getting latest block: {e}")
            return 0
    
    def get_order_filled_events(
        self,
        from_block: int,
        to_block: Optional[int] = None,
        maker_address: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get OrderFilled events from the blockchain.
        
        Args:
            from_block: Starting block number
            to_block: Ending block number (None for latest)
            maker_address: Filter by maker address (None for all)
            
        Returns:
            List of event dictionaries
        """
        try:
            if to_block is None:
                to_block = 'latest'
            
            # Build event filter
            event_filter = self.contract.events.OrderFilled.create_filter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={'maker': maker_address} if maker_address else {}
            )
            
            events = event_filter.get_all_entries()
            
            parsed_events = []
            for event in events:
                parsed_events.append({
                    'transaction_hash': event['transactionHash'].hex(),
                    'block_number': event['blockNumber'],
                    'maker': event['args']['maker'],
                    'order_hash': event['args']['orderHash'].hex(),
                    'token_id': event['args']['tokenId'],
                    'maker_amount': event['args']['makerAmount'],
                    'taker_amount': event['args']['takerAmount'],
                    'side': event['args']['side'],
                    'timestamp': self._get_block_timestamp(event['blockNumber'])
                })
            
            logger.debug(f"Retrieved {len(parsed_events)} OrderFilled events from blocks {from_block} to {to_block}")
            return parsed_events
            
        except Exception as e:
            logger.error(f"Error fetching OrderFilled events: {e}")
            return []
    
    def get_order_cancelled_events(
        self,
        from_block: int,
        to_block: Optional[int] = None,
        maker_address: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get OrderCancelled events from the blockchain.
        
        Args:
            from_block: Starting block number
            to_block: Ending block number (None for latest)
            maker_address: Filter by maker address (None for all)
            
        Returns:
            List of event dictionaries
        """
        try:
            if to_block is None:
                to_block = 'latest'
            
            event_filter = self.contract.events.OrderCancelled.create_filter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={'maker': maker_address} if maker_address else {}
            )
            
            events = event_filter.get_all_entries()
            
            parsed_events = []
            for event in events:
                parsed_events.append({
                    'transaction_hash': event['transactionHash'].hex(),
                    'block_number': event['blockNumber'],
                    'maker': event['args']['maker'],
                    'order_hash': event['args']['orderHash'].hex(),
                    'timestamp': self._get_block_timestamp(event['blockNumber'])
                })
            
            logger.debug(f"Retrieved {len(parsed_events)} OrderCancelled events")
            return parsed_events
            
        except Exception as e:
            logger.error(f"Error fetching OrderCancelled events: {e}")
            return []
    
    def _get_block_timestamp(self, block_number: int) -> datetime:
        """Get timestamp for a block."""
        try:
            block = self.w3.eth.get_block(block_number)
            return datetime.fromtimestamp(block['timestamp'])
        except Exception as e:
            logger.error(f"Error getting block timestamp: {e}")
            return datetime.utcnow()
    
    def monitor_wallet(
        self,
        wallet_address: str,
        from_block: int,
        callback: Callable[[Dict[str, Any]], None],
        poll_interval: float = 5.0
    ):
        """
        Continuously monitor a wallet for new events.
        
        Args:
            wallet_address: Wallet address to monitor
            from_block: Starting block number
            callback: Function to call for each new event
            poll_interval: Polling interval in seconds
        """
        wallet_address = Web3.to_checksum_address(wallet_address)
        current_block = from_block
        
        logger.info(f"Starting to monitor wallet {wallet_address} from block {from_block}")
        
        while True:
            try:
                latest_block = self.get_latest_block()
                
                if latest_block > current_block:
                    # Get new events
                    events = self.get_order_filled_events(
                        from_block=current_block + 1,
                        to_block=latest_block,
                        maker_address=wallet_address
                    )
                    
                    # Process each event
                    for event in events:
                        try:
                            callback(event)
                        except Exception as e:
                            logger.error(f"Error in callback processing event: {e}")
                    
                    current_block = latest_block
                
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(poll_interval)
