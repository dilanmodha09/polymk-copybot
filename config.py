"""
Configuration management for Polymarket Copy Trading Bot.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Wallet Configuration
    source_wallet_address: str = Field(..., description="Address of the wallet to copy trades from")
    follower_wallet_address: str = Field(..., description="Address of the follower wallet")
    follower_wallet_private_key: str = Field(..., description="Private key for follower wallet")
    
    # Polymarket Configuration
    polymarket_api_url: str = Field(
        default="https://clob.polymarket.com",
        description="Polymarket CLOB API URL"
    )
    polygon_rpc_url: str = Field(..., description="Polygon RPC endpoint URL")
    polymarket_chain_id: int = Field(default=137, description="Polygon chain ID")
    
    # Scaling Parameters
    scaling_method: str = Field(default="proportional", description="Method for scaling trades")
    min_order_size_usdc: float = Field(default=1.0, description="Minimum order size in USDC")
    max_position_size_percent: float = Field(
        default=20.0,
        description="Maximum position size as percentage of follower wallet"
    )
    
    # Risk Controls
    max_wallet_utilization_percent: float = Field(
        default=80.0,
        description="Maximum percentage of wallet that can be used"
    )
    daily_loss_limit_percent: float = Field(
        default=10.0,
        description="Maximum daily loss before kill-switch activates"
    )
    circuit_breaker_error_threshold: int = Field(
        default=5,
        description="Number of consecutive API errors before circuit breaker triggers"
    )
    
    # Execution Parameters
    slippage_tolerance_percent: float = Field(
        default=2.0,
        description="Maximum acceptable slippage percentage"
    )
    max_gas_price_gwei: float = Field(
        default=500.0,
        description="Maximum gas price in Gwei"
    )
    retry_attempts: int = Field(default=3, description="Number of retry attempts for failed trades")
    retry_delay_seconds: float = Field(default=2.0, description="Delay between retries in seconds")
    
    # Monitoring & Polling
    polling_interval_seconds: float = Field(
        default=5.0,
        description="Interval for polling source wallet trades"
    )
    balance_check_interval_seconds: float = Field(
        default=30.0,
        description="Interval for checking wallet balances"
    )
    
    # Database
    database_url: str = Field(
        default="sqlite:///./polymarket_copybot.db",
        description="Database connection URL"
    )
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/copybot.log", description="Log file path")
    
    # Emergency Controls
    emergency_shutdown: bool = Field(default=False, description="Emergency shutdown flag")
    
    @validator("max_position_size_percent", "max_wallet_utilization_percent", "daily_loss_limit_percent")
    def validate_percentage(cls, v):
        if not 0 < v <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        return v
    
    @validator("slippage_tolerance_percent")
    def validate_slippage(cls, v):
        if not 0 <= v <= 50:
            raise ValueError("Slippage tolerance must be between 0 and 50")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global settings
    if settings is None:
        settings = Settings()
    return settings


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global settings
    settings = Settings()
    return settings
