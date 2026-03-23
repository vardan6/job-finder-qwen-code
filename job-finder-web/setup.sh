#!/bin/bash
# ===========================================
# Job Finder Web App - Setup Script
# ===========================================
# This script sets up the development environment

set -e  # Exit on error

echo "🚀 Job Finder Web App - Setup Script"
echo "======================================"

# Check Python version
echo "📌 Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "   Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "   ✓ Virtual environment created"
else
    echo "   ✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📌 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
echo "   ✓ Dependencies installed"

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install
echo "   ✓ Playwright browsers installed"

# Install Playwright system dependencies (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🔧 Installing Playwright system dependencies..."
    playwright install-deps || echo "   ⚠️  Could not install system dependencies (may need sudo)"
fi

# Generate encryption key if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "🔑 Generating .env file..."
    cp .env.example .env
    
    # Generate encryption key
    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    sed -i "s/your-encryption-key-here/$ENCRYPTION_KEY/" .env
    
    # Generate secret key
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/your-secret-key-here/$SECRET_KEY/" .env
    
    echo "   ✓ .env file created with secure keys"
    echo "   ⚠️  Please review .env and configure LLM API keys if needed"
else
    echo "   ✓ .env file already exists"
fi

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/candidates
mkdir -p data/cookies
mkdir -p data/backups
mkdir -p data/archive
echo "   ✓ Data directories created"

echo ""
echo "======================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Review .env file and configure LLM API keys if needed"
echo "2. Run the app: python run.py"
echo "3. Open browser: http://localhost:8000"
echo ""
