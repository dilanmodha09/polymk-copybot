# Troubleshooting Guide

Common issues and solutions for the Polymarket Copy Trading Bot.

## Installation Issues

### Problem: `pip install` fails with "No module named pip"

**Solution:**
```bash
# Upgrade pip
python3 -m pip install --upgrade pip

# Or reinstall pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
```

### Problem: Virtual environment activation fails

**Solution:**
```bash
# On Linux/Mac
source venv/bin/activate

# On Windows
venv\Scripts\activate

# If permission denied
chmod +x venv/bin/activate
```

### Problem: Dependencies fail to install

**Solution:**
```bash
# Install system dependencies first (Ubuntu/Debian)
sudo apt update
sudo apt install python3-dev build-essential libssl-dev libffi-dev

# Then retry
pip install -r requirements.txt
```

## Configuration Issues

### Problem: "Failed to load configuration"

**Solution:**
```bash
# Check .env file exists
ls -la .env

# Verify format (no spaces around =)
cat .env | grep "="

# Correct format:
SOURCE_WALLET_ADDRESS=0x123...

# Incorrect format:
SOURCE_WALLET_ADDRESS = 0x123...
```

### Problem: "Invalid private key"

**Solution:**
- Ensure private key has no `0x` prefix
- Verify it's 64 hexadecimal characters
- Check for hidden characters or spaces
- Never share your private key!

```bash
# Private key format (example - never use this!)
FOLLOWER_WALLET_PRIVATE_KEY=1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

### Problem: "Failed to connect to Polygon RPC"

**Solution:**
```bash
# Test RPC endpoint
curl -X POST \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
  YOUR_RPC_URL

# If it fails, try alternative RPCs:
# - https://polygon-rpc.com
# - https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
# - https://rpc-mainnet.matic.network
```

## Runtime Errors

### Problem: Bot detects trades but doesn't execute

**Possible causes and solutions:**

1. **Risk controls activated:**
```bash
# Check logs
grep -E "kill-switch|circuit breaker|Risk" logs/copybot.log

# Reset if needed (in database)
sqlite3 polymarket_copybot.db
UPDATE system_state SET value='false' WHERE key='kill_switch_active';
UPDATE system_state SET value='false' WHERE key='circuit_breaker_active';
.quit
```

2. **Insufficient balance:**
```bash
# Check wallet balance
grep "Follower wallet:" logs/copybot.log | tail -1

# Verify on Polymarket UI
# Ensure you have USDC, not just MATIC
```

3. **Trade size too small:**
```bash
# Check minimum order size in .env
# Default is $1 USDC
MIN_ORDER_SIZE_USDC=1.0

# Increase scale if follower wallet is much smaller
```

### Problem: "Trade execution failed" errors

**Solution:**

1. **Check slippage tolerance:**
```bash
# In .env, increase if market is volatile
SLIPPAGE_TOLERANCE_PERCENT=5.0
```

2. **Check gas price:**
```bash
# Increase max gas price if network is congested
MAX_GAS_PRICE_GWEI=1000.0
```

3. **Verify Polymarket API status:**
```bash
# Check Polymarket status
curl https://clob.polymarket.com/health

# Or check their status page
```

### Problem: Database locked errors

**Solution:**

1. **Stop all bot instances:**
```bash
# Check running processes
ps aux | grep main.py

# Kill all instances
pkill -f "python main.py"

# Or with systemd
sudo systemctl stop polymarket-copybot
```

2. **Switch to PostgreSQL (recommended for production):**
```bash
# Install PostgreSQL
sudo apt install postgresql

# Setup database (see DEPLOYMENT.md)
# Update DATABASE_URL in .env
```

### Problem: "Circuit breaker activated"

**Cause:** Too many consecutive API/execution errors

**Solution:**

1. **Check logs for underlying issue:**
```bash
grep ERROR logs/copybot.log | tail -20
```

2. **Common causes:**
   - Polymarket API down
   - Network connectivity issues
   - Invalid API responses
   - RPC endpoint problems

3. **Reset circuit breaker:**
```bash
# In database
sqlite3 polymarket_copybot.db
UPDATE system_state SET value='false' WHERE key='circuit_breaker_active';
.quit

# Restart bot
sudo systemctl restart polymarket-copybot
```

### Problem: "Kill-switch activated"

**Cause:** Daily loss exceeded threshold

**Solution:**

1. **Review trading activity:**
```bash
# Check recent trades
sqlite3 polymarket_copybot.db
SELECT * FROM follower_trades ORDER BY id DESC LIMIT 10;
.quit
```

2. **Analyze losses:**
```bash
# Check wallet balance history
sqlite3 polymarket_copybot.db
SELECT * FROM wallet_balances ORDER BY timestamp DESC LIMIT 5;
.quit
```

3. **Reset kill-switch (only if appropriate):**
```bash
sqlite3 polymarket_copybot.db
UPDATE system_state SET value='false' WHERE key='kill_switch_active';
.quit
```

**⚠️ WARNING:** Only reset kill-switch after understanding why losses occurred!

## Performance Issues

### Problem: Bot is slow to detect trades

**Solution:**

1. **Decrease polling interval:**
```bash
# In .env
POLLING_INTERVAL_SECONDS=2.0
```

2. **Use faster RPC endpoint:**
- Paid plans from Alchemy, Infura offer better performance
- Consider running your own Polygon node

### Problem: High memory usage

**Solution:**

1. **Check for log file growth:**
```bash
du -h logs/copybot.log

# If too large, rotate logs
mv logs/copybot.log logs/copybot.log.old
```

2. **Limit database size:**
```bash
# Archive old data
sqlite3 polymarket_copybot.db
DELETE FROM wallet_balances WHERE timestamp < datetime('now', '-30 days');
VACUUM;
.quit
```

### Problem: High CPU usage

**Solution:**

1. **Increase polling intervals:**
```bash
POLLING_INTERVAL_SECONDS=10.0
BALANCE_CHECK_INTERVAL_SECONDS=60.0
```

2. **Check for infinite loops in logs:**
```bash
tail -f logs/copybot.log
# Look for rapidly repeating messages
```

## Database Issues

### Problem: "No such table" error

**Solution:**
```bash
# Reinitialize database
python3 -c "from models import Database; from config import get_settings; db = Database(get_settings().database_url); db.create_tables()"
```

### Problem: Corrupted database

**Solution:**

1. **Backup first:**
```bash
cp polymarket_copybot.db polymarket_copybot.db.backup
```

2. **Try to repair:**
```bash
sqlite3 polymarket_copybot.db
.recover
.quit
```

3. **If repair fails, start fresh:**
```bash
mv polymarket_copybot.db polymarket_copybot.db.corrupted
# Database will be recreated on next run
```

## Network Issues

### Problem: Timeout errors

**Solution:**

1. **Test network connectivity:**
```bash
# Test Polymarket API
curl -v https://clob.polymarket.com

# Test Polygon RPC
curl -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' \
  YOUR_RPC_URL
```

2. **Increase retry attempts:**
```bash
# In .env
RETRY_ATTEMPTS=5
RETRY_DELAY_SECONDS=5.0
```

3. **Check firewall:**
```bash
# Ensure HTTPS is allowed
sudo ufw status
```

## Debugging Tips

### Enable debug logging

```bash
# In .env
LOG_LEVEL=DEBUG

# Restart bot
sudo systemctl restart polymarket-copybot

# Watch debug logs
tail -f logs/copybot.log
```

### Monitor in real-time

```bash
# Follow all logs
tail -f logs/copybot.log

# Filter for errors only
tail -f logs/copybot.log | grep ERROR

# Filter for trades
tail -f logs/copybot.log | grep -E "Trade|trade"

# Filter for risk controls
tail -f logs/copybot.log | grep -E "kill-switch|circuit breaker|Risk"
```

### Check database state

```bash
sqlite3 polymarket_copybot.db

-- Check open positions
SELECT market_id, outcome_side, total_shares, is_open FROM positions WHERE is_open=1;

-- Check recent trades
SELECT id, market_id, status FROM follower_trades ORDER BY id DESC LIMIT 10;

-- Check system state
SELECT * FROM system_state;

-- Check last balance update
SELECT * FROM wallet_balances ORDER BY timestamp DESC LIMIT 1;

.quit
```

### Test individual components

```python
# Test configuration
python3 -c "from config import get_settings; s = get_settings(); print(f'Source: {s.source_wallet_address}')"

# Test database
python3 -c "from models import Database; from config import get_settings; db = Database(get_settings().database_url); print('Database OK')"

# Test Polymarket client
python3 -c "from polymarket_client import PolymarketClient; from config import get_settings; s = get_settings(); client = PolymarketClient(s.polymarket_api_url); print('Client OK')"
```

## Getting Help

If you're still experiencing issues:

1. **Check logs thoroughly:**
```bash
# Get last 100 lines
tail -n 100 logs/copybot.log

# Search for specific errors
grep -A 5 "ERROR" logs/copybot.log
```

2. **Gather system information:**
```bash
# Python version
python3 --version

# OS information
uname -a
cat /etc/os-release

# Memory and CPU
free -h
top -bn1 | head -20
```

3. **Create minimal reproduction:**
- Note exact error message
- List steps to reproduce
- Include relevant log excerpts
- Describe expected vs actual behavior

4. **Open GitHub issue:**
- Include system information
- Attach logs (remove private keys!)
- Describe troubleshooting steps already tried

## Common Error Messages

### "ModuleNotFoundError: No module named 'X'"
**Solution:** `pip install X` or `pip install -r requirements.txt`

### "PermissionError: [Errno 13]"
**Solution:** Check file permissions with `ls -l`, use `chmod` to fix

### "ConnectionRefusedError"
**Solution:** Service not running or firewall blocking

### "sqlite3.OperationalError: database is locked"
**Solution:** Another process is using the database, stop it

### "Invalid JSON response"
**Solution:** API endpoint issue, check network and API status

### "Insufficient funds"
**Solution:** Add USDC to follower wallet

## Prevention

### Best practices to avoid issues:

1. **Start small:** Test with minimal amounts first
2. **Monitor closely:** Check logs daily initially
3. **Regular backups:** Automate database backups
4. **Keep updated:** Pull latest changes regularly
5. **Use PostgreSQL:** For production deployments
6. **Set up alerts:** Monitor for kill-switch/circuit breaker
7. **Test recovery:** Practice restore procedures
8. **Document changes:** Keep notes on configuration tweaks

---

**Still stuck?** Open an issue on GitHub with detailed information about your problem.
