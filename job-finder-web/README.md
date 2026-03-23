# Job Finder Web App

Multi-candidate job search automation with AI-powered analysis.

## Features

- ✅ **Multi-Candidate Support** - Manage job searches for multiple people
- ✅ **AI-Powered Analysis** - Automatic job scoring and matching
- ✅ **Remote Work Detection** - AI analyzes remote work compatibility
- ✅ **Conservative Scraping** - Ultra-safe rate limiting to protect accounts
- ✅ **Web UI** - Clean, modern interface with HTMX + Bootstrap
- ✅ **Local Storage** - All data stored locally with encryption
- ✅ **Docker-Ready** - Easy deployment when ready

## Quick Start

### 1. Run Setup Script

**Linux/macOS:**
```bash
cd job-finder-web
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
cd job-finder-web
setup.bat
```

### 2. Configure (Optional)

Edit `.env` file to configure:
- LLM API keys (OpenRouter, Anthropic, etc.)
- Ollama URL (if using local Ollama)
- App settings (port, debug mode)

### 3. Start Application

```bash
python run.py
```

### 4. Open Browser

Navigate to: **http://localhost:9002**

## Project Structure

```
job-finder-web/
├── backend/              # FastAPI application
│   ├── routes/          # API endpoints
│   ├── models/          # Database models
│   ├── services/        # Business logic
│   └── utils/           # Utilities
├── frontend/            # HTML templates + static files
│   ├── templates/
│   └── static/
├── data/                # Database + files (auto-created)
├── logs/                # Application logs (auto-created)
├── requirements.txt     # Python dependencies
├── setup.sh / setup.bat # Setup scripts
└── run.py              # Entry point
```

## Development Phases

### Phase 1: Core Foundation (Current)
- ✅ Project skeleton
- ✅ Candidate management (CRUD)
- ✅ Database setup
- ✅ LLM test interface
- ✅ Health check
- ⏳ Base template + navigation
- ⏳ Flash messages
- ⏳ Logging

### Phase 2: Candidate Profiles (Next)
- Platform accounts
- Job titles & skills
- Search queries
- Preferences

### Phase 3: Job Search Engine
- Playwright scraping
- Rate limiting
- AI analysis
- Deduplication

### Phase 4: Job Management
- Dashboard
- Application tracking
- Export/Reports

### Phase 5: Polish & Deploy
- Testing
- Docker
- Documentation

## Technology Stack

- **Backend:** FastAPI (Python, async)
- **Frontend:** HTMX + Alpine.js + Bootstrap 5
- **Database:** SQLite
- **Browser Automation:** Playwright
- **AI/LLM:** LiteLLM (Ollama, OpenRouter, etc.)
- **Security:** Fernet encryption, Bleach (XSS protection)

## Requirements

- Python 3.11+
- 2GB RAM minimum
- 500MB disk space
- Internet connection (for job searches)

## Security Notes

- Encryption key is generated on first run
- API keys are stored encrypted
- Cookies are encrypted at rest
- All data stored locally

## License

MIT License

## Support

For issues or questions, please check the documentation or create an issue.
