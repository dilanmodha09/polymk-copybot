#!/bin/bash

# Quick Start Script for Polymarket Copy Trading Bot
# This script helps set up the bot for first-time users

set -e  # Exit on any error

echo "================================================"
echo "  Polymarket Copy Trading Bot - Quick Start"
echo "================================================"
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    echo "Please install Python 3.8 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet
echo "Dependencies installed."
echo ""

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env configuration file..."
    cp .env.example .env
    echo ".env file created from template."
    echo ""
    echo "⚠️  IMPORTANT: You must edit .env with your configuration!"
    echo "   Required settings:"
    echo "   - SOURCE_WALLET_ADDRESS"
    echo "   - FOLLOWER_WALLET_ADDRESS"
    echo "   - FOLLOWER_WALLET_PRIVATE_KEY"
    echo "   - POLYGON_RPC_URL"
    echo ""
    read -p "Press Enter to open .env in nano editor (or Ctrl+C to exit and edit manually)..."
    nano .env
else
    echo ".env file already exists."
fi
echo ""

# Create logs directory
if [ ! -d "logs" ]; then
    echo "Creating logs directory..."
    mkdir -p logs
    echo "Logs directory created."
else
    echo "Logs directory already exists."
fi
echo ""

# Verify configuration
echo "Verifying configuration..."
if grep -q "your_private_key_here" .env; then
    echo ""
    echo "⚠️  WARNING: .env file still contains placeholder values!"
    echo "   Please edit .env with your actual configuration before running."
    echo ""
    read -p "Do you want to edit .env now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    fi
else
    echo "Configuration appears to be set up."
fi
echo ""

# Test import
echo "Testing bot initialization..."
python3 -c "from config import get_settings; print('✓ Configuration loaded successfully')" 2>/dev/null || {
    echo "⚠️  Warning: Configuration test failed. Please check your .env file."
}
echo ""

echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Ensure your .env file is properly configured"
echo "2. Make sure you have USDC in your follower wallet"
echo "3. Start the bot:"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "4. Monitor logs in real-time:"
echo "   tail -f logs/copybot.log"
echo ""
echo "For deployment on VPS, see DEPLOYMENT.md"
echo ""
echo "⚠️  SECURITY REMINDER:"
echo "   - Never commit .env file to version control"
echo "   - Keep your private key secure"
echo "   - Start with small amounts for testing"
echo ""
echo "================================================"
