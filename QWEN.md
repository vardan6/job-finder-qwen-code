# Job Finder Web App — Project Context

**User:** Vardan Arakelyan
**Location:** Armenia
**Goal:** Find fully remote jobs in US/EU/Canada while working from Armenia
**Project Status:** 
- ✅ Phase 1: Core Foundation — COMPLETE
- ✅ Phase 2: Candidate Profiles — COMPLETE  
- ✅ LLM Configuration Redesign — COMPLETE
- ⏳ Phase 3: Job Search Engine — NEXT

**Last Updated:** March 24, 2026

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

### ✅ Phase 2: Candidate Profiles — COMPLETE

All Phase 2 tasks completed:

- ✅ **Skills Management** - Modal-based UI with search, filter, bulk actions
- ✅ **AI Skill Extraction** - Parse skills from uploaded documents
- ✅ **Enable/Disable Skills** - Toggle skills for search matching
- ✅ **Search Preferences** - Min scores, remote-only, experience levels
- ✅ **Platform Accounts** - Encrypted cookie storage for LinkedIn/Glassdoor

**Tested & Working:**
- Skills modal with search/filter functionality
- AI parsing of skills from documents
- Bulk enable/disable/delete operations
- Preferences page with sliders and checkboxes
- Platform accounts with cookie import

### ✅ LLM Configuration Redesign — COMPLETE

**New Features:**
- ✅ **Inline Model Selectors** - Dropdown next to AI action buttons
- ✅ **Reusable Model Selector Widget** - `components/model_selector.html`
- ✅ **Backend API Endpoints** - `/api/llm/models`, `/api/llm/function/{name}/model`
- ✅ **Code Cleanup** - Removed duplicate functions (DRY principle restored)
- ✅ **Enhanced Navigation** - Links between provider config and function mappings

**Files Changed:**
- Backend: 7 files (removed duplicates, added API endpoints, updated imports)
- Frontend: 4 files (new widget component, added inline selectors)

**How to Use:**
1. Visit candidate page → See model selector next to "Parse from Files"
2. Change model → Auto-saves to database
3. Click parse → Uses selected model
4. Central config still available at `/settings/functions`

**Documentation:**
- See `IMPLEMENTATION_SUMMARY.md` for complete details
- See `LLM_REDESIGN_PLAN.md` for original plan
- See `CODE_REVIEW_CLEANUP.md` for cleanup analysis

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

### Fixed Issues (Phase 2 - LLM Integration)

9. ✅ **NVIDIA NIM Integration** - Fixed after deep research
   - Model format: `nvidia_nim/meta/llama3-70b-instruct` (NOT `nvidia/...`)
   - API base: `https://integrate.api.nvidia.com/v1/` (with trailing slash)
   - All routes updated: `chat.py`, `llm_config.py`, `llm_test.py`
   - Tested & working models:
     - `meta/llama3-70b-instruct` (free tier)
     - `meta/llama3-8b-instruct` (free tier)
     - `qwen/qwen3-coder-480b-a35b-instruct` (Continue.dev)
     - `meta/llama-3.1-405b-instruct` (requires credits)
10. ✅ **AI Chat Page** - Shows provider names in model dropdown `[NVIDIA] model-name`
11. ✅ **Provider Detection** - Smart detection for `nvidia_nim/`, `ollama/`, etc.

### Fixed Issues (Phase 2 - Document Upload & AI Chat)

12. ✅ **NVIDIA API Key Decryption** - Fixed in `chat.py`, `document_parser.py`
    - Changed `decrypt_token` → `decrypt_data` for consistency
13. ✅ **NVIDIA Model Prefix for LiteLLM** - Added proper prefixes
    - `nvidia/` for NVIDIA, `openrouter/` for OpenRouter, etc.
    - Fixed in: `chat.py`, `document_parser.py`, `llm_test.py`
14. ✅ **NVIDIA API Base URL** - Fixed `/v1/v1/` double path issue
    - LiteLLM appends `/v1`, so strip it from config
    - Code: `if api_base.endswith('/v1'): api_base = api_base[:-3]`
15. ✅ **Parse from Files Button Error** - Fixed March 24 session
    - Profile docs now use cached parsed data (faster, no format mismatch)
    - HTMX timeout extended to 180s
    - Added timeout and error handlers
    - Fixed in: `job_title_parser.py`, `detail.html`

### Current Limitations

- Job search/scraping not yet implemented (Phase 3)
- Candidate profiles incomplete (Phase 2)
- No application tracking yet (Phase 4)
- Docker deployment not configured (Phase 5)

---

## 🔐 Security Notes

**Sensitive Files (NEVER commit to GitHub):**
- `.env` - Contains `ENCRYPTION_KEY`, `SECRET_KEY`, API keys
- `data/jobs.db` - Encrypted API keys, user data
- `data/cookies/` - Browser session cookies
- `logs/app.log` - May contain debug info

**All above files are in `.gitignore` ✅**

---

## 🎯 Next Steps for Development

### Immediate (Continue Phase 2)

1. ✅ **Parse from Files** - FIXED and tested (March 24)
2. [ ] Test NVIDIA Integration - Verify AI Chat works with NVIDIA models
3. [ ] Test Document Upload - Upload `prefered-job-titles.md` and verify extraction
4. [ ] Test All Providers - OpenRouter, Anthropic, OpenAI (if API keys configured)
5. [ ] Candidate experience section (manual entry + AI extraction)
6. [ ] Candidate skills management (required/preferred)
7. [ ] Candidate platform accounts (LinkedIn, Glassdoor cookies)
8. [ ] Candidate timezone & location preferences
9. [ ] Search query management per candidate

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

**Test LLM Model Selection API:**
```bash
# Get all available models
curl http://localhost:9002/api/llm/models

# Get current model for job_title_parser
curl http://localhost:9002/api/llm/function/job_title_parser/model

# Set model for skill_extractor (replace 5 with actual model ID)
curl -X POST http://localhost:9002/api/llm/function/skill_extractor/model \
  -H "Content-Type: application/json" \
  -d '{"model_id": 5}'
```

**Generate New Keys (if needed):**
```bash
# ENCRYPTION_KEY (for data encryption)
venv/bin/python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# SECRET_KEY (for sessions)
venv/bin/python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```

**NVIDIA NIM Configuration:**
- Model format: `nvidia_nim/meta/llama3-70b-instruct`
- API Base: `https://integrate.api.nvidia.com/v1/`
- Free models: `meta/llama3-70b-instruct`, `meta/llama3-8b-instruct`
- Continue.dev models: `qwen/qwen3-coder-480b-a35b-instruct`

**Parse from Files (AI Job Title Extraction):**
- Button location: Candidate Detail page → "Preferred Job Titles (AI Extracted)" section
- Extracts from: `job_titles`, `profile`, `resume` documents
- Uses cached parsed data for profile docs (faster)
- Timeout: 180 seconds (HTMX)
- Expected time: 30-90 seconds depending on LLM

---

**END OF PROJECT CONTEXT**
