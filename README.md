# Polymarket Copy Trading Bot

A production-grade system for automatically copying trades from a source Polymarket wallet to a follower wallet with intelligent position scaling and comprehensive risk controls.

## 🎯 Features

### Core Functionality
- **Real-time Trade Monitoring**: Monitors source wallet using Polymarket API and on-chain events (Polygon)
- **Intelligent Trade Scaling**: Proportionally scales trades based on wallet balances
- **Position Synchronization**: Automatically mirrors opens, closes, and partial exits
- **Multi-Market Support**: Handles multiple simultaneous positions across different markets

### Risk Controls
- **Maximum Position Size**: Limits individual positions to configurable % of wallet (default: 20%)
- **Wallet Utilization Cap**: Prevents over-allocation of capital (default: 80%)
- **Daily Loss Kill-Switch**: Automatically halts trading if daily loss exceeds threshold (default: 10%)
- **Circuit Breaker**: Stops trading after consecutive API/execution failures (default: 5 errors)
- **Emergency Shutdown**: Manual kill-switch for immediate trading halt

### Trade Execution
- **Slippage Protection**: Configurable slippage tolerance (default: 2%)
- **Automatic Retries**: Exponential backoff for failed trades (configurable attempts)
- **Gas Optimization**: Configurable maximum gas price limits
- **Minimum Order Size**: Enforces exchange minimums (default: $1 USDC)
- **Tick Size Rounding**: Respects Polymarket's price increments

### Architecture
- **State Persistence**: SQLite/PostgreSQL database for all state
- **Graceful Restart**: Recovers from restarts without losing state or double-executing
- **Dual Data Sources**: API + on-chain events for redundancy
- **Thread-Safe**: Concurrent balance monitoring and trade execution

## 📋 Requirements

- Python 3.8+
- Polygon RPC endpoint (Infura, Alchemy, or QuickNode)
- Polymarket account with USDC
- Source wallet to monitor (read-only)
- Follower wallet with private key (for trading)

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/dilanmodha09/polymk-copybot.git
cd polymk-copybot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy the example configuration
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Required Configuration:**
- `SOURCE_WALLET_ADDRESS`: Wallet address to copy trades from
- `FOLLOWER_WALLET_ADDRESS`: Your wallet address
- `FOLLOWER_WALLET_PRIVATE_KEY`: Your wallet's private key (KEEP SECRET!)
- `POLYGON_RPC_URL`: Your Polygon RPC endpoint

See `.env.example` for all available configuration options.

### 3. Initialize Database

```bash
# The database will be created automatically on first run
python main.py
```

### 4. Run the Bot

```bash
# Start the bot
python main.py

# Or run in background with nohup
nohup python main.py > output.log 2>&1 &

# Or use screen/tmux for persistent sessions
screen -S copybot
python main.py
# Ctrl+A, D to detach
```

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    POLYMARKET COPY TRADING BOT               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ Data Ingestion Layer   │                                 │
│  ├──────────────┤         ├──────────────┤                 │
│  │ Polymarket   │         │  Polygon     │                 │
│  │ API Client   │◄────────┤  Blockchain  │                 │
│  │              │         │  Listener    │                 │
│  └──────┬───────┘         └──────┬───────┘                 │
│         │                        │                          │
│         └────────┬───────────────┘                          │
│                  ▼                                           │
│         ┌────────────────┐                                  │
│         │  Trade Parser  │                                  │
│         │  & Validator   │                                  │
│         └────────┬───────┘                                  │
│                  ▼                                           │
│         ┌────────────────┐                                  │
│         │ Trade Scaling  │                                  │
│         │    Engine      │                                  │
│         └────────┬───────┘                                  │
│                  ▼                                           │
│         ┌────────────────┐      ┌──────────────┐           │
│         │ Risk Controls  │◄────►│  Database    │           │
│         │  & Validation  │      │  (SQLite/PG) │           │
│         └────────┬───────┘      └──────────────┘           │
│                  ▼                                           │
│         ┌────────────────┐                                  │
│         │     Trade      │                                  │
│         │   Executor     │                                  │
│         └────────┬───────┘                                  │
│                  ▼                                           │
│         ┌────────────────┐                                  │
│         │  Polymarket    │                                  │
│         │  Exchange      │                                  │
│         └────────────────┘                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🗄️ Database Schema

### Tables

**source_trades**: Tracks all detected source wallet trades
- `trade_hash`: Unique trade identifier
- `market_id`: Polymarket market ID
- `outcome_side`: YES or NO
- `size_shares`, `size_usdc`, `price`: Trade details
- `action`: OPEN, CLOSE, or PARTIAL_CLOSE
- `processed`: Whether trade has been mirrored

**follower_trades**: Tracks executed follower trades
- `source_trade_id`: Link to source trade
- `follower_size_shares`, `follower_size_usdc`: Scaled sizes
- `scale_factor`: Applied scaling factor
- `status`: PENDING, EXECUTING, COMPLETED, FAILED
- `transaction_hash`: On-chain transaction

**positions**: Tracks open positions
- `market_id`, `outcome_side`: Position identifier
- `total_shares`, `total_usdc_invested`: Position size
- `average_price`: Average entry price
- `is_open`: Position status

**wallet_balances**: Historical balance tracking
- `wallet_address`: Wallet identifier
- `usdc_balance`: Available USDC
- `positions_value`: Value of open positions
- `timestamp`: Recording time

**system_state**: Stores system state (kill-switch, circuit breaker)

## 🔧 Configuration Options

### Scaling Parameters

```python
# Proportional scaling based on wallet balance ratio
scale = follower_wallet_balance / source_wallet_balance
follower_trade_size = source_trade_size × scale
```

- `MIN_ORDER_SIZE_USDC`: Minimum trade size (default: $1)
- `MAX_POSITION_SIZE_PERCENT`: Max % of wallet per position (default: 20%)

### Risk Controls

- `MAX_WALLET_UTILIZATION_PERCENT`: Max % of wallet to use (default: 80%)
- `DAILY_LOSS_LIMIT_PERCENT`: Daily loss before kill-switch (default: 10%)
- `CIRCUIT_BREAKER_ERROR_THRESHOLD`: Errors before circuit breaker (default: 5)

### Execution Settings

- `SLIPPAGE_TOLERANCE_PERCENT`: Max slippage (default: 2%)
- `RETRY_ATTEMPTS`: Number of retries (default: 3)
- `MAX_GAS_PRICE_GWEI`: Max gas price (default: 500 Gwei)

## 📝 Usage Examples

### Basic Monitoring

The bot runs continuously, monitoring the source wallet and executing trades automatically:

```bash
python main.py
```

Output:
```
2024-01-11 10:00:00 - INFO - Initializing Polymarket Copy Trading Bot
2024-01-11 10:00:01 - INFO - Database initialized
2024-01-11 10:00:02 - INFO - Polymarket clients initialized
2024-01-11 10:00:03 - INFO - Starting Polymarket Copy Trading Bot
2024-01-11 10:00:03 - INFO - Source Wallet: 0x1234...
2024-01-11 10:00:03 - INFO - Follower Wallet: 0xabcd...
2024-01-11 10:00:04 - INFO - Follower wallet: 5000.00 USDC, Positions: 0.00 USDC
2024-01-11 10:00:05 - INFO - Entering main event loop
```

### Trade Execution Flow

When a source trade is detected:

```
2024-01-11 10:05:23 - INFO - Found 1 new trades to process
2024-01-11 10:05:23 - INFO - Stored new source trade: 123
2024-01-11 10:05:23 - INFO - Processing source trade 123: open
2024-01-11 10:05:23 - DEBUG - Calculated scale factor: 0.5000
2024-01-11 10:05:23 - INFO - Scaled trade: 100.00 USDC -> 50.00 USDC (50.00 shares)
2024-01-11 10:05:23 - INFO - Created follower trade record: 456
2024-01-11 10:05:24 - INFO - Executing trade attempt 1/3: open 50.00 USDC
2024-01-11 10:05:26 - INFO - Trade executed successfully
2024-01-11 10:05:26 - INFO - Opened new position 789: market_123 yes - 50.00 shares
```

### Emergency Shutdown

To stop trading immediately:

1. Edit `.env` file:
   ```bash
   EMERGENCY_SHUTDOWN=true
   ```

2. Or kill the process:
   ```bash
   pkill -f "python main.py"
   ```

The bot performs graceful shutdown, logging final state:

```
2024-01-11 15:30:00 - INFO - Initiating graceful shutdown
2024-01-11 15:30:00 - INFO - Risk control status: {'kill_switch_active': False, ...}
2024-01-11 15:30:00 - INFO - Open positions: 3
2024-01-11 15:30:00 - INFO -   - market_123 yes: 50.00 shares @ $0.650
2024-01-11 15:30:00 - INFO - Shutdown complete
```

## 🔒 Security Best Practices

1. **Private Key Security**
   - Never commit `.env` file to version control
   - Use environment variables or secure key management
   - Consider hardware wallet integration for production

2. **API Keys**
   - Use dedicated RPC endpoints with rate limits
   - Monitor API usage and costs

3. **Testing**
   - Test on Polygon Mumbai testnet first
   - Use small amounts initially
   - Monitor closely for first 24 hours

4. **Monitoring**
   - Check logs regularly: `tail -f logs/copybot.log`
   - Set up alerts for kill-switch/circuit breaker activation
   - Monitor wallet balances and positions

## 🚀 VPS Deployment

### Recommended VPS Providers
- DigitalOcean (Droplet)
- AWS EC2
- Google Cloud Compute
- Linode
- Vultr

### Deployment Steps

1. **Setup VPS** (Ubuntu 22.04 recommended)
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   
   # Install Python 3
   sudo apt install python3 python3-pip python3-venv -y
   
   # Install git
   sudo apt install git -y
   ```

2. **Clone and Setup**
   ```bash
   # Clone repository
   cd ~
   git clone https://github.com/dilanmodha09/polymk-copybot.git
   cd polymk-copybot
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Configure
   cp .env.example .env
   nano .env  # Edit configuration
   ```

3. **Run as Service (systemd)**
   ```bash
   # Create service file
   sudo nano /etc/systemd/system/polymarket-copybot.service
   ```
   
   Add:
   ```ini
   [Unit]
   Description=Polymarket Copy Trading Bot
   After=network.target
   
   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/polymk-copybot
   Environment="PATH=/home/ubuntu/polymk-copybot/venv/bin"
   ExecStart=/home/ubuntu/polymk-copybot/venv/bin/python main.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable polymarket-copybot
   sudo systemctl start polymarket-copybot
   
   # Check status
   sudo systemctl status polymarket-copybot
   
   # View logs
   sudo journalctl -u polymarket-copybot -f
   ```

4. **Setup Firewall**
   ```bash
   sudo ufw allow ssh
   sudo ufw enable
   ```

5. **Monitoring**
   ```bash
   # Check service status
   sudo systemctl status polymarket-copybot
   
   # View logs
   tail -f ~/polymk-copybot/logs/copybot.log
   
   # Check database
   sqlite3 ~/polymk-copybot/polymarket_copybot.db "SELECT COUNT(*) FROM positions WHERE is_open=1;"
   ```

## 🐛 Troubleshooting

### Common Issues

**Problem**: Bot not detecting trades
- **Solution**: Check source wallet address is correct
- Verify Polygon RPC endpoint is working
- Check API connectivity: `curl https://clob.polymarket.com`

**Problem**: Trades failing to execute
- **Solution**: Verify follower wallet has sufficient USDC
- Check private key is correct
- Ensure slippage tolerance is adequate
- Check gas price limits

**Problem**: Circuit breaker activated
- **Solution**: Check Polymarket API status
- Verify RPC endpoint is responsive
- Review error logs for specific issues
- Manually reset: Set `circuit_breaker_active=false` in database

**Problem**: Database locked errors
- **Solution**: Switch to PostgreSQL for production
- Ensure no other processes accessing database

### Logs

Check different log levels:
```bash
# View all logs
tail -f logs/copybot.log

# View only errors
grep ERROR logs/copybot.log

# View trade executions
grep "Trade executed" logs/copybot.log

# View risk control triggers
grep -E "kill-switch|circuit breaker" logs/copybot.log
```

## 📚 API Reference

### Configuration (config.py)

```python
from config import get_settings

settings = get_settings()
print(settings.source_wallet_address)
```

### Database Access

```python
from models import Database, Position

db = Database("sqlite:///polymarket_copybot.db")
session = db.get_session()

# Query positions
positions = session.query(Position).filter(Position.is_open == True).all()
```

### Manual Trade Execution

```python
from polymarket_client import PolymarketExecutor

executor = PolymarketExecutor(
    private_key="your_key",
    chain_id=137
)

# Place market order
result = executor.place_market_order(
    token_id="123",
    side="BUY",
    amount=10.0
)
```

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## ⚠️ Disclaimer

This software is provided "as is" without warranty. Trading cryptocurrencies involves substantial risk. Use at your own risk. The authors are not responsible for any financial losses.

**Important:**
- Start with small amounts
- Test thoroughly on testnet
- Monitor continuously
- Never invest more than you can afford to lose

## 📄 License

MIT License - see LICENSE file for details

## 📞 Support

- GitHub Issues: https://github.com/dilanmodha09/polymk-copybot/issues
- Documentation: This README
- Logs: Check `logs/copybot.log` for debugging

## 🔄 Version History

- **v1.0.0** (2024-01): Initial release
  - Real-time trade monitoring
  - Proportional scaling
  - Risk controls
  - Position tracking
  - State persistence

---

**Built for production use with real money. Trade responsibly.**