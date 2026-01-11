"""
Risk control mechanisms for the trading system.
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from models import Database, WalletBalance, SystemState
from logger import get_logger

logger = get_logger(__name__)


class RiskController:
    """Manage risk controls and circuit breakers."""
    
    def __init__(
        self,
        db: Database,
        max_wallet_utilization_percent: float = 80.0,
        daily_loss_limit_percent: float = 10.0,
        circuit_breaker_error_threshold: int = 5
    ):
        """
        Initialize risk controller.
        
        Args:
            db: Database instance
            max_wallet_utilization_percent: Maximum wallet utilization %
            daily_loss_limit_percent: Daily loss limit before kill-switch
            circuit_breaker_error_threshold: Consecutive errors before circuit breaker
        """
        self.db = db
        self.max_wallet_utilization = max_wallet_utilization_percent / 100.0
        self.daily_loss_limit = daily_loss_limit_percent / 100.0
        self.error_threshold = circuit_breaker_error_threshold
        
        self.consecutive_errors = 0
        self.circuit_breaker_active = False
        self.kill_switch_active = False
        
        logger.info(
            f"Initialized RiskController: max_util={max_wallet_utilization_percent}%, "
            f"daily_loss={daily_loss_limit_percent}%, error_threshold={circuit_breaker_error_threshold}"
        )
    
    def check_wallet_utilization(
        self,
        current_balance: float,
        total_position_value: float,
        proposed_trade_size: float
    ) -> bool:
        """
        Check if proposed trade would exceed wallet utilization limit.
        
        Args:
            current_balance: Current wallet balance in USDC
            total_position_value: Total value of open positions
            proposed_trade_size: Size of proposed trade in USDC
            
        Returns:
            True if trade is allowed, False otherwise
        """
        total_value = current_balance + total_position_value
        
        if total_value <= 0:
            logger.error("Total wallet value is zero or negative")
            return False
        
        current_utilization = total_position_value / total_value
        proposed_utilization = (total_position_value + proposed_trade_size) / total_value
        
        if proposed_utilization > self.max_wallet_utilization:
            logger.warning(
                f"Trade rejected: would exceed max utilization "
                f"({proposed_utilization * 100:.1f}% > {self.max_wallet_utilization * 100:.1f}%)"
            )
            return False
        
        logger.debug(f"Wallet utilization check passed: {proposed_utilization * 100:.1f}%")
        return True
    
    def check_daily_loss_limit(self, wallet_address: str) -> bool:
        """
        Check if daily loss limit has been exceeded (kill-switch).
        
        Args:
            wallet_address: Wallet address to check
            
        Returns:
            True if trading is allowed, False if kill-switch activated
        """
        if self.kill_switch_active:
            logger.warning("Kill-switch is active, trading disabled")
            return False
        
        session = self.db.get_session()
        try:
            # Get balance from 24 hours ago
            day_ago = datetime.utcnow() - timedelta(days=1)
            
            past_balance = session.query(WalletBalance).filter(
                WalletBalance.wallet_address == wallet_address,
                WalletBalance.timestamp >= day_ago
            ).order_by(WalletBalance.timestamp.asc()).first()
            
            if not past_balance:
                logger.debug("No historical balance data, allowing trade")
                return True
            
            # Get current balance
            current_balance = session.query(WalletBalance).filter(
                WalletBalance.wallet_address == wallet_address
            ).order_by(WalletBalance.timestamp.desc()).first()
            
            if not current_balance:
                logger.warning("No current balance data found")
                return True
            
            # Calculate loss
            past_value = past_balance.total_value
            current_value = current_balance.total_value
            
            if past_value <= 0:
                logger.debug("Past value is zero, allowing trade")
                return True
            
            loss_percent = (past_value - current_value) / past_value
            
            if loss_percent > self.daily_loss_limit:
                self.kill_switch_active = True
                self._set_system_state("kill_switch_active", "true")
                logger.error(
                    f"KILL-SWITCH ACTIVATED: Daily loss {loss_percent * 100:.2f}% "
                    f"exceeds limit {self.daily_loss_limit * 100:.2f}%"
                )
                return False
            
            logger.debug(f"Daily loss check passed: {loss_percent * 100:.2f}%")
            return True
            
        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}")
            return False
        finally:
            session.close()
    
    def record_error(self):
        """Record an API/execution error for circuit breaker."""
        self.consecutive_errors += 1
        logger.warning(f"Error recorded: {self.consecutive_errors}/{self.error_threshold}")
        
        if self.consecutive_errors >= self.error_threshold:
            self.activate_circuit_breaker()
    
    def reset_error_count(self):
        """Reset error count after successful operation."""
        if self.consecutive_errors > 0:
            logger.info(f"Resetting error count from {self.consecutive_errors}")
            self.consecutive_errors = 0
    
    def activate_circuit_breaker(self):
        """Activate circuit breaker to stop trading."""
        if not self.circuit_breaker_active:
            self.circuit_breaker_active = True
            self._set_system_state("circuit_breaker_active", "true")
            logger.error(
                f"CIRCUIT BREAKER ACTIVATED: {self.consecutive_errors} consecutive errors"
            )
    
    def deactivate_circuit_breaker(self):
        """Manually deactivate circuit breaker."""
        self.circuit_breaker_active = False
        self.consecutive_errors = 0
        self._set_system_state("circuit_breaker_active", "false")
        logger.info("Circuit breaker deactivated")
    
    def activate_kill_switch(self):
        """Manually activate kill-switch."""
        self.kill_switch_active = True
        self._set_system_state("kill_switch_active", "true")
        logger.error("Kill-switch manually activated")
    
    def deactivate_kill_switch(self):
        """Manually deactivate kill-switch."""
        self.kill_switch_active = False
        self._set_system_state("kill_switch_active", "false")
        logger.info("Kill-switch deactivated")
    
    def is_trading_allowed(self) -> bool:
        """
        Check if trading is allowed based on all risk controls.
        
        Returns:
            True if trading is allowed, False otherwise
        """
        if self.kill_switch_active:
            logger.warning("Trading blocked: kill-switch active")
            return False
        
        if self.circuit_breaker_active:
            logger.warning("Trading blocked: circuit breaker active")
            return False
        
        return True
    
    def get_status(self) -> Dict[str, any]:
        """
        Get current risk control status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'kill_switch_active': self.kill_switch_active,
            'circuit_breaker_active': self.circuit_breaker_active,
            'consecutive_errors': self.consecutive_errors,
            'error_threshold': self.error_threshold,
            'trading_allowed': self.is_trading_allowed()
        }
    
    def _set_system_state(self, key: str, value: str):
        """Set a system state value in database."""
        session = self.db.get_session()
        try:
            state = session.query(SystemState).filter(SystemState.key == key).first()
            
            if state:
                state.value = value
                state.updated_at = datetime.utcnow()
            else:
                state = SystemState(key=key, value=value)
                session.add(state)
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting system state: {e}")
        finally:
            session.close()
    
    def _get_system_state(self, key: str) -> Optional[str]:
        """Get a system state value from database."""
        session = self.db.get_session()
        try:
            state = session.query(SystemState).filter(SystemState.key == key).first()
            return state.value if state else None
        finally:
            session.close()
    
    def restore_state_from_db(self):
        """Restore risk control state from database (after restart)."""
        kill_switch = self._get_system_state("kill_switch_active")
        circuit_breaker = self._get_system_state("circuit_breaker_active")
        
        self.kill_switch_active = kill_switch == "true"
        self.circuit_breaker_active = circuit_breaker == "true"
        
        logger.info(
            f"Restored risk control state: "
            f"kill_switch={self.kill_switch_active}, "
            f"circuit_breaker={self.circuit_breaker_active}"
        )
