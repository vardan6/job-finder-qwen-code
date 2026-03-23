@echo off
REM ===========================================
REM Job Finder Web App - Setup Script (Windows)
REM ===========================================

echo 🚀 Job Finder Web App - Setup Script
echo ======================================

REM Check Python version
echo 📌 Checking Python version...
python --version
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    echo    ✓ Virtual environment created
) else (
    echo    ✓ Virtual environment already exists
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo 📌 Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt
echo    ✓ Dependencies installed

REM Install Playwright browsers
echo 🌐 Installing Playwright browsers...
playwright install
echo    ✓ Playwright browsers installed

REM Generate encryption key if .env doesn't exist
if not exist ".env" (
    echo 🔑 Generating .env file...
    copy .env.example .env
    
    REM Generate encryption key
    for /f "delims=" %%i in ('python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"') do set ENCRYPTION_KEY=%%i
    powershell -Command "(Get-Content .env) -replace 'your-encryption-key-here', '%ENCRYPTION_KEY%' | Set-Content .env"
    
    REM Generate secret key
    for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set SECRET_KEY=%%i
    powershell -Command "(Get-Content .env) -replace 'your-secret-key-here', '%SECRET_KEY%' | Set-Content .env"
    
    echo    ✓ .env file created with secure keys
    echo    ⚠️  Please review .env and configure LLM API keys if needed
) else (
    echo    ✓ .env file already exists
)

REM Create data directories
echo 📁 Creating data directories...
if not exist "data\candidates" mkdir data\candidates
if not exist "data\cookies" mkdir data\cookies
if not exist "data\backups" mkdir data\backups
if not exist "data\archive" mkdir data\archive
echo    ✓ Data directories created

echo.
echo ======================================
echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Review .env file and configure LLM API keys if needed
echo 2. Run the app: python run.py
echo 3. Open browser: http://localhost:8000
echo.
