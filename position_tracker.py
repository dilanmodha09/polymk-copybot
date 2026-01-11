"""
Position tracker for managing open positions.
"""
from typing import Dict, Optional, List
from datetime import datetime
from models import Position, TradeSide, Database
from sqlalchemy import and_
from logger import get_logger

logger = get_logger(__name__)


class PositionTracker:
    """Track and manage open positions."""
    
    def __init__(self, db: Database):
        """
        Initialize position tracker.
        
        Args:
            db: Database instance
        """
        self.db = db
        logger.info("Initialized PositionTracker")
    
    def open_position(
        self,
        market_id: str,
        outcome_side: TradeSide,
        shares: float,
        usdc_invested: float,
        price: float,
        source_position_id: Optional[str] = None
    ) -> Position:
        """
        Open a new position or add to existing one.
        
        Args:
            market_id: Market ID
            outcome_side: YES or NO
            shares: Number of shares
            usdc_invested: USDC invested
            price: Entry price
            source_position_id: Reference to source position
            
        Returns:
            Position object
        """
        session = self.db.get_session()
        try:
            # Check if position already exists
            existing_position = session.query(Position).filter(
                and_(
                    Position.market_id == market_id,
                    Position.outcome_side == outcome_side,
                    Position.is_open == True
                )
            ).first()
            
            if existing_position:
                # Update existing position
                total_shares = existing_position.total_shares + shares
                total_usdc = existing_position.total_usdc_invested + usdc_invested
                
                # Calculate new average price
                existing_position.average_price = total_usdc / total_shares if total_shares > 0 else price
                existing_position.total_shares = total_shares
                existing_position.total_usdc_invested = total_usdc
                existing_position.updated_at = datetime.utcnow()
                
                session.commit()
                logger.info(
                    f"Updated position {existing_position.id}: "
                    f"{market_id} {outcome_side.value} - {total_shares:.2f} shares"
                )
                return existing_position
            else:
                # Create new position
                position = Position(
                    market_id=market_id,
                    outcome_side=outcome_side,
                    total_shares=shares,
                    total_usdc_invested=usdc_invested,
                    average_price=price,
                    source_position_id=source_position_id,
                    is_open=True,
                    opened_at=datetime.utcnow()
                )
                
                session.add(position)
                session.commit()
                
                logger.info(
                    f"Opened new position {position.id}: "
                    f"{market_id} {outcome_side.value} - {shares:.2f} shares at ${price:.3f}"
                )
                return position
                
        except Exception as e:
            session.rollback()
            logger.error(f"Error opening position: {e}")
            raise
        finally:
            session.close()
    
    def reduce_position(
        self,
        market_id: str,
        outcome_side: TradeSide,
        shares_to_reduce: float
    ) -> Optional[Position]:
        """
        Reduce an open position.
        
        Args:
            market_id: Market ID
            outcome_side: YES or NO
            shares_to_reduce: Number of shares to reduce
            
        Returns:
            Updated Position object or None if not found
        """
        session = self.db.get_session()
        try:
            position = session.query(Position).filter(
                and_(
                    Position.market_id == market_id,
                    Position.outcome_side == outcome_side,
                    Position.is_open == True
                )
            ).first()
            
            if not position:
                logger.warning(f"No open position found for {market_id} {outcome_side.value}")
                return None
            
            if shares_to_reduce >= position.total_shares:
                # Close entire position
                return self.close_position(market_id, outcome_side)
            
            # Reduce position proportionally
            reduction_ratio = shares_to_reduce / position.total_shares
            usdc_to_reduce = position.total_usdc_invested * reduction_ratio
            
            position.total_shares -= shares_to_reduce
            position.total_usdc_invested -= usdc_to_reduce
            position.updated_at = datetime.utcnow()
            
            session.commit()
            
            logger.info(
                f"Reduced position {position.id}: "
                f"removed {shares_to_reduce:.2f} shares, "
                f"remaining {position.total_shares:.2f} shares"
            )
            return position
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error reducing position: {e}")
            raise
        finally:
            session.close()
    
    def close_position(
        self,
        market_id: str,
        outcome_side: TradeSide
    ) -> Optional[Position]:
        """
        Close an open position.
        
        Args:
            market_id: Market ID
            outcome_side: YES or NO
            
        Returns:
            Closed Position object or None if not found
        """
        session = self.db.get_session()
        try:
            position = session.query(Position).filter(
                and_(
                    Position.market_id == market_id,
                    Position.outcome_side == outcome_side,
                    Position.is_open == True
                )
            ).first()
            
            if not position:
                logger.warning(f"No open position found for {market_id} {outcome_side.value}")
                return None
            
            position.is_open = False
            position.closed_at = datetime.utcnow()
            position.total_shares = 0
            
            session.commit()
            
            logger.info(f"Closed position {position.id}: {market_id} {outcome_side.value}")
            return position
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error closing position: {e}")
            raise
        finally:
            session.close()
    
    def get_position(
        self,
        market_id: str,
        outcome_side: TradeSide
    ) -> Optional[Position]:
        """
        Get an open position.
        
        Args:
            market_id: Market ID
            outcome_side: YES or NO
            
        Returns:
            Position object or None if not found
        """
        session = self.db.get_session()
        try:
            position = session.query(Position).filter(
                and_(
                    Position.market_id == market_id,
                    Position.outcome_side == outcome_side,
                    Position.is_open == True
                )
            ).first()
            return position
        finally:
            session.close()
    
    def get_all_open_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of open Position objects
        """
        session = self.db.get_session()
        try:
            positions = session.query(Position).filter(Position.is_open == True).all()
            logger.debug(f"Retrieved {len(positions)} open positions")
            return positions
        finally:
            session.close()
    
    def get_total_position_value(self) -> float:
        """
        Get total value of all open positions (USDC invested).
        
        Returns:
            Total USDC invested across all positions
        """
        session = self.db.get_session()
        try:
            positions = session.query(Position).filter(Position.is_open == True).all()
            total = sum(p.total_usdc_invested for p in positions)
            logger.debug(f"Total position value: {total:.2f} USDC")
            return total
        finally:
            session.close()
    
    def get_position_for_market(self, market_id: str) -> Dict[str, Optional[Position]]:
        """
        Get all positions for a specific market.
        
        Args:
            market_id: Market ID
            
        Returns:
            Dictionary with 'yes' and 'no' positions
        """
        session = self.db.get_session()
        try:
            positions = session.query(Position).filter(
                and_(
                    Position.market_id == market_id,
                    Position.is_open == True
                )
            ).all()
            
            result = {'yes': None, 'no': None}
            for position in positions:
                if position.outcome_side == TradeSide.YES:
                    result['yes'] = position
                elif position.outcome_side == TradeSide.NO:
                    result['no'] = position
            
            return result
        finally:
            session.close()
