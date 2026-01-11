"""
Trade scaling engine for calculating proportional position sizes.
"""
from typing import Optional
from logger import get_logger

logger = get_logger(__name__)


class TradeScaler:
    """Engine for scaling trades proportionally based on wallet balances."""
    
    def __init__(
        self,
        min_order_size_usdc: float = 1.0,
        max_position_size_percent: float = 20.0,
        max_wallet_utilization_percent: float = 80.0,
        tick_size: float = 0.01
    ):
        """
        Initialize trade scaler.
        
        Args:
            min_order_size_usdc: Minimum order size in USDC
            max_position_size_percent: Maximum position size as % of follower wallet
            max_wallet_utilization_percent: Maximum % of wallet that can be used
            tick_size: Minimum price increment (default: 0.01)
        """
        self.min_order_size_usdc = min_order_size_usdc
        self.max_position_size_percent = max_position_size_percent / 100.0
        self.max_wallet_utilization_percent = max_wallet_utilization_percent / 100.0
        self.tick_size = tick_size
        
        logger.info(
            f"Initialized TradeScaler: min={min_order_size_usdc} USDC, "
            f"max_position={max_position_size_percent}%, "
            f"max_utilization={max_wallet_utilization_percent}%"
        )
    
    def calculate_scale_factor(
        self,
        source_wallet_balance: float,
        follower_wallet_balance: float
    ) -> float:
        """
        Calculate the scaling factor based on wallet balances.
        
        Formula: scale = FollowerWalletUSDC / SourceWalletUSDC
        
        Args:
            source_wallet_balance: Source wallet balance in USDC
            follower_wallet_balance: Follower wallet balance in USDC
            
        Returns:
            Scale factor as float
        """
        if source_wallet_balance <= 0:
            logger.error("Source wallet balance must be positive")
            return 0.0
        
        scale = follower_wallet_balance / source_wallet_balance
        logger.debug(f"Calculated scale factor: {scale:.4f}")
        return scale
    
    def scale_trade(
        self,
        source_size_usdc: float,
        source_size_shares: float,
        scale_factor: float,
        follower_wallet_balance: float,
        current_position_size_usdc: float = 0.0
    ) -> Optional[dict]:
        """
        Scale a trade based on the scale factor and risk controls.
        
        Args:
            source_size_usdc: Source trade size in USDC
            source_size_shares: Source trade size in shares
            scale_factor: Scaling factor to apply
            follower_wallet_balance: Current follower wallet balance
            current_position_size_usdc: Current position size for this market
            
        Returns:
            Dictionary with scaled trade details or None if trade should be skipped
        """
        # Calculate raw scaled size
        raw_follower_size_usdc = source_size_usdc * scale_factor
        raw_follower_size_shares = source_size_shares * scale_factor
        
        logger.debug(
            f"Scaling trade: source={source_size_usdc:.2f} USDC, "
            f"scale={scale_factor:.4f}, raw_follower={raw_follower_size_usdc:.2f} USDC"
        )
        
        # Check minimum order size
        if raw_follower_size_usdc < self.min_order_size_usdc:
            logger.warning(
                f"Scaled trade size {raw_follower_size_usdc:.2f} USDC is below "
                f"minimum {self.min_order_size_usdc} USDC. Trade skipped."
            )
            return None
        
        # Check maximum position size
        max_position_usdc = follower_wallet_balance * self.max_position_size_percent
        new_position_size = current_position_size_usdc + raw_follower_size_usdc
        
        if new_position_size > max_position_usdc:
            # Cap the trade size
            available_usdc = max_position_usdc - current_position_size_usdc
            
            if available_usdc < self.min_order_size_usdc:
                logger.warning(
                    f"Position size limit reached. Available: {available_usdc:.2f} USDC, "
                    f"needed: {raw_follower_size_usdc:.2f} USDC. Trade skipped."
                )
                return None
            
            # Scale down to available size
            size_reduction_factor = available_usdc / raw_follower_size_usdc
            raw_follower_size_usdc = available_usdc
            raw_follower_size_shares = raw_follower_size_shares * size_reduction_factor
            
            logger.warning(
                f"Trade size capped to position limit. "
                f"Adjusted to {raw_follower_size_usdc:.2f} USDC"
            )
        
        # Check maximum wallet utilization
        max_wallet_usdc = follower_wallet_balance * self.max_wallet_utilization_percent
        
        if current_position_size_usdc + raw_follower_size_usdc > max_wallet_usdc:
            logger.warning(
                f"Trade would exceed maximum wallet utilization "
                f"({self.max_wallet_utilization_percent * 100:.0f}%). Trade skipped."
            )
            return None
        
        # Round to tick size (for shares)
        follower_size_shares = self._round_to_tick(raw_follower_size_shares)
        follower_size_usdc = round(raw_follower_size_usdc, 2)
        
        result = {
            'follower_size_usdc': follower_size_usdc,
            'follower_size_shares': follower_size_shares,
            'scale_factor': scale_factor,
            'raw_size_usdc': raw_follower_size_usdc,
            'raw_size_shares': raw_follower_size_shares,
            'was_capped': new_position_size > max_position_usdc
        }
        
        logger.info(
            f"Scaled trade: {source_size_usdc:.2f} USDC -> {follower_size_usdc:.2f} USDC "
            f"({follower_size_shares:.2f} shares)"
        )
        
        return result
    
    def scale_close_trade(
        self,
        source_close_size_shares: float,
        source_total_position_shares: float,
        follower_total_position_shares: float
    ) -> float:
        """
        Scale a close/reduce position trade.
        
        Args:
            source_close_size_shares: Shares being closed in source
            source_total_position_shares: Total position shares in source
            follower_total_position_shares: Total position shares in follower
            
        Returns:
            Follower close size in shares
        """
        if source_total_position_shares <= 0:
            logger.error("Source total position must be positive")
            return 0.0
        
        # Calculate the proportion being closed
        close_proportion = source_close_size_shares / source_total_position_shares
        
        # Apply same proportion to follower position
        follower_close_size = follower_total_position_shares * close_proportion
        
        # Round to tick size
        follower_close_size = self._round_to_tick(follower_close_size)
        
        logger.info(
            f"Scaled close: closing {close_proportion * 100:.1f}% of position "
            f"({follower_close_size:.2f} shares)"
        )
        
        return follower_close_size
    
    def _round_to_tick(self, value: float) -> float:
        """
        Round a value to the nearest tick size.
        
        Args:
            value: Value to round
            
        Returns:
            Rounded value
        """
        return round(value / self.tick_size) * self.tick_size
    
    def validate_trade_size(
        self,
        trade_size_usdc: float,
        follower_wallet_balance: float
    ) -> bool:
        """
        Validate if a trade size is acceptable.
        
        Args:
            trade_size_usdc: Trade size in USDC
            follower_wallet_balance: Follower wallet balance
            
        Returns:
            True if valid, False otherwise
        """
        if trade_size_usdc < self.min_order_size_usdc:
            logger.warning(f"Trade size {trade_size_usdc} below minimum")
            return False
        
        max_position = follower_wallet_balance * self.max_position_size_percent
        if trade_size_usdc > max_position:
            logger.warning(f"Trade size {trade_size_usdc} exceeds position limit")
            return False
        
        return True
