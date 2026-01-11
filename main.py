"""
Main orchestration engine for the Polymarket Copy Trading Bot.
"""
import signal
import sys
import time
from typing import Optional
from datetime import datetime, timedelta
from threading import Thread, Event

from config import get_settings
from logger import setup_logging, get_logger
from models import Database, SourceTrade, WalletBalance, TradeAction, TradeSide, TradeType
from polymarket_client import PolymarketClient, PolymarketExecutor
from blockchain_listener import PolygonListener
from trade_scaler import TradeScaler
from position_tracker import PositionTracker
from risk_controller import RiskController
from trade_executor import TradeExecutor

logger = get_logger(__name__)


class CopyTradingBot:
    """Main orchestration engine for copy trading."""
    
    def __init__(self):
        """Initialize the copy trading bot."""
        self.settings = get_settings()
        self.shutdown_event = Event()
        
        # Setup logging
        setup_logging(self.settings.log_level, self.settings.log_file)
        logger.info("="*60)
        logger.info("Initializing Polymarket Copy Trading Bot")
        logger.info("="*60)
        
        # Initialize database
        self.db = Database(self.settings.database_url)
        self.db.create_tables()
        logger.info("Database initialized")
        
        # Initialize Polymarket clients
        self.polymarket_client = PolymarketClient(
            api_url=self.settings.polymarket_api_url,
            chain_id=self.settings.polymarket_chain_id
        )
        
        self.polymarket_executor = PolymarketExecutor(
            private_key=self.settings.follower_wallet_private_key,
            chain_id=self.settings.polymarket_chain_id,
            host=self.settings.polymarket_api_url
        )
        logger.info("Polymarket clients initialized")
        
        # Initialize blockchain listener
        try:
            self.blockchain_listener = PolygonListener(
                rpc_url=self.settings.polygon_rpc_url
            )
            logger.info("Blockchain listener initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize blockchain listener: {e}")
            self.blockchain_listener = None
        
        # Initialize core components
        self.trade_scaler = TradeScaler(
            min_order_size_usdc=self.settings.min_order_size_usdc,
            max_position_size_percent=self.settings.max_position_size_percent,
            max_wallet_utilization_percent=self.settings.max_wallet_utilization_percent
        )
        
        self.position_tracker = PositionTracker(self.db)
        
        self.risk_controller = RiskController(
            db=self.db,
            max_wallet_utilization_percent=self.settings.max_wallet_utilization_percent,
            daily_loss_limit_percent=self.settings.daily_loss_limit_percent,
            circuit_breaker_error_threshold=self.settings.circuit_breaker_error_threshold
        )
        
        # Restore risk control state from database
        self.risk_controller.restore_state_from_db()
        
        self.trade_executor = TradeExecutor(
            db=self.db,
            executor=self.polymarket_executor,
            scaler=self.trade_scaler,
            position_tracker=self.position_tracker,
            risk_controller=self.risk_controller,
            slippage_tolerance=self.settings.slippage_tolerance_percent / 100.0,
            max_retries=self.settings.retry_attempts
        )
        
        logger.info("Core components initialized")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.last_balance_check = datetime.utcnow()
        self.last_processed_timestamp = int(time.time())
        
        logger.info("Bot initialization complete")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()
    
    def start(self):
        """Start the copy trading bot."""
        logger.info("="*60)
        logger.info("Starting Polymarket Copy Trading Bot")
        logger.info(f"Source Wallet: {self.settings.source_wallet_address}")
        logger.info(f"Follower Wallet: {self.settings.follower_wallet_address}")
        logger.info("="*60)
        
        # Initial balance check
        self._update_wallet_balances()
        
        # Start balance monitoring thread
        balance_thread = Thread(target=self._balance_monitor_loop, daemon=True)
        balance_thread.start()
        
        # Main event loop
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        finally:
            self._shutdown()
    
    def _main_loop(self):
        """Main event processing loop."""
        logger.info("Entering main event loop")
        
        while not self.shutdown_event.is_set():
            try:
                # Check emergency shutdown flag
                if self.settings.emergency_shutdown:
                    logger.error("Emergency shutdown flag detected!")
                    break
                
                # Check risk controls
                if not self.risk_controller.is_trading_allowed():
                    logger.warning("Trading is paused due to risk controls")
                    time.sleep(10)
                    continue
                
                # Fetch new trades from source wallet
                new_trades = self._fetch_source_trades()
                
                if new_trades:
                    logger.info(f"Found {len(new_trades)} new trades to process")
                    
                    for trade_data in new_trades:
                        if self.shutdown_event.is_set():
                            break
                        
                        # Store source trade
                        source_trade = self._store_source_trade(trade_data)
                        
                        if source_trade:
                            # Execute the trade
                            self.trade_executor.execute_source_trade(source_trade)
                
                # Sleep before next poll
                time.sleep(self.settings.polling_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                self.risk_controller.record_error()
                time.sleep(self.settings.polling_interval_seconds)
    
    def _fetch_source_trades(self):
        """Fetch new trades from source wallet."""
        try:
            trades = self.polymarket_client.get_trades(
                wallet_address=self.settings.source_wallet_address,
                since_timestamp=self.last_processed_timestamp
            )
            
            if trades:
                # Update last processed timestamp
                self.last_processed_timestamp = int(time.time())
            
            return trades
            
        except Exception as e:
            logger.error(f"Error fetching source trades: {e}")
            self.risk_controller.record_error()
            return []
    
    def _store_source_trade(self, trade_data: dict) -> Optional[SourceTrade]:
        """Store a source trade in the database."""
        session = self.db.get_session()
        try:
            # Check if trade already exists
            trade_hash = trade_data.get('id', trade_data.get('transactionHash', ''))
            
            existing = session.query(SourceTrade).filter(
                SourceTrade.trade_hash == trade_hash
            ).first()
            
            if existing:
                logger.debug(f"Trade {trade_hash} already exists")
                return None
            
            # Parse trade data
            # Note: Actual parsing logic would depend on Polymarket API response format
            source_trade = SourceTrade(
                trade_hash=trade_hash,
                market_id=trade_data.get('market', trade_data.get('asset_id', '')),
                outcome_side=TradeSide.YES if trade_data.get('side') == 'YES' else TradeSide.NO,
                trade_type=TradeType.MARKET if trade_data.get('type') == 'MARKET' else TradeType.LIMIT,
                action=self._determine_trade_action(trade_data),
                size_shares=float(trade_data.get('size', 0)),
                size_usdc=float(trade_data.get('price', 0)) * float(trade_data.get('size', 0)),
                price=float(trade_data.get('price', 0)),
                timestamp=datetime.fromtimestamp(trade_data.get('timestamp', time.time())),
                transaction_hash=trade_data.get('transactionHash'),
                processed=False
            )
            
            session.add(source_trade)
            session.commit()
            
            logger.info(f"Stored new source trade: {source_trade.id}")
            return source_trade
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing source trade: {e}")
            return None
        finally:
            session.close()
    
    def _determine_trade_action(self, trade_data: dict) -> TradeAction:
        """Determine if trade is opening or closing a position."""
        # This would need actual logic based on position state
        # For now, assuming we can infer from trade data
        
        # If there's a field indicating this, use it
        if 'action' in trade_data:
            action_str = trade_data['action'].upper()
            if 'CLOSE' in action_str:
                return TradeAction.CLOSE
            elif 'PARTIAL' in action_str:
                return TradeAction.PARTIAL_CLOSE
        
        # Default to OPEN
        return TradeAction.OPEN
    
    def _balance_monitor_loop(self):
        """Background thread for monitoring wallet balances."""
        logger.info("Started balance monitoring thread")
        
        while not self.shutdown_event.is_set():
            try:
                time.sleep(self.settings.balance_check_interval_seconds)
                self._update_wallet_balances()
                
            except Exception as e:
                logger.error(f"Error in balance monitor: {e}")
    
    def _update_wallet_balances(self):
        """Update wallet balances in database."""
        session = self.db.get_session()
        try:
            # Get follower wallet balance
            follower_usdc = self.polymarket_executor.get_balance("USDC")
            follower_positions_value = self.position_tracker.get_total_position_value()
            
            follower_balance = WalletBalance(
                wallet_address=self.settings.follower_wallet_address,
                usdc_balance=follower_usdc,
                positions_value=follower_positions_value,
                total_value=follower_usdc + follower_positions_value
            )
            
            session.add(follower_balance)
            session.commit()
            
            logger.info(
                f"Follower wallet: {follower_usdc:.2f} USDC, "
                f"Positions: {follower_positions_value:.2f} USDC, "
                f"Total: {follower_usdc + follower_positions_value:.2f} USDC"
            )
            
            # For source wallet, we'd need to query Polymarket or on-chain
            # For now, just log that we updated balances
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating wallet balances: {e}")
        finally:
            session.close()
    
    def _shutdown(self):
        """Graceful shutdown procedure."""
        logger.info("="*60)
        logger.info("Initiating graceful shutdown")
        logger.info("="*60)
        
        # Log final status
        status = self.risk_controller.get_status()
        logger.info(f"Risk control status: {status}")
        
        positions = self.position_tracker.get_all_open_positions()
        logger.info(f"Open positions: {len(positions)}")
        
        for pos in positions:
            logger.info(
                f"  - {pos.market_id} {pos.outcome_side.value}: "
                f"{pos.total_shares:.2f} shares @ ${pos.average_price:.3f}"
            )
        
        logger.info("="*60)
        logger.info("Shutdown complete")
        logger.info("="*60)


def main():
    """Main entry point."""
    try:
        bot = CopyTradingBot()
        bot.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
