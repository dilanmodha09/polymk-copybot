"""
Test database models and operations.
"""
import pytest
from datetime import datetime
from models import (
    Database, SourceTrade, FollowerTrade, Position, WalletBalance,
    TradeStatus, TradeSide, TradeType, TradeAction
)


class TestModels:
    """Test database models."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.db = Database("sqlite:///:memory:")
        self.db.create_tables()
    
    def test_create_source_trade(self):
        """Test creating a source trade."""
        session = self.db.get_session()
        
        trade = SourceTrade(
            trade_hash="0xabc123",
            market_id="market_1",
            outcome_side=TradeSide.YES,
            trade_type=TradeType.MARKET,
            action=TradeAction.OPEN,
            size_shares=100.0,
            size_usdc=65.0,
            price=0.65,
            timestamp=datetime.utcnow()
        )
        
        session.add(trade)
        session.commit()
        
        # Query it back
        retrieved = session.query(SourceTrade).filter(
            SourceTrade.trade_hash == "0xabc123"
        ).first()
        
        assert retrieved is not None
        assert retrieved.market_id == "market_1"
        assert retrieved.size_shares == 100.0
        assert retrieved.processed is False
        
        session.close()
    
    def test_create_follower_trade(self):
        """Test creating a follower trade."""
        session = self.db.get_session()
        
        # First create source trade
        source_trade = SourceTrade(
            trade_hash="0xdef456",
            market_id="market_2",
            outcome_side=TradeSide.NO,
            trade_type=TradeType.LIMIT,
            action=TradeAction.OPEN,
            size_shares=50.0,
            size_usdc=35.0,
            price=0.70,
            timestamp=datetime.utcnow()
        )
        session.add(source_trade)
        session.commit()
        
        # Create follower trade
        follower_trade = FollowerTrade(
            source_trade_id=source_trade.id,
            market_id="market_2",
            outcome_side=TradeSide.NO,
            trade_type=TradeType.LIMIT,
            action=TradeAction.OPEN,
            source_size_shares=50.0,
            source_size_usdc=35.0,
            follower_size_shares=25.0,
            follower_size_usdc=17.5,
            price=0.70,
            scale_factor=0.5,
            status=TradeStatus.PENDING
        )
        session.add(follower_trade)
        session.commit()
        
        # Query it back
        retrieved = session.query(FollowerTrade).filter(
            FollowerTrade.source_trade_id == source_trade.id
        ).first()
        
        assert retrieved is not None
        assert retrieved.follower_size_shares == 25.0
        assert retrieved.scale_factor == 0.5
        assert retrieved.status == TradeStatus.PENDING
        
        session.close()
    
    def test_create_position(self):
        """Test creating a position."""
        session = self.db.get_session()
        
        position = Position(
            market_id="market_3",
            outcome_side=TradeSide.YES,
            total_shares=100.0,
            total_usdc_invested=60.0,
            average_price=0.60,
            is_open=True
        )
        
        session.add(position)
        session.commit()
        
        # Query it back
        retrieved = session.query(Position).filter(
            Position.market_id == "market_3",
            Position.is_open == True
        ).first()
        
        assert retrieved is not None
        assert retrieved.total_shares == 100.0
        assert retrieved.average_price == 0.60
        
        session.close()
    
    def test_wallet_balance(self):
        """Test wallet balance tracking."""
        session = self.db.get_session()
        
        balance = WalletBalance(
            wallet_address="0x123",
            usdc_balance=5000.0,
            positions_value=1000.0,
            total_value=6000.0
        )
        
        session.add(balance)
        session.commit()
        
        # Query it back
        retrieved = session.query(WalletBalance).filter(
            WalletBalance.wallet_address == "0x123"
        ).first()
        
        assert retrieved is not None
        assert retrieved.usdc_balance == 5000.0
        assert retrieved.total_value == 6000.0
        
        session.close()
    
    def test_unique_trade_hash(self):
        """Test that trade hash is unique."""
        session = self.db.get_session()
        
        trade1 = SourceTrade(
            trade_hash="0xunique",
            market_id="market_1",
            outcome_side=TradeSide.YES,
            trade_type=TradeType.MARKET,
            action=TradeAction.OPEN,
            size_shares=100.0,
            size_usdc=65.0,
            price=0.65,
            timestamp=datetime.utcnow()
        )
        
        session.add(trade1)
        session.commit()
        
        # Try to create another with same hash
        trade2 = SourceTrade(
            trade_hash="0xunique",
            market_id="market_2",
            outcome_side=TradeSide.NO,
            trade_type=TradeType.MARKET,
            action=TradeAction.OPEN,
            size_shares=50.0,
            size_usdc=25.0,
            price=0.50,
            timestamp=datetime.utcnow()
        )
        
        session.add(trade2)
        
        # Should raise integrity error
        with pytest.raises(Exception):
            session.commit()
        
        session.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
