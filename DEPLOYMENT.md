# VPS Deployment Guide

Complete guide for deploying the Polymarket Copy Trading Bot on a Virtual Private Server.

## Prerequisites

- VPS with Ubuntu 22.04 LTS (minimum 1GB RAM, 1 CPU)
- Root or sudo access
- Source wallet address to monitor
- Follower wallet with private key
- Polygon RPC endpoint (Infura/Alchemy/QuickNode)
- Basic Linux command line knowledge

## Step-by-Step Deployment

### 1. Initial VPS Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Create a non-root user (if not exists)
sudo adduser polymarket
sudo usermod -aG sudo polymarket

# Switch to the new user
su - polymarket
```

### 2. Install and Configure Bot

```bash
# Clone repository
cd ~
git clone https://github.com/dilanmodha09/polymk-copybot.git
cd polymk-copybot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Create logs directory
mkdir -p logs
```

### 3. Configuration

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

**Required settings to update:**

```bash
# YOUR WALLET ADDRESSES
SOURCE_WALLET_ADDRESS=0x...  # Source wallet to copy
FOLLOWER_WALLET_ADDRESS=0x...  # Your wallet
FOLLOWER_WALLET_PRIVATE_KEY=...  # YOUR PRIVATE KEY (KEEP SECRET!)

# RPC ENDPOINT
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# Adjust these based on your risk tolerance
MAX_POSITION_SIZE_PERCENT=20.0
MAX_WALLET_UTILIZATION_PERCENT=80.0
DAILY_LOSS_LIMIT_PERCENT=10.0

# Use PostgreSQL for production (optional but recommended)
# DATABASE_URL=postgresql://user:password@localhost:5432/polymarket_copybot
```

Save and exit (Ctrl+X, Y, Enter)

### 4. Test the Bot

```bash
# Activate virtual environment
source venv/bin/activate

# Test run
python main.py
```

You should see:
```
INFO - Initializing Polymarket Copy Trading Bot
INFO - Database initialized
INFO - Polymarket clients initialized
INFO - Starting Polymarket Copy Trading Bot
...
```

Press Ctrl+C to stop after verifying it works.

### 5. Setup as Systemd Service

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/polymarket-copybot.service
```

Add the following content (adjust paths for your username):

```ini
[Unit]
Description=Polymarket Copy Trading Bot
After=network.target

[Service]
Type=simple
User=polymarket
WorkingDirectory=/home/polymarket/polymk-copybot
Environment="PATH=/home/polymarket/polymk-copybot/venv/bin"
ExecStart=/home/polymarket/polymk-copybot/venv/bin/python /home/polymarket/polymk-copybot/main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/polymarket/polymk-copybot/logs/service.log
StandardError=append:/home/polymarket/polymk-copybot/logs/service.error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Save and exit.

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable polymarket-copybot

# Start the service
sudo systemctl start polymarket-copybot

# Check status
sudo systemctl status polymarket-copybot
```

Expected output:
```
● polymarket-copybot.service - Polymarket Copy Trading Bot
     Loaded: loaded (/etc/systemd/system/polymarket-copybot.service; enabled)
     Active: active (running) since ...
```

### 6. Configure Firewall

```bash
# Allow SSH (important - don't lock yourself out!)
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

### 7. Setup Log Rotation

Create log rotation config:

```bash
sudo nano /etc/logrotate.d/polymarket-copybot
```

Add:

```
/home/polymarket/polymk-copybot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0644 polymarket polymarket
}
```

Test log rotation:

```bash
sudo logrotate -f /etc/logrotate.d/polymarket-copybot
```

### 8. Optional: PostgreSQL Setup

For production, use PostgreSQL instead of SQLite:

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE polymarket_copybot;
CREATE USER polymarket_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE polymarket_copybot TO polymarket_user;
\q

# Update .env file
nano ~/polymk-copybot/.env
```

Change:
```bash
DATABASE_URL=postgresql://polymarket_user:your_secure_password@localhost:5432/polymarket_copybot
```

Restart the service:
```bash
sudo systemctl restart polymarket-copybot
```

## Monitoring and Management

### View Logs

```bash
# View service logs (last 50 lines)
sudo journalctl -u polymarket-copybot -n 50 --no-pager

# Follow service logs in real-time
sudo journalctl -u polymarket-copybot -f

# View application logs
tail -f ~/polymk-copybot/logs/copybot.log

# View last 100 lines
tail -n 100 ~/polymk-copybot/logs/copybot.log

# Search for errors
grep ERROR ~/polymk-copybot/logs/copybot.log

# Search for completed trades
grep "Trade executed successfully" ~/polymk-copybot/logs/copybot.log
```

### Service Management

```bash
# Check service status
sudo systemctl status polymarket-copybot

# Stop the service
sudo systemctl stop polymarket-copybot

# Start the service
sudo systemctl start polymarket-copybot

# Restart the service
sudo systemctl restart polymarket-copybot

# Disable service (stop from auto-starting)
sudo systemctl disable polymarket-copybot

# Enable service (auto-start on boot)
sudo systemctl enable polymarket-copybot
```

### Database Queries

```bash
# Access database
cd ~/polymk-copybot
source venv/bin/activate
sqlite3 polymarket_copybot.db

# Or with PostgreSQL
psql -U polymarket_user -d polymarket_copybot
```

Useful queries:

```sql
-- View open positions
SELECT market_id, outcome_side, total_shares, average_price, opened_at 
FROM positions 
WHERE is_open = 1;

-- View recent trades
SELECT id, market_id, action, size_usdc, timestamp, processed 
FROM source_trades 
ORDER BY timestamp DESC 
LIMIT 10;

-- View follower trade execution status
SELECT id, market_id, status, follower_size_usdc, executed_at 
FROM follower_trades 
ORDER BY id DESC 
LIMIT 10;

-- Check system state
SELECT * FROM system_state;

-- Check wallet balance history
SELECT wallet_address, usdc_balance, total_value, timestamp 
FROM wallet_balances 
ORDER BY timestamp DESC 
LIMIT 5;
```

### Update Bot

```bash
# Stop the service
sudo systemctl stop polymarket-copybot

# Backup database
cd ~/polymk-copybot
cp polymarket_copybot.db polymarket_copybot.db.backup

# Pull latest changes
git pull origin main

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart service
sudo systemctl start polymarket-copybot
```

## Security Hardening

### 1. Secure Private Key

```bash
# Ensure .env is not readable by others
chmod 600 ~/polymk-copybot/.env

# Verify permissions
ls -l ~/polymk-copybot/.env
# Should show: -rw------- (only owner can read/write)
```

### 2. SSH Key Authentication

```bash
# On your local machine, generate SSH key if you don't have one
ssh-keygen -t ed25519

# Copy public key to VPS
ssh-copy-id polymarket@your_vps_ip

# On VPS, disable password authentication
sudo nano /etc/ssh/sshd_config
```

Change:
```
PasswordAuthentication no
PubkeyAuthentication yes
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

### 3. Setup Fail2Ban

```bash
# Install fail2ban
sudo apt install fail2ban -y

# Start and enable
sudo systemctl start fail2ban
sudo systemctl enable fail2ban
```

### 4. Regular Security Updates

```bash
# Create update script
nano ~/update_system.sh
```

Add:
```bash
#!/bin/bash
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y
```

Make executable:
```bash
chmod +x ~/update_system.sh

# Add to crontab (weekly updates)
crontab -e
```

Add line:
```
0 3 * * 0 /home/polymarket/update_system.sh
```

## Monitoring Setup

### 1. Create Monitoring Script

```bash
nano ~/polymk-copybot/monitor.sh
```

Add:
```bash
#!/bin/bash

LOG_FILE=~/polymk-copybot/logs/copybot.log

# Check if service is running
if ! systemctl is-active --quiet polymarket-copybot; then
    echo "$(date): Service is DOWN!" | tee -a ~/polymk-copybot/logs/monitor.log
    # Add notification here (email, Telegram, etc.)
fi

# Check for kill-switch activation
if grep -q "KILL-SWITCH ACTIVATED" "$LOG_FILE"; then
    echo "$(date): KILL-SWITCH DETECTED!" | tee -a ~/polymk-copybot/logs/monitor.log
    # Add notification here
fi

# Check for circuit breaker
if grep -q "CIRCUIT BREAKER ACTIVATED" "$LOG_FILE"; then
    echo "$(date): CIRCUIT BREAKER DETECTED!" | tee -a ~/polymk-copybot/logs/monitor.log
    # Add notification here
fi

# Check for recent errors (last 5 minutes)
if tail -n 100 "$LOG_FILE" | grep -q "ERROR"; then
    echo "$(date): Recent errors detected" | tee -a ~/polymk-copybot/logs/monitor.log
fi
```

Make executable:
```bash
chmod +x ~/polymk-copybot/monitor.sh

# Add to crontab (check every 5 minutes)
crontab -e
```

Add:
```
*/5 * * * * /home/polymarket/polymk-copybot/monitor.sh
```

### 2. Simple Web Status Page (Optional)

```bash
# Install nginx
sudo apt install nginx -y

# Create status script
nano ~/polymk-copybot/status.py
```

Add simple Flask app:
```python
from flask import Flask, jsonify
from models import Database
from config import get_settings

app = Flask(__name__)

@app.route('/status')
def status():
    settings = get_settings()
    db = Database(settings.database_url)
    
    # Get basic stats
    session = db.get_session()
    # Add your status queries here
    
    return jsonify({'status': 'running'})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status polymarket-copybot

# Check logs
sudo journalctl -u polymarket-copybot -n 50

# Check file permissions
ls -l ~/polymk-copybot/.env
ls -l ~/polymk-copybot/main.py

# Verify virtual environment
source ~/polymk-copybot/venv/bin/activate
which python
python --version
```

### Database Locked

```bash
# Check for other processes
ps aux | grep main.py

# Stop all instances
sudo systemctl stop polymarket-copybot
pkill -f "python main.py"

# Restart
sudo systemctl start polymarket-copybot
```

### Out of Memory

```bash
# Check memory usage
free -h

# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### High CPU Usage

```bash
# Check CPU
top -u polymarket

# Adjust polling intervals in .env
nano ~/polymk-copybot/.env
```

Increase:
```
POLLING_INTERVAL_SECONDS=10.0
BALANCE_CHECK_INTERVAL_SECONDS=60.0
```

## Backup Strategy

### Automated Backup Script

```bash
nano ~/backup_bot.sh
```

Add:
```bash
#!/bin/bash

BACKUP_DIR=~/polymarket_backups
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp ~/polymk-copybot/polymarket_copybot.db $BACKUP_DIR/db_$DATE.db

# Backup .env file
cp ~/polymk-copybot/.env $BACKUP_DIR/env_$DATE

# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "$(date): Backup completed" >> $BACKUP_DIR/backup.log
```

Make executable and schedule:
```bash
chmod +x ~/backup_bot.sh

# Daily backup at 2 AM
crontab -e
```

Add:
```
0 2 * * * /home/polymarket/backup_bot.sh
```

## Performance Optimization

### For High-Volume Trading

1. **Use PostgreSQL** instead of SQLite
2. **Increase polling intervals** slightly to reduce API calls
3. **Add database indexes** for frequently queried fields
4. **Use connection pooling** in production

### Resource Limits

Set in service file:
```ini
[Service]
MemoryLimit=512M
CPUQuota=50%
```

## Disaster Recovery

### Quick Recovery Steps

1. **Stop service**: `sudo systemctl stop polymarket-copybot`
2. **Restore database**: `cp backup.db polymarket_copybot.db`
3. **Check configuration**: `cat .env`
4. **Start service**: `sudo systemctl start polymarket-copybot`
5. **Verify**: `sudo systemctl status polymarket-copybot`

### Emergency Procedures

**Kill-Switch Activation:**
1. Edit `.env`: `EMERGENCY_SHUTDOWN=true`
2. Restart: `sudo systemctl restart polymarket-copybot`
3. Verify all trading stopped

**Manually Close All Positions:**
- Use Polymarket UI directly
- Or write a close-all script

## Support and Maintenance

- Check logs daily for first week
- Monitor wallet balances
- Review open positions regularly
- Update bot monthly
- Backup database weekly
- Test recovery procedures

---

**Remember:** This is production software handling real money. Start small, monitor closely, and scale gradually.
