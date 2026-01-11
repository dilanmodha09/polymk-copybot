"""
Unit tests for Trade Scaler.
"""
import pytest
from trade_scaler import TradeScaler


class TestTradeScaler:
    """Test cases for TradeScaler."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.scaler = TradeScaler(
            min_order_size_usdc=1.0,
            max_position_size_percent=20.0,
            max_wallet_utilization_percent=80.0,
            tick_size=0.01
        )
    
    def test_calculate_scale_factor(self):
        """Test scale factor calculation."""
        # Source has $10,000, follower has $5,000
        scale = self.scaler.calculate_scale_factor(10000, 5000)
        assert scale == 0.5
        
        # Source has $5,000, follower has $10,000
        scale = self.scaler.calculate_scale_factor(5000, 10000)
        assert scale == 2.0
        
        # Equal balances
        scale = self.scaler.calculate_scale_factor(5000, 5000)
        assert scale == 1.0
    
    def test_scale_factor_zero_source(self):
        """Test scale factor with zero source balance."""
        scale = self.scaler.calculate_scale_factor(0, 5000)
        assert scale == 0.0
    
    def test_scale_trade_basic(self):
        """Test basic trade scaling."""
        result = self.scaler.scale_trade(
            source_size_usdc=100.0,
            source_size_shares=100.0,
            scale_factor=0.5,
            follower_wallet_balance=5000.0
        )
        
        assert result is not None
        assert result['follower_size_usdc'] == 50.0
        assert result['follower_size_shares'] == 50.0
        assert result['scale_factor'] == 0.5
    
    def test_scale_trade_below_minimum(self):
        """Test trade scaling below minimum size."""
        result = self.scaler.scale_trade(
            source_size_usdc=10.0,
            source_size_shares=10.0,
            scale_factor=0.05,  # Would result in $0.50
            follower_wallet_balance=5000.0
        )
        
        # Should be rejected as below $1 minimum
        assert result is None
    
    def test_scale_trade_position_limit(self):
        """Test trade scaling with position size limit."""
        # Max position is 20% of $5000 = $1000
        # Current position is $800
        # Requesting $300 scaled trade should be capped to $200
        
        result = self.scaler.scale_trade(
            source_size_usdc=600.0,
            source_size_shares=600.0,
            scale_factor=0.5,  # Would be $300
            follower_wallet_balance=5000.0,
            current_position_size_usdc=800.0
        )
        
        assert result is not None
        # Should be capped to available $200
        assert result['follower_size_usdc'] == 200.0
        assert result['was_capped'] is True
    
    def test_scale_trade_exceeds_wallet_utilization(self):
        """Test trade exceeding wallet utilization limit."""
        # Max utilization is 80% of $5000 = $4000
        # Current position is $3900
        # Requesting $200 trade should be rejected
        
        result = self.scaler.scale_trade(
            source_size_usdc=400.0,
            source_size_shares=400.0,
            scale_factor=0.5,  # Would be $200
            follower_wallet_balance=5000.0,
            current_position_size_usdc=3900.0
        )
        
        # Should be rejected
        assert result is None
    
    def test_round_to_tick(self):
        """Test tick size rounding."""
        # Test rounding (use approximate comparison for floating point)
        assert abs(self.scaler._round_to_tick(10.123) - 10.12) < 0.001
        # 10.125 rounds to 10.12 (banker's rounding / round half to even)
        assert abs(self.scaler._round_to_tick(10.125) - 10.12) < 0.001
        assert abs(self.scaler._round_to_tick(10.129) - 10.13) < 0.001
    
    def test_scale_close_trade(self):
        """Test scaling a close trade."""
        # Source closing 50% of position (50 out of 100 shares)
        # Follower has 60 shares total
        
        follower_close = self.scaler.scale_close_trade(
            source_close_size_shares=50.0,
            source_total_position_shares=100.0,
            follower_total_position_shares=60.0
        )
        
        # Should close 50% of follower position
        assert follower_close == 30.0
    
    def test_validate_trade_size(self):
        """Test trade size validation."""
        # Valid trade
        assert self.scaler.validate_trade_size(100.0, 5000.0) is True
        
        # Below minimum
        assert self.scaler.validate_trade_size(0.5, 5000.0) is False
        
        # Exceeds position limit (20% of 5000 = 1000)
        assert self.scaler.validate_trade_size(1500.0, 5000.0) is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
