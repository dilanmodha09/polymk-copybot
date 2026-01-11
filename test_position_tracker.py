"""
Test position tracker functionality.
"""
import pytest
from models import Database, TradeSide
from position_tracker import PositionTracker


class TestPositionTracker:
    """Test cases for PositionTracker."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.db = Database("sqlite:///:memory:")
        self.db.create_tables()
        self.tracker = PositionTracker(self.db)
    
    def test_open_new_position(self):
        """Test opening a new position."""
        position = self.tracker.open_position(
            market_id="market_1",
            outcome_side=TradeSide.YES,
            shares=100.0,
            usdc_invested=60.0,
            price=0.60
        )
        
        assert position is not None
        assert position.market_id == "market_1"
        assert position.total_shares == 100.0
        assert position.average_price == 0.60
        assert position.is_open is True
    
    def test_add_to_existing_position(self):
        """Test adding to an existing position."""
        # Open initial position
        position1 = self.tracker.open_position(
            market_id="market_2",
            outcome_side=TradeSide.NO,
            shares=100.0,
            usdc_invested=70.0,
            price=0.70
        )
        
        # Add to position
        position2 = self.tracker.open_position(
            market_id="market_2",
            outcome_side=TradeSide.NO,
            shares=50.0,
            usdc_invested=32.5,
            price=0.65
        )
        
        # Should be same position object
        assert position1.id == position2.id
        
        # Check updated values
        assert position2.total_shares == 150.0
        assert position2.total_usdc_invested == 102.5
        
        # Average price should be (70 + 32.5) / 150 = 0.683
        assert abs(position2.average_price - 0.683) < 0.001
    
    def test_reduce_position(self):
        """Test reducing a position."""
        # Open position
        self.tracker.open_position(
            market_id="market_3",
            outcome_side=TradeSide.YES,
            shares=100.0,
            usdc_invested=55.0,
            price=0.55
        )
        
        # Reduce by 30 shares
        position = self.tracker.reduce_position(
            market_id="market_3",
            outcome_side=TradeSide.YES,
            shares_to_reduce=30.0
        )
        
        assert position is not None
        assert position.total_shares == 70.0
        
        # USDC should be reduced proportionally: 55 * 0.7 = 38.5
        assert abs(position.total_usdc_invested - 38.5) < 0.01
        assert position.is_open is True
    
    def test_reduce_position_fully(self):
        """Test reducing position to zero closes it."""
        # Open position
        self.tracker.open_position(
            market_id="market_4",
            outcome_side=TradeSide.NO,
            shares=100.0,
            usdc_invested=80.0,
            price=0.80
        )
        
        # Reduce by all shares
        position = self.tracker.reduce_position(
            market_id="market_4",
            outcome_side=TradeSide.NO,
            shares_to_reduce=100.0
        )
        
        assert position is not None
        assert position.is_open is False
        assert position.total_shares == 0.0
    
    def test_close_position(self):
        """Test closing a position."""
        # Open position
        self.tracker.open_position(
            market_id="market_5",
            outcome_side=TradeSide.YES,
            shares=100.0,
            usdc_invested=45.0,
            price=0.45
        )
        
        # Close position
        position = self.tracker.close_position(
            market_id="market_5",
            outcome_side=TradeSide.YES
        )
        
        assert position is not None
        assert position.is_open is False
        assert position.total_shares == 0.0
        assert position.closed_at is not None
    
    def test_get_position(self):
        """Test getting a position."""
        # Open position
        original = self.tracker.open_position(
            market_id="market_6",
            outcome_side=TradeSide.NO,
            shares=50.0,
            usdc_invested=30.0,
            price=0.60
        )
        
        # Get position
        retrieved = self.tracker.get_position(
            market_id="market_6",
            outcome_side=TradeSide.NO
        )
        
        assert retrieved is not None
        assert retrieved.id == original.id
        assert retrieved.total_shares == 50.0
    
    def test_get_nonexistent_position(self):
        """Test getting a position that doesn't exist."""
        position = self.tracker.get_position(
            market_id="nonexistent",
            outcome_side=TradeSide.YES
        )
        
        assert position is None
    
    def test_get_all_open_positions(self):
        """Test getting all open positions."""
        # Open multiple positions
        self.tracker.open_position("market_7", TradeSide.YES, 100, 50, 0.50)
        self.tracker.open_position("market_8", TradeSide.NO, 50, 30, 0.60)
        self.tracker.open_position("market_9", TradeSide.YES, 75, 45, 0.60)
        
        # Close one
        self.tracker.close_position("market_8", TradeSide.NO)
        
        # Get all open
        positions = self.tracker.get_all_open_positions()
        
        assert len(positions) == 2
        assert all(p.is_open for p in positions)
    
    def test_get_total_position_value(self):
        """Test getting total position value."""
        # Open multiple positions
        self.tracker.open_position("market_10", TradeSide.YES, 100, 60, 0.60)
        self.tracker.open_position("market_11", TradeSide.NO, 50, 40, 0.80)
        
        total = self.tracker.get_total_position_value()
        
        # Should be 60 + 40 = 100
        assert total == 100.0
    
    def test_multiple_sides_same_market(self):
        """Test having both YES and NO positions in same market."""
        # Open YES position
        yes_pos = self.tracker.open_position(
            market_id="market_12",
            outcome_side=TradeSide.YES,
            shares=100.0,
            usdc_invested=55.0,
            price=0.55
        )
        
        # Open NO position (different side, same market)
        no_pos = self.tracker.open_position(
            market_id="market_12",
            outcome_side=TradeSide.NO,
            shares=50.0,
            usdc_invested=25.0,
            price=0.50
        )
        
        # Should be different positions
        assert yes_pos.id != no_pos.id
        
        # Get both
        positions = self.tracker.get_position_for_market("market_12")
        
        assert positions['yes'] is not None
        assert positions['no'] is not None
        assert positions['yes'].total_shares == 100.0
        assert positions['no'].total_shares == 50.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
