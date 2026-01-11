# System Architecture

## Overview

The Polymarket Copy Trading Bot is designed as a production-grade system with multiple layers of abstraction, comprehensive error handling, and robust state management.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SYSTEMS                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐              ┌───────────────────┐               │
│  │  Polymarket API  │              │  Polygon Network  │               │
│  │   (REST/WS)      │              │   (JSON-RPC)      │               │
│  └────────┬─────────┘              └─────────┬─────────┘               │
│           │                                   │                          │
└───────────┼───────────────────────────────────┼──────────────────────────┘
            │                                   │
            │                                   │
┌───────────┼───────────────────────────────────┼──────────────────────────┐
│           │         DATA INGESTION LAYER      │                          │
├───────────┼───────────────────────────────────┼──────────────────────────┤
│           ▼                                   ▼                          │
│  ┌─────────────────┐              ┌────────────────────┐               │
│  │ Polymarket      │              │  Blockchain        │               │
│  │ Client          │              │  Listener          │               │
│  │ - Get trades    │              │  - Monitor events  │               │
│  │ - Get markets   │              │  - Parse txs       │               │
│  └────────┬────────┘              └─────────┬──────────┘               │
│           │                                  │                          │
│           └────────────┬─────────────────────┘                          │
│                        │                                                 │
│                        ▼                                                 │
│           ┌──────────────────────┐                                      │
│           │   Trade Detection    │                                      │
│           │   & Normalization    │                                      │
│           └──────────┬───────────┘                                      │
└──────────────────────┼──────────────────────────────────────────────────┘
                       │
                       │
┌──────────────────────┼──────────────────────────────────────────────────┐
│                      │    CORE PROCESSING LAYER                         │
├──────────────────────┼──────────────────────────────────────────────────┤
│                      ▼                                                   │
│         ┌───────────────────────┐                                       │
│         │   Main Orchestrator   │                                       │
│         │   - Event loop        │                                       │
│         │   - State management  │                                       │
│         └──────────┬────────────┘                                       │
│                    │                                                     │
│       ┌────────────┼────────────┐                                       │
│       │            │             │                                       │
│       ▼            ▼             ▼                                       │
│  ┌────────┐  ┌─────────┐  ┌──────────┐                                │
│  │ Trade  │  │Position │  │   Risk   │                                 │
│  │ Scaler │  │Tracker  │  │Controller│                                 │
│  └───┬────┘  └────┬────┘  └─────┬────┘                                │
│      │            │              │                                       │
│      └────────────┼──────────────┘                                       │
│                   │                                                      │
│                   ▼                                                      │
│         ┌──────────────────┐                                           │
│         │  Trade Executor  │                                            │
│         │  - Validation    │                                            │
│         │  - Retry logic   │                                            │
│         │  - Error handling│                                            │
│         └────────┬─────────┘                                            │
└──────────────────┼──────────────────────────────────────────────────────┘
                   │
                   │
┌──────────────────┼──────────────────────────────────────────────────────┐
│                  │     EXECUTION LAYER                                  │
├──────────────────┼──────────────────────────────────────────────────────┤
│                  ▼                                                       │
│       ┌────────────────────┐                                           │
│       │  Polymarket        │                                            │
│       │  Executor          │                                            │
│       │  - Sign txs        │                                            │
│       │  - Submit orders   │                                            │
│       └──────────┬─────────┘                                            │
│                  │                                                       │
└──────────────────┼──────────────────────────────────────────────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │   Polymarket    │
          │   Exchange      │
          └─────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        PERSISTENCE LAYER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │                    Database (SQLite/PostgreSQL)          │          │
│  ├──────────────────────────────────────────────────────────┤          │
│  │  - source_trades       - positions                       │          │
│  │  - follower_trades     - wallet_balances                 │          │
│  │  - system_state                                          │          │
│  └──────────────────────────────────────────────────────────┘          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Data Ingestion Layer

**Polymarket Client** (`polymarket_client.py`)
- Polls Polymarket CLOB API for trade history
- Fetches market information
- Provides order book data
- Handles API rate limiting

**Blockchain Listener** (`blockchain_listener.py`)
- Monitors Polygon blockchain events
- Detects OrderFilled and OrderCancelled events
- Provides redundancy for API failures
- Real-time event notifications

### 2. Core Processing Layer

**Main Orchestrator** (`main.py`)
- Central event loop
- Coordinates all components
- Manages graceful shutdown
- Handles signal processing (SIGINT, SIGTERM)
- Background threads for balance monitoring

**Trade Scaler** (`trade_scaler.py`)
- Calculates proportional scaling: `scale = follower_balance / source_balance`
- Enforces minimum order sizes
- Applies maximum position limits
- Rounds to tick sizes
- Validates trade sizes

**Position Tracker** (`position_tracker.py`)
- Tracks open positions by market and side
- Calculates average entry prices
- Handles position updates (open, reduce, close)
- Provides position summaries
- Calculates total exposure

**Risk Controller** (`risk_controller.py`)
- Wallet utilization limits
- Daily loss monitoring (kill-switch)
- Circuit breaker for API failures
- Emergency shutdown mechanism
- State persistence across restarts

**Trade Executor** (`trade_executor.py`)
- Orchestrates trade execution
- Validates trades before execution
- Implements retry logic with exponential backoff
- Records execution results
- Updates positions after successful trades

### 3. Execution Layer

**Polymarket Executor** (`polymarket_client.py`)
- Wraps py-clob-client library
- Signs transactions with private key
- Submits market and limit orders
- Manages wallet connection
- Handles gas optimization

### 4. Persistence Layer

**Database** (`models.py`)
- SQLAlchemy ORM models
- Schema versioning support
- Transaction management
- Connection pooling
- Supports SQLite (dev) and PostgreSQL (prod)

## Data Flow

### Trade Detection and Execution

```
1. Source Trade Detection
   ├─> Polymarket API polls source wallet
   ├─> Blockchain listener monitors events
   └─> Trade normalized and stored in DB

2. Trade Validation
   ├─> Check if already processed (idempotency)
   ├─> Verify risk controls allow trading
   └─> Fetch current wallet balances

3. Trade Scaling
   ├─> Calculate scale factor
   ├─> Apply scaling to trade size
   ├─> Check minimum order size
   ├─> Apply position size limits
   └─> Check wallet utilization

4. Risk Checks
   ├─> Wallet utilization limit
   ├─> Daily loss limit
   ├─> Circuit breaker status
   └─> Emergency shutdown flag

5. Trade Execution
   ├─> Create follower trade record
   ├─> Submit order to Polymarket
   ├─> Retry on failure (exponential backoff)
   └─> Record execution result

6. Position Update
   ├─> Update position tracker
   ├─> Calculate new averages
   └─> Mark source trade as processed

7. Balance Monitoring
   ├─> Periodic balance checks
   ├─> Record in wallet_balances table
   └─> Used for daily loss calculation
```

## State Management

### Idempotency
- Each source trade has unique `trade_hash`
- `processed` flag prevents double execution
- Database transactions ensure atomicity

### Recovery
- All state persisted in database
- Risk control states restored on startup
- Positions tracked continuously
- Balance history maintained

### Error Handling
- Retry logic for transient failures
- Circuit breaker for systemic issues
- Kill-switch for excessive losses
- Graceful shutdown preserves state

## Concurrency Model

```
Main Thread
├─> Event Loop (polling source trades)
├─> Trade Processing (sequential)
└─> Graceful Shutdown Handler

Background Thread
└─> Balance Monitor (periodic checks)

Database
└─> Thread-safe sessions (SQLAlchemy)
```

## Security Considerations

1. **Private Key Management**
   - Stored in environment variables
   - Never logged or exposed
   - Used only for transaction signing

2. **Database Security**
   - Local file for SQLite
   - Connection string in .env
   - No sensitive data in logs

3. **API Security**
   - HTTPS for all API calls
   - No API keys required for reading
   - Rate limiting respected

4. **Risk Controls**
   - Multiple layers of validation
   - Automatic shutdown mechanisms
   - Manual override capabilities

## Performance Characteristics

### Latency
- **Trade Detection**: 5-10 seconds (configurable polling)
- **Scaling Calculation**: <1ms
- **Risk Validation**: <10ms
- **Order Execution**: 1-3 seconds
- **Total Latency**: 6-15 seconds from source trade to follower execution

### Throughput
- Single-threaded trade execution (by design)
- Sequential processing prevents race conditions
- Can handle 10+ trades per minute

### Resource Usage
- **Memory**: ~100MB typical
- **CPU**: <5% on modern systems
- **Network**: ~10KB/s typical
- **Disk**: Growing database (SQLite: ~1MB per 1000 trades)

## Failure Modes and Recovery

### API Failures
- **Detection**: Consecutive error counter
- **Response**: Circuit breaker activation
- **Recovery**: Manual reset after issue resolved

### Network Issues
- **Detection**: Connection timeouts
- **Response**: Retry with exponential backoff
- **Recovery**: Automatic when network restored

### Excessive Losses
- **Detection**: Daily loss calculation
- **Response**: Kill-switch activation
- **Recovery**: Manual reset (requires investigation)

### System Crashes
- **Detection**: Process monitoring (systemd)
- **Response**: Automatic restart
- **Recovery**: State restored from database

## Monitoring and Observability

### Logs
- Structured logging with levels
- File rotation (by date)
- Critical events highlighted
- Trade execution details

### Metrics (Available)
- Open positions count
- Total exposure
- Daily PnL
- Error rates
- Trading active/paused status

### Alerts (Recommended)
- Kill-switch activation
- Circuit breaker trigger
- Daily loss threshold
- API failures
- Execution errors

## Scalability

### Current Design
- Single source wallet
- Single follower wallet
- Sequential trade processing

### Future Enhancements
- Multiple source wallets
- Multiple follower wallets
- Parallel trade execution
- Advanced scaling strategies
- ML-based position sizing

## Technology Stack

- **Language**: Python 3.8+
- **Web3**: web3.py, eth-account
- **API Client**: py-clob-client (Polymarket)
- **Database**: SQLAlchemy (ORM)
- **HTTP**: requests, aiohttp
- **Retry Logic**: tenacity
- **Configuration**: pydantic-settings
- **Logging**: Python logging module

## Testing Strategy

### Unit Tests
- Trade scaling calculations
- Risk control logic
- Position tracking
- Price rounding

### Integration Tests
- Database operations
- API client mocking
- End-to-end trade flow
- Recovery scenarios

### Manual Testing
- Testnet deployment
- Small position sizes
- Various market conditions
- Shutdown/restart scenarios
