"""
Trade execution engine with retry logic and error handling.
"""
from typing import Optional, Dict, Any
from datetime import datetime
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from models import (
    Database, FollowerTrade, SourceTrade, TradeStatus, 
    TradeSide, TradeType, TradeAction, WalletBalance
)
from polymarket_client import PolymarketExecutor
from trade_scaler import TradeScaler
from position_tracker import PositionTracker
from risk_controller import RiskController
from logger import get_logger

logger = get_logger(__name__)


class TradeExecutor:
    """Execute trades on Polymarket with risk controls."""
    
    def __init__(
        self,
        db: Database,
        executor: PolymarketExecutor,
        scaler: TradeScaler,
        position_tracker: PositionTracker,
        risk_controller: RiskController,
        slippage_tolerance: float = 0.02,
        max_retries: int = 3
    ):
        """
        Initialize trade executor.
        
        Args:
            db: Database instance
            executor: Polymarket executor
            scaler: Trade scaler
            position_tracker: Position tracker
            risk_controller: Risk controller
            slippage_tolerance: Maximum slippage tolerance
            max_retries: Maximum number of retry attempts
        """
        self.db = db
        self.executor = executor
        self.scaler = scaler
        self.position_tracker = position_tracker
        self.risk_controller = risk_controller
        self.slippage_tolerance = slippage_tolerance
        self.max_retries = max_retries
        
        logger.info("Initialized TradeExecutor")
    
    def execute_source_trade(self, source_trade: SourceTrade) -> bool:
        """
        Execute a trade based on source wallet activity.
        
        Args:
            source_trade: Source trade to mirror
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing source trade {source_trade.id}: {source_trade.action.value}")
            
            # Check if already processed
            if source_trade.processed:
                logger.warning(f"Source trade {source_trade.id} already processed")
                return False
            
            # Check risk controls
            if not self.risk_controller.is_trading_allowed():
                logger.error("Trading is not allowed due to risk controls")
                return False
            
            # Get wallet balances for scaling
            follower_balance = self._get_follower_balance()
            source_balance = self._get_source_balance()
            
            if follower_balance <= 0 or source_balance <= 0:
                logger.error("Invalid wallet balances")
                return False
            
            # Calculate scale factor
            scale_factor = self.scaler.calculate_scale_factor(source_balance, follower_balance)
            
            # Handle based on action type
            if source_trade.action == TradeAction.OPEN:
                return self._execute_open_trade(source_trade, scale_factor, follower_balance)
            
            elif source_trade.action in [TradeAction.CLOSE, TradeAction.PARTIAL_CLOSE]:
                return self._execute_close_trade(source_trade, scale_factor)
            
            else:
                logger.error(f"Unknown trade action: {source_trade.action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing source trade: {e}")
            self.risk_controller.record_error()
            return False
    
    def _execute_open_trade(
        self,
        source_trade: SourceTrade,
        scale_factor: float,
        follower_balance: float
    ) -> bool:
        """Execute an opening trade."""
        try:
            # Get current position value for this market
            existing_position = self.position_tracker.get_position(
                source_trade.market_id,
                source_trade.outcome_side
            )
            current_position_usdc = existing_position.total_usdc_invested if existing_position else 0.0
            
            # Scale the trade
            scaled_trade = self.scaler.scale_trade(
                source_size_usdc=source_trade.size_usdc,
                source_size_shares=source_trade.size_shares,
                scale_factor=scale_factor,
                follower_wallet_balance=follower_balance,
                current_position_size_usdc=current_position_usdc
            )
            
            if not scaled_trade:
                logger.warning("Trade scaling resulted in no trade (below minimum or exceeds limits)")
                self._mark_trade_skipped(source_trade)
                return False
            
            # Check wallet utilization
            total_position_value = self.position_tracker.get_total_position_value()
            if not self.risk_controller.check_wallet_utilization(
                follower_balance,
                total_position_value,
                scaled_trade['follower_size_usdc']
            ):
                logger.warning("Trade rejected by wallet utilization check")
                self._mark_trade_skipped(source_trade)
                return False
            
            # Check daily loss limit
            if not self.risk_controller.check_daily_loss_limit(self.executor.client.address):
                logger.error("Trade rejected by daily loss limit")
                return False
            
            # Create follower trade record
            follower_trade = self._create_follower_trade(
                source_trade,
                scaled_trade['follower_size_shares'],
                scaled_trade['follower_size_usdc'],
                scaled_trade['scale_factor']
            )
            
            # Execute the trade with retry
            success = self._execute_with_retry(follower_trade, source_trade)
            
            if success:
                # Update position
                self.position_tracker.open_position(
                    market_id=source_trade.market_id,
                    outcome_side=source_trade.outcome_side,
                    shares=scaled_trade['follower_size_shares'],
                    usdc_invested=scaled_trade['follower_size_usdc'],
                    price=source_trade.price
                )
                
                # Mark source trade as processed
                self._mark_trade_processed(source_trade)
                
                # Reset error count on success
                self.risk_controller.reset_error_count()
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing open trade: {e}")
            self.risk_controller.record_error()
            return False
    
    def _execute_close_trade(
        self,
        source_trade: SourceTrade,
        scale_factor: float
    ) -> bool:
        """Execute a closing/reducing trade."""
        try:
            # Get current follower position
            position = self.position_tracker.get_position(
                source_trade.market_id,
                source_trade.outcome_side
            )
            
            if not position:
                logger.warning(
                    f"No follower position found for {source_trade.market_id} "
                    f"{source_trade.outcome_side.value}"
                )
                self._mark_trade_skipped(source_trade)
                return False
            
            # Calculate follower close size proportionally
            # We need to estimate the source's total position to calculate proportion
            # For simplicity, we'll use the scale factor
            follower_close_shares = source_trade.size_shares * scale_factor
            
            # Cap at current position size
            if follower_close_shares > position.total_shares:
                follower_close_shares = position.total_shares
            
            follower_close_usdc = follower_close_shares * source_trade.price
            
            # Create follower trade record
            follower_trade = self._create_follower_trade(
                source_trade,
                follower_close_shares,
                follower_close_usdc,
                scale_factor
            )
            
            # Execute the trade
            success = self._execute_with_retry(follower_trade, source_trade)
            
            if success:
                # Update position
                if source_trade.action == TradeAction.CLOSE:
                    self.position_tracker.close_position(
                        source_trade.market_id,
                        source_trade.outcome_side
                    )
                else:
                    self.position_tracker.reduce_position(
                        source_trade.market_id,
                        source_trade.outcome_side,
                        follower_close_shares
                    )
                
                # Mark source trade as processed
                self._mark_trade_processed(source_trade)
                
                # Reset error count
                self.risk_controller.reset_error_count()
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing close trade: {e}")
            self.risk_controller.record_error()
            return False
    
    def _execute_with_retry(
        self,
        follower_trade: FollowerTrade,
        source_trade: SourceTrade
    ) -> bool:
        """Execute trade with retry logic."""
        session = self.db.get_session()
        
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Executing trade attempt {attempt + 1}/{self.max_retries}: "
                    f"{follower_trade.action.value} {follower_trade.follower_size_usdc:.2f} USDC"
                )
                
                # Update status
                follower_trade.status = TradeStatus.EXECUTING
                follower_trade.submitted_at = datetime.utcnow()
                session.commit()
                
                # Determine buy/sell based on action and side
                # Opening YES or closing NO = BUY
                # Opening NO or closing YES = SELL
                if source_trade.action == TradeAction.OPEN:
                    side = 'BUY' if source_trade.outcome_side == TradeSide.YES else 'SELL'
                else:  # CLOSE or PARTIAL_CLOSE
                    side = 'SELL' if source_trade.outcome_side == TradeSide.YES else 'BUY'
                
                # Execute based on trade type
                # Note: We need the token_id for the specific outcome
                # For now, using market_id as placeholder - in production, 
                # would need to resolve to actual token_id
                token_id = f"{source_trade.market_id}"  # Placeholder
                
                if source_trade.trade_type == TradeType.MARKET:
                    result = self.executor.place_market_order(
                        token_id=token_id,
                        side=side,
                        amount=follower_trade.follower_size_usdc,
                        slippage_tolerance=self.slippage_tolerance
                    )
                else:
                    result = self.executor.place_limit_order(
                        token_id=token_id,
                        side=side,
                        amount=follower_trade.follower_size_shares,
                        price=source_trade.price
                    )
                
                if result:
                    # Trade successful
                    follower_trade.status = TradeStatus.COMPLETED
                    follower_trade.executed_at = datetime.utcnow()
                    follower_trade.transaction_hash = result.get('transactionHash', '')
                    session.commit()
                    
                    logger.info(f"Trade executed successfully: {result}")
                    return True
                else:
                    # Trade failed
                    follower_trade.retry_count += 1
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"Trade failed, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        follower_trade.status = TradeStatus.FAILED
                        follower_trade.error_message = "Max retries exceeded"
                        session.commit()
                        logger.error("Trade failed after max retries")
                        return False
                        
            except Exception as e:
                logger.error(f"Error in trade execution attempt {attempt + 1}: {e}")
                follower_trade.retry_count += 1
                follower_trade.error_message = str(e)
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    follower_trade.status = TradeStatus.FAILED
                    session.commit()
                    return False
        
        session.close()
        return False
    
    def _create_follower_trade(
        self,
        source_trade: SourceTrade,
        follower_shares: float,
        follower_usdc: float,
        scale_factor: float
    ) -> FollowerTrade:
        """Create a follower trade record."""
        session = self.db.get_session()
        try:
            follower_trade = FollowerTrade(
                source_trade_id=source_trade.id,
                market_id=source_trade.market_id,
                outcome_side=source_trade.outcome_side,
                trade_type=source_trade.trade_type,
                action=source_trade.action,
                source_size_shares=source_trade.size_shares,
                source_size_usdc=source_trade.size_usdc,
                follower_size_shares=follower_shares,
                follower_size_usdc=follower_usdc,
                price=source_trade.price,
                scale_factor=scale_factor,
                status=TradeStatus.PENDING
            )
            
            session.add(follower_trade)
            session.commit()
            
            logger.info(f"Created follower trade record: {follower_trade.id}")
            return follower_trade
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating follower trade: {e}")
            raise
        finally:
            session.close()
    
    def _mark_trade_processed(self, source_trade: SourceTrade):
        """Mark source trade as processed."""
        session = self.db.get_session()
        try:
            source_trade.processed = True
            source_trade.processed_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()
    
    def _mark_trade_skipped(self, source_trade: SourceTrade):
        """Mark source trade as processed but skipped."""
        session = self.db.get_session()
        try:
            source_trade.processed = True
            source_trade.processed_at = datetime.utcnow()
            session.commit()
            logger.info(f"Source trade {source_trade.id} marked as skipped")
        finally:
            session.close()
    
    def _get_follower_balance(self) -> float:
        """Get follower wallet USDC balance."""
        try:
            return self.executor.get_balance("USDC")
        except Exception as e:
            logger.error(f"Error getting follower balance: {e}")
            return 0.0
    
    def _get_source_balance(self) -> float:
        """Get source wallet balance from latest recorded balance."""
        session = self.db.get_session()
        try:
            from config import get_settings
            settings = get_settings()
            
            latest = session.query(WalletBalance).filter(
                WalletBalance.wallet_address == settings.source_wallet_address
            ).order_by(WalletBalance.timestamp.desc()).first()
            
            if latest:
                return latest.usdc_balance
            
            # Default to a reasonable value if no data
            logger.warning("No source balance data, using default")
            return 10000.0
            
        finally:
            session.close()
