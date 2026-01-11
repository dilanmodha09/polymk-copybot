"""
Database models for Polymarket Copy Trading Bot.
"""
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, 
    DateTime, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum


Base = declarative_base()


class TradeStatus(enum.Enum):
    """Status of a trade."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeType(enum.Enum):
    """Type of trade."""
    MARKET = "market"
    LIMIT = "limit"


class TradeSide(enum.Enum):
    """Side of trade."""
    YES = "yes"
    NO = "no"


class TradeAction(enum.Enum):
    """Action of trade."""
    OPEN = "open"
    CLOSE = "close"
    PARTIAL_CLOSE = "partial_close"


class SourceTrade(Base):
    """Model for trades from the source wallet."""
    __tablename__ = "source_trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_hash = Column(String, unique=True, nullable=False, index=True)
    market_id = Column(String, nullable=False, index=True)
    outcome_side = Column(SQLEnum(TradeSide), nullable=False)
    trade_type = Column(SQLEnum(TradeType), nullable=False)
    action = Column(SQLEnum(TradeAction), nullable=False)
    
    size_shares = Column(Float, nullable=False)
    size_usdc = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    block_number = Column(Integer, nullable=True)
    transaction_hash = Column(String, nullable=True)
    
    # Processing status
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    follower_trades = relationship("FollowerTrade", back_populates="source_trade")
    
    def __repr__(self):
        return f"<SourceTrade(id={self.id}, market={self.market_id}, action={self.action.value})>"


class FollowerTrade(Base):
    """Model for trades executed by the follower wallet."""
    __tablename__ = "follower_trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_trade_id = Column(Integer, ForeignKey("source_trades.id"), nullable=False, index=True)
    
    market_id = Column(String, nullable=False, index=True)
    outcome_side = Column(SQLEnum(TradeSide), nullable=False)
    trade_type = Column(SQLEnum(TradeType), nullable=False)
    action = Column(SQLEnum(TradeAction), nullable=False)
    
    # Original source trade details
    source_size_shares = Column(Float, nullable=False)
    source_size_usdc = Column(Float, nullable=False)
    
    # Scaled follower trade details
    follower_size_shares = Column(Float, nullable=False)
    follower_size_usdc = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    
    # Scaling factor used
    scale_factor = Column(Float, nullable=False)
    
    # Execution details
    status = Column(SQLEnum(TradeStatus), nullable=False, default=TradeStatus.PENDING, index=True)
    submitted_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    transaction_hash = Column(String, nullable=True)
    gas_used = Column(Float, nullable=True)
    
    # Error handling
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    source_trade = relationship("SourceTrade", back_populates="follower_trades")
    
    def __repr__(self):
        return f"<FollowerTrade(id={self.id}, status={self.status.value}, market={self.market_id})>"


class Position(Base):
    """Model for tracking open positions."""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, nullable=False, index=True)
    outcome_side = Column(SQLEnum(TradeSide), nullable=False)
    
    # Position details
    total_shares = Column(Float, nullable=False, default=0.0)
    total_usdc_invested = Column(Float, nullable=False, default=0.0)
    average_price = Column(Float, nullable=False, default=0.0)
    
    # Tracking
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    is_open = Column(Boolean, default=True, index=True)
    
    # Source position reference
    source_position_id = Column(String, nullable=True, index=True)
    
    def __repr__(self):
        return f"<Position(id={self.id}, market={self.market_id}, shares={self.total_shares})>"


class WalletBalance(Base):
    """Model for tracking wallet balances over time."""
    __tablename__ = "wallet_balances"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_address = Column(String, nullable=False, index=True)
    
    usdc_balance = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False, default=0.0)
    total_value = Column(Float, nullable=False)
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<WalletBalance(wallet={self.wallet_address[:8]}, balance={self.usdc_balance})>"


class SystemState(Base):
    """Model for tracking system state and health."""
    __tablename__ = "system_state"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<SystemState(key={self.key}, value={self.value})>"


# Create indexes for performance
Index("idx_source_trades_market_time", SourceTrade.market_id, SourceTrade.timestamp)
Index("idx_follower_trades_status_time", FollowerTrade.status, FollowerTrade.submitted_at)
Index("idx_positions_market_side", Position.market_id, Position.outcome_side, Position.is_open)


class Database:
    """Database connection and session management."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get a new database session."""
        return self.SessionLocal()
    
    def drop_tables(self):
        """Drop all tables (use with caution)."""
        Base.metadata.drop_all(bind=self.engine)
