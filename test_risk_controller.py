"""
Unit tests for Risk Controller.
"""
import pytest
from datetime import datetime, timedelta
from models import Database, WalletBalance
from risk_controller import RiskController


class TestRiskController:
    """Test cases for RiskController."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Use in-memory database for testing
        self.db = Database("sqlite:///:memory:")
        self.db.create_tables()
        
        self.controller = RiskController(
            db=self.db,
            max_wallet_utilization_percent=80.0,
            daily_loss_limit_percent=10.0,
            circuit_breaker_error_threshold=5
        )
    
    def test_check_wallet_utilization_valid(self):
        """Test wallet utilization check with valid trade."""
        result = self.controller.check_wallet_utilization(
            current_balance=5000.0,
            total_position_value=2000.0,  # 40% utilized
            proposed_trade_size=1000.0    # Would be 60% utilized
        )
        
        assert result is True
    
    def test_check_wallet_utilization_exceeds(self):
        """Test wallet utilization check exceeding limit."""
        result = self.controller.check_wallet_utilization(
            current_balance=5000.0,
            total_position_value=3000.0,  # Currently 37.5% utilized (3000/8000)
            proposed_trade_size=4000.0    # Would be 87.5% utilized (7000/8000 > 80%)
        )
        
        assert result is False
    
    def test_check_wallet_utilization_at_limit(self):
        """Test wallet utilization exactly at limit."""
        result = self.controller.check_wallet_utilization(
            current_balance=5000.0,
            total_position_value=2000.0,  # 40% utilized
            proposed_trade_size=2000.0    # Would be exactly 80% utilized
        )
        
        assert result is True
    
    def test_error_counting(self):
        """Test error counting for circuit breaker."""
        assert self.controller.consecutive_errors == 0
        assert self.controller.circuit_breaker_active is False
        
        # Record errors
        for i in range(4):
            self.controller.record_error()
            assert self.controller.consecutive_errors == i + 1
            assert self.controller.circuit_breaker_active is False
        
        # Fifth error should trigger circuit breaker
        self.controller.record_error()
        assert self.controller.consecutive_errors == 5
        assert self.controller.circuit_breaker_active is True
    
    def test_error_reset(self):
        """Test error count reset."""
        self.controller.record_error()
        self.controller.record_error()
        assert self.controller.consecutive_errors == 2
        
        self.controller.reset_error_count()
        assert self.controller.consecutive_errors == 0
    
    def test_circuit_breaker_activation(self):
        """Test manual circuit breaker activation."""
        assert self.controller.circuit_breaker_active is False
        
        self.controller.activate_circuit_breaker()
        assert self.controller.circuit_breaker_active is True
        
        self.controller.deactivate_circuit_breaker()
        assert self.controller.circuit_breaker_active is False
        assert self.controller.consecutive_errors == 0
    
    def test_kill_switch_activation(self):
        """Test manual kill-switch activation."""
        assert self.controller.kill_switch_active is False
        
        self.controller.activate_kill_switch()
        assert self.controller.kill_switch_active is True
        
        self.controller.deactivate_kill_switch()
        assert self.controller.kill_switch_active is False
    
    def test_is_trading_allowed(self):
        """Test trading allowed check."""
        # Initially should be allowed
        assert self.controller.is_trading_allowed() is True
        
        # Activate kill-switch
        self.controller.activate_kill_switch()
        assert self.controller.is_trading_allowed() is False
        
        # Deactivate kill-switch, activate circuit breaker
        self.controller.deactivate_kill_switch()
        self.controller.activate_circuit_breaker()
        assert self.controller.is_trading_allowed() is False
        
        # Both inactive
        self.controller.deactivate_circuit_breaker()
        assert self.controller.is_trading_allowed() is True
    
    def test_get_status(self):
        """Test status reporting."""
        status = self.controller.get_status()
        
        assert 'kill_switch_active' in status
        assert 'circuit_breaker_active' in status
        assert 'consecutive_errors' in status
        assert 'error_threshold' in status
        assert 'trading_allowed' in status
        
        assert status['kill_switch_active'] is False
        assert status['circuit_breaker_active'] is False
        assert status['consecutive_errors'] == 0
        assert status['trading_allowed'] is True
    
    def test_check_daily_loss_limit_no_data(self):
        """Test daily loss check with no historical data."""
        result = self.controller.check_daily_loss_limit("0x123")
        
        # Should allow trading when no data
        assert result is True
    
    def test_check_daily_loss_limit_within_limit(self):
        """Test daily loss check within acceptable limit."""
        session = self.db.get_session()
        
        wallet_address = "0x123"
        
        # Create balance from 23 hours ago: $10,000
        past_balance = WalletBalance(
            wallet_address=wallet_address,
            usdc_balance=10000.0,
            positions_value=0.0,
            total_value=10000.0,
            timestamp=datetime.utcnow() - timedelta(hours=23)
        )
        session.add(past_balance)
        
        # Current balance: $9,500 (5% loss - within 10% limit)
        current_balance = WalletBalance(
            wallet_address=wallet_address,
            usdc_balance=9500.0,
            positions_value=0.0,
            total_value=9500.0,
            timestamp=datetime.utcnow()
        )
        session.add(current_balance)
        session.commit()
        session.close()
        
        result = self.controller.check_daily_loss_limit(wallet_address)
        assert result is True
        assert self.controller.kill_switch_active is False
    
    def test_check_daily_loss_limit_exceeds(self):
        """Test daily loss check exceeding limit."""
        session = self.db.get_session()
        
        wallet_address = "0x456"
        
        # Create balance from 23 hours ago: $10,000
        past_balance = WalletBalance(
            wallet_address=wallet_address,
            usdc_balance=10000.0,
            positions_value=0.0,
            total_value=10000.0,
            timestamp=datetime.utcnow() - timedelta(hours=23)
        )
        session.add(past_balance)
        
        # Current balance: $8,500 (15% loss - exceeds 10% limit)
        current_balance = WalletBalance(
            wallet_address=wallet_address,
            usdc_balance=8500.0,
            positions_value=0.0,
            total_value=8500.0,
            timestamp=datetime.utcnow()
        )
        session.add(current_balance)
        session.commit()
        session.close()
        
        result = self.controller.check_daily_loss_limit(wallet_address)
        assert result is False
        assert self.controller.kill_switch_active is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
