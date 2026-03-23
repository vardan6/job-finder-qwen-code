# Job Finder Web App — Project Context

**User:** Vardan Arakelyan  
**Location:** Armenia  
**Goal:** Find fully remote jobs in US/EU/Canada while working from Armenia  
**Project Status:** Phase 1 COMPLETE (Core Foundation)  
**Last Updated:** March 23, 2026

---

## 📋 Project Overview

A **web-based job search automation application** that:

- Supports **multiple candidates** (you, brother, friends) with isolated data per candidate
- Scrapes job platforms (**LinkedIn, Glassdoor, Indeed**) with ultra-conservative anti-detection
- Uses **AI** (Ollama/OpenRouter) to analyze and score job postings for remote-work compatibility
- Provides an **interactive web UI** for managing candidates, jobs, and applications
- Stores all data **locally** with encryption (Fernet for cookies/API keys)
- Is **Docker-ready** for future deployment

### Key Constraints

| Constraint | Decision |
|------------|----------|
| **Budget** | $0 (free services only) |
| **Accounts** | 1 LinkedIn, 1 Glassdoor (your own accounts) |
| **Risk Tolerance** | Very low (protect accounts at all costs) |
| **Deployment** | Local-first, Docker-ready for later |
| **Architecture** | Backend does everything, Frontend is GUI only |

---

## 🎯 Current Development Status

### ✅ Phase 1: Core Foundation — COMPLETE

All 11 tasks completed and tested:

- ✅ Project skeleton (FastAPI + HTMX structure)
- ✅ Base template with navigation and flash messages
- ✅ Database models (Candidate, Job, LLMProvider, Supporting models)
- ✅ Static files (HTMX, Alpine.js, Bootstrap 5)
- ✅ Candidate CRUD routes and UI
- ✅ Flash message system
- ✅ Logging (file + console)
- ✅ LLM configuration UI with test interface
- ✅ Health check endpoint (`/api/health`)
- ✅ Custom error pages (404, 500)

**Tested & Working:**
- Application starts without configuration (auto-generates encryption key)
- Create, view, edit, delete candidates
- Dashboard shows live stats from database
- LLM settings page for configuring Ollama, OpenRouter, Anthropic, OpenAI
- Health check verifies database connectivity

### 📋 Phase 2: Candidate Profiles — NEXT

Pending implementation:
- Platform accounts (encrypted cookie storage per candidate)
- Candidate profile (experience, location, timezone)
- Job titles (per-candidate preferred titles, priority ordering)
- Skills (required/preferred skills per candidate)
- Search queries (per-candidate query management)
- Profile UI (settings pages for all candidate config)

### Future Phases

- **Phase 3:** Job Search Engine (Playwright scraping, rate limiting, AI analysis)
- **Phase 4:** Job Management (dashboard, application tracking, export/reports)
- **Phase 5:** Polish & Deploy (testing, Docker, documentation)

---

## 🏗️ Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI (Python, async) | REST API, routing, templates |
| **Frontend** | HTMX + Alpine.js + Bootstrap 5 | Interactive UI without build step |
| **Database** | SQLite | Single-file local storage |
| **Browser Automation** | Playwright (async) | Job platform scraping |
| **AI/LLM** | LiteLLM | Unified API for Ollama, OpenRouter, Anthropic, OpenAI |
| **Security** | Cryptography (Fernet) + Bleach | Encryption + XSS protection |
| **Validation** | Pydantic | Input validation, type safety |

---

## 📁 Project Structure

```
job-finder-qwen-code/
├── QWEN.md                    # This file — project context
├── PROJECT_PLAN.md            # Complete 5-phase implementation plan
├── linkedin-profile.md        # User's professional profile
├── prefered-job-titles.md     # Target job titles (7 roles)
├── my-role-claude-gold.md     # Detailed role description at Silvaco
├── job-search-platforms.md    # Job platform research (12 platforms)
├── cover-letter.md            # Cover letter templates
├── tmp.md                     # Initial project notes
│
└── job-finder-web/            # Main application directory
    ├── backend/
    │   ├── app.py             # FastAPI application entry point
    │   ├── config.py          # Environment variables, auto-generates ENCRYPTION_KEY
    │   ├── database.py        # SQLite configuration
    │   ├── security.py        # Encryption/decryption utilities
    │   ├── logging_config.py  # File + console logging
    │   ├── routes/
    │   │   ├── candidates.py  # Candidate CRUD endpoints
    │   │   ├── health.py      # Health check endpoint
    │   │   ├── llm_test.py    # LLM test endpoint
    │   │   └── llm_config.py  # LLM provider configuration UI
    │   ├── models/
    │   │   ├── candidate.py   # Candidate model
    │   │   ├── job.py         # Job and JobApplication models
    │   │   ├── llm_provider.py # LLM provider model
    │   │   ├── supporting.py  # JobTitle, Skill, Preferences models
    │   │   └── __init__.py    # All model exports
    │   ├── scrapers/          # (Phase 3) LinkedIn, Glassdoor scrapers
    │   ├── services/          # (Phase 3+) Business logic
    │   ├── validators/        # (Phase 3+) Input validation
    │   └── utils/             # (Phase 3+) Utilities
    ├── frontend/
    │   ├── templates/
    │   │   ├── base.html      # Base template with navigation
    │   │   ├── dashboard.html # Home page with stats
    │   │   ├── candidates/
    │   │   │   ├── list.html  # Candidate list
    │   │   │   ├── edit.html  # Create/edit form
    │   │   │   └── detail.html # Candidate detail view
    │   │   ├── jobs/
    │   │   │   └── list.html  # Job list (placeholder)
    │   │   ├── settings/
    │   │   │   ├── index.html # Settings index (redirects to LLM)
    │   │   │   ├── llm.html   # LLM configuration UI
    │   │   │   └── llm_test_result.html # Test result template
    │   │   └── errors/
    │   │       ├── 404.html   # Not found page
    │   │       └── 500.html   # Error page
    │   └── static/
    │       ├── css/style.css  # Custom styles
    │       └── js/app.js      # JavaScript utilities
    ├── data/                  # Auto-created at runtime
    │   ├── jobs.db            # SQLite database
    │   ├── candidates/        # Per-candidate folders
    │   ├── cookies/           # Encrypted session cookies
    │   └── backups/           # Database backups
    ├── logs/                  # Auto-created
    │   └── app.log            # Application logs
    ├── requirements.txt       # Python dependencies
    ├── setup.sh / setup.bat   # Setup scripts
    ├── run.py                 # Entry point
    └── .env.example           # Environment template
```

---

## 🚀 Building and Running

### Quick Start

```bash
# Navigate to project
cd /mnt/c/Users/vardana/Documents/Proj/job-finder-qwen-code/job-finder-web

# Run setup (first time only)
./setup.sh          # Linux/macOS
setup.bat           # Windows

# Start the application
python run.py

# Open browser
# Navigate to: http://localhost:9002
```

### Setup Script Does:
1. Creates virtual environment
2. Installs dependencies from `requirements.txt`
3. Installs Playwright browsers
4. Generates `.env` with secure encryption key
5. Creates data directories

### Manual Setup (if needed)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Generate encryption key (if .env missing)
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# Start application
python run.py
```

### Available Commands

| Command | Description |
|---------|-------------|
| `./setup.sh` | Full setup script (Linux/macOS) |
| `setup.bat` | Full setup script (Windows) |
| `python run.py` | Start the web application |
| `playwright install` | Install browser binaries |
| `pip install -r requirements.txt` | Install Python dependencies |

---

## 🧪 Testing

### Manual Testing

1. **Health Check:**
   ```bash
   curl http://localhost:9002/api/health
   # Expected: {"status":"ok","database":"connected","message":"Job Finder Web App is running"}
   ```

2. **Dashboard:**
   ```bash
   curl http://localhost:9002/
   # Should show candidate count, quick actions
   ```

3. **Candidates:**
   ```bash
   curl http://localhost:9002/candidates/
   # Should list all candidates
   ```

4. **LLM Settings:**
   ```bash
   curl http://localhost:9002/settings/llm
   # Should show LLM provider configuration UI
   ```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard with stats |
| `/candidates/` | GET | List candidates |
| `/candidates/new` | GET | New candidate form |
| `/candidates/` | POST | Create candidate |
| `/candidates/{id}` | GET | View candidate |
| `/candidates/{id}/edit` | GET | Edit candidate form |
| `/candidates/{id}` | POST | Update candidate |
| `/candidates/{id}/delete` | POST | Delete candidate |
| `/api/health` | GET | Health check |
| `/api/llm/test` | POST | Test LLM connection |
| `/settings/llm` | GET | LLM configuration UI |
| `/settings/` | POST | Save LLM provider |
| `/settings/delete` | POST | Delete LLM provider |
| `/settings/test` | POST | Test LLM provider |

---

## 📝 Development Conventions

### Coding Style

- **Python:** Follow PEP 8, use type hints where practical
- **Frontend:** Inline styles minimal, prefer Bootstrap classes
- **Templates:** Jinja2, extend `base.html` for consistency
- **Routes:** Use `APIRouter`, lazy-load heavy imports

### Architecture Principles

- **Frontend = GUI Only:** All logic in backend
- **Backend Does Everything:** Scraping, AI, data processing
- **Local-First:** All data stored locally, encrypted at rest
- **Lazy Imports:** Heavy modules (LiteLLM) imported on-demand

### Security Practices

- **Encryption:** Fernet for API keys, cookies
- **XSS Protection:** Bleach for user input sanitization
- **Input Validation:** Pydantic validators on all forms
- **SQL Injection Prevention:** SQLAlchemy ORM, parameterized queries

### Database Notes

- SQLite for simplicity (single file, no setup)
- `func.now()` for timestamps (SQLAlchemy 2.0 compatible)
- Foreign keys with `ON DELETE CASCADE`
- Soft deletes for candidates (`is_active` flag)

---

## 👤 User Profile Summary

### Professional Background

**Current Role:** Software Engineer at Silvaco Inc. (2020–Present)  
**Previous:** Synopsys Armenia (2008–2019) — R&D Engineer → Senior QA → Lead QA  
**Total Experience:** 18+ years in EDA, VLSI, QA Automation

### Key Skills

- **Languages:** Python, Bash, Perl, Tcl-Tk, C
- **Tools:** FastAPI, Flask, Playwright, Git, GitHub Actions
- **Domains:** EDA (SmartSpice), VLSI, CI/CD, Test Automation
- **Analysis:** Valgrind, Sanitizers (ASAN/UBSAN), Code Coverage

### Target Job Titles

1. Staff SDET / Staff Software Engineer in Test
2. Principal SDET / Principal Software Development Engineer in Test
3. Principal EDA Design Automation Engineer
4. Staff CAD Engineer (EDA Tools / Workflow Optimization)
5. Lead SDET – EDA/Semiconductor
6. Senior EDA Tools Engineer (Test Infrastructure)
7. Test Infrastructure Architect / QA Automation Architect

### Job Preferences

- **Location:** Fully Remote (working from Armenia)
- **Regions:** US, EU, Canada
- **Languages:** English (primary), Russian (secondary)
- **Timezone:** Asia/Yerevan (UTC+4)

---

## 📚 Key Reference Documents

| File | Purpose |
|------|---------|
| `PROJECT_PLAN.md` | Complete 5-phase implementation plan with task breakdown |
| `linkedin-profile.md` | User's full professional profile, experience, skills |
| `prefered-job-titles.md` | 7 target job titles with descriptions |
| `my-role-claude-gold.md` | Detailed role description at Silvaco |
| `job-search-platforms.md` | Research on 12 job platforms (LinkedIn, Glassdoor, etc.) |
| `cover-letter.md` | Cover letter templates (initial, basic, short versions) |

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Security (auto-generated on first run)
ENCRYPTION_KEY=your-key-here
SECRET_KEY=your-secret-key

# LLM (optional)
OLLAMA_URL=http://localhost:11434
OPENROUTER_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEFAULT_LLM_MODEL=ollama/llama3

# App (optional)
DEBUG=true
HOST=0.0.0.0
PORT=9002
DEFAULT_TIMEZONE=Asia/Yerevan
```

### Default Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `PORT` | 9002 | Web server port |
| `HOST` | 0.0.0.0 | Bind address |
| `DEBUG` | true | Enable auto-reload |
| `DEFAULT_TIMEZONE` | Asia/Yerevan | Default for new candidates |
| `PLAYWRIGHT_HEADLESS` | false | Show browser during scraping |

---

## 🐛 Known Issues & Notes

### Fixed Issues (Phase 1 Bug Fixes)

1. ✅ Auto-generates `ENCRYPTION_KEY` on first run (no manual setup needed)
2. ✅ Handles missing encryption key gracefully with clear error
3. ✅ Fixed missing imports (`Session`, `Depends`) in `app.py`
4. ✅ Updated deprecated SQLAlchemy import (`declarative_base`)
5. ✅ Replaced `datetime.utcnow` with `func.now()` (Python 3.12 compatible)
6. ✅ Fixed 500 error handler signature for FastAPI
7. ✅ Created LLM configuration UI (was "Coming Soon")
8. ✅ All models properly imported in `__init__.py`

### Current Limitations

- Job search/scraping not yet implemented (Phase 3)
- Candidate profiles incomplete (Phase 2)
- No application tracking yet (Phase 4)
- Docker deployment not configured (Phase 5)

---

## 🎯 Next Steps for Development

### Immediate (Continue Phase 2)

1. Implement candidate profile editing (experience, skills)
2. Add job title management per candidate
3. Add skill management (required/preferred)
4. Create search query configuration
5. Build candidate preferences UI

### Short Term (Phase 3)

1. Implement LinkedIn scraper with anti-detection
2. Add Glassdoor scraper
3. Build rate limiter (SQLite-backed)
4. Create AI job analysis service
5. Implement job deduplication

---

## 📞 Quick Reference

**Start Development:**
```bash
cd /mnt/c/Users/vardana/Documents/Proj/job-finder-qwen-code/job-finder-web
source venv/bin/activate
python run.py
```

**Check Status:**
```bash
curl http://localhost:9002/api/health
```

**View Logs:**
```bash
tail -f logs/app.log
```

---

**END OF PROJECT CONTEXT**
