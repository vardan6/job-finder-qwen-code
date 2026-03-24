# Job Finder Web App - Complete Project Plan

**Version:** 7.0 (Final)  
**Last Updated:** March 23, 2025  
**User:** Vardan Arakelyan  
**Location:** Armenia  
**Goal:** Remote job search automation for multiple candidates  

---

## 📋 Executive Summary

### What We're Building

A **web-based job search application** that:

- ✅ Supports **multiple candidates** (you, brother, friends) - each with isolated data
- ✅ Scrapes job platforms (**LinkedIn, Glassdoor**) with ultra-conservative anti-detection
- ✅ Uses **AI** (Ollama/OpenRouter) to analyze and score jobs
- ✅ Provides **interactive web UI** for managing candidates and jobs
- ✅ Stores all data **locally** with encryption
- ✅ Is **Docker-ready** for future deployment

### Key Constraints

| Constraint | Decision |
|------------|----------|
| **Budget** | $0 (free services only) |
| **Accounts** | 1 LinkedIn, 1 Glassdoor (your own) |
| **Risk Tolerance** | Very low (protect accounts at all costs) |
| **Deployment** | Local-first, Docker-ready for later |
| **Architecture** | Backend does everything, Frontend is GUI only |

### Estimated Development Time

**Total:** 38-58 hours (revised from 40-60)

- **AI Development Time:** 38-58 hours (writing code)
- **Your Time:** 10-20 hours (reviewing, testing, feedback)
- **Spread:** Multiple sessions over days/weeks

**Phase Breakdown:**
- Phase 1: 13 hours (Core Foundation) - Hours 1-13
- Phase 2: 9 hours (Candidate Profiles) - Hours 14-22
- Phase 3: 19 hours (Job Search Engine) - Hours 23-41
- Phase 4: 9 hours (Job Management) - Hours 42-50
- Phase 5: 5+ hours (Polish & Deploy) - Hours 51-55+

---

## 🎯 Phased Implementation Strategy

### ✅ Phase 1: Core Foundation (Hours 1-13) — COMPLETE

**Goal:** Working web app with candidate management

| Phase | Task | Deliverable | Status |
|-------|------|-------------|--------|
| 1.1 | Project Skeleton | FastAPI + HTMX structure, requirements.txt, .env.example, setup script | ✅ COMPLETE |
| 1.2 | Base Template | base.html, navigation, flash message system, error handling | ✅ COMPLETE |
| 1.3 | Database Models | Candidate, Job, LLMProvider, Supporting models | ✅ COMPLETE |
| 1.4 | Static Files | HTMX, Alpine.js, basic CSS, favicon | ✅ COMPLETE |
| 1.5 | Candidate Routes | CRUD endpoints with Pydantic validation | ✅ COMPLETE |
| 1.6 | Candidate UI | Forms with error display, HTMX interactions | ✅ COMPLETE |
| 1.7 | Flash Messages | User feedback system (success/error messages) | ✅ COMPLETE |
| 1.8 | Logging | File + console logging, debug support | ✅ COMPLETE |
| 1.9 | LLM Config + Test | API keys, encrypted storage, test chat interface | ✅ COMPLETE |
| 1.10 | Health Check | /api/health endpoint, smoke test script | ✅ COMPLETE |
| 1.11 | Error Pages | Custom 404, 500 pages (basic) | ✅ COMPLETE |

**End of Phase 1:**
- ✅ Working web app with navigation
- ✅ Can create/edit/delete candidates with feedback
- ✅ LLM providers configured and testable
- ✅ Logging configured for debugging
- ✅ Health check verifies everything works
- ✅ AI Chat interface working

---

### ✅ Phase 2: Candidate Profiles — COMPLETE

**Goal:** Complete candidate configuration

| Phase | Task | Deliverable | Status |
|-------|------|-------------|--------|
| 2.1 | Platform Accounts | Encrypted cookie storage per candidate, login flow | ✅ COMPLETE |
| 2.2 | Candidate Profile | Edit experience, location, timezone | ✅ COMPLETE (via document upload) |
| 2.3 | Job Titles | Per-candidate preferred titles, priority ordering | ✅ COMPLETE + AI extraction |
| 2.4 | Skills | Required/preferred skills per candidate | ✅ COMPLETE + AI extraction |
| 2.5 | Search Queries | Per-candidate query management, validation | ⏳ Deferred to Phase 3 |
| 2.6 | Profile UI | Settings pages for all candidate config | ✅ COMPLETE |

**Additional Features Implemented:**
- ✅ AI-powered job title extraction from documents
- ✅ AI-powered skill extraction with categorization (required/preferred)
- ✅ Skills modal with search, filter, bulk actions
- ✅ Enable/disable skills toggle for search matching
- ✅ Search preferences (min scores, remote-only, experience levels)
- ✅ Platform accounts UI with cookie import
- ✅ Document upload and parsing system
- ✅ LLM function mappings for all AI features

**End of Phase 2:** Full candidate profiles ready for job search ✅

---

### ✅ LLM Configuration Redesign — COMPLETE

**Additional improvements implemented after Phase 2:**

| Feature | Description | Status |
|---------|-------------|--------|
| **Inline Model Selectors** | Dropdown next to each AI action button | ✅ COMPLETE |
| **Reusable Model Selector Widget** | `components/model_selector.html` component | ✅ COMPLETE |
| **Backend API Endpoints** | `/api/llm/models`, `/api/llm/function/{name}/model` | ✅ COMPLETE |
| **Code Cleanup (DRY)** | Removed duplicate functions, single source of truth | ✅ COMPLETE |
| **Enhanced Navigation** | Links between provider config and function mappings | ✅ COMPLETE |

**AI Functions Configured (5 total):**
- ✅ `job_title_parser` - Job Title Parser (AI)
- ✅ `skill_extractor` - Skill Extractor (AI)
- ✅ `job_scorer` - Job Scorer (AI) - Ready for Phase 3
- ✅ `resume_matcher` - Resume-Job Matcher (AI) - Ready for Phase 3
- ✅ `ai_chat` - AI Chat Assistant

**Files Changed:**
- Backend: 7 files (removed duplicates, added API endpoints, updated imports)
- Frontend: 4 files (new widget component, added inline selectors)

---

### Phase 3: Job Search Engine (Hours 23-41)

**Goal:** Conservative scraping with anti-detection

| Phase | Task | Deliverable | Time |
|-------|------|-------------|------|
| 3.1 | Job Search Service | Async Playwright scraping | 4h |
| 3.2 | Rate Limiter | SQLite-backed, persistent across restarts | 3h |
| 3.3 | Search Lock | File-based global lock (one search at a time) | 1h |
| 3.4 | AI Analysis | Remote score, skill match, Ollama with fallback | 6h |
| 3.5 | Deduplication | Multi-signal matching, calibrated thresholds | 3h |
| 3.6 | Browser Manager | Orphan process cleanup, atexit handlers | 2h |

**End of Phase 3:** Working job scraping with full protection

---

### Phase 4: Job Management (Hours 42-50)

**Goal:** View, filter, track jobs

| Phase | Task | Deliverable | Time |
|-------|------|-------------|------|
| 4.1 | Job Dashboard | Interactive table, filters, sorting | 3h |
| 4.2 | Job Detail View | Full description, AI analysis, scores | 2h |
| 4.3 | Applications | Status tracking (interested/applied/interview) | 1h |
| 4.4 | Export & Reports | Markdown/CSV export, per-candidate | 2h |
| 4.5 | Backup Service | SQLite backup() API, safe snapshots | 1h |

**End of Phase 4:** Complete job management system

---

### Phase 5: Polish & Deploy (Hours 51-55+)

**Goal:** Production-ready application

| Phase | Task | Deliverable | Time |
|-------|------|-------------|------|
| 5.1 | Testing | Unit tests for critical components | 2h |
| 5.2 | Docker | Dockerfile, docker-compose.yml | 1h |
| 5.3 | Documentation | User guide, troubleshooting | 30m |
| 5.4 | Monitoring | Failure alerts, usage statistics | 30m |

**End of Phase 5:** Production-ready, deployable application

---

## 📝 Phase 1 Enhancements (Critical Fixes Added)

After critical review, these items were **added to Phase 1** to prevent issues:

| Enhancement | Why Added | Time |
|-------------|-----------|------|
| **Setup Script** | Automate dependency installation, Playwright browsers | +30m |
| **Base Template** | DRY principle, consistent navigation/layout | +1h |
| **Static Files** | HTMX, Alpine.js required for frontend | +30m |
| **Flash Messages** | User feedback on actions (success/error) | +30m |
| **Logging** | Critical for debugging issues | +20m |
| **Health Check** | Verify database, config working | +30m |
| **Error Pages** | Better UX than default errors | +30m |

**Removed from Phase 1:**
- ❌ Separate "Security Layer" (integrated into each feature instead)
- ❌ Database migrations (add in Phase 2 when schema stabilizes)

**Net Impact:** +2 hours, but prevents 5+ hours of debugging later

---

## 🏗️ Architecture

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend** | FastAPI (async) | Modern, fast, auto API docs, async support |
| **Frontend** | HTMX + Alpine.js | Simple, no build step, interactive enough |
| **Database** | SQLite | Single file, no setup, works in Docker |
| **Browser Automation** | Playwright (async) | Modern, reliable, harder to detect than Selenium |
| **AI/LLM** | LiteLLM | Unified API (Ollama, OpenRouter, Anthropic, etc.) |
| **Security** | Cryptography + Bleach | Encryption + XSS protection |
| **Validation** | Pydantic | Input validation, type safety |

### Architecture Principle

**Frontend (GUI Only) → Backend (ALL Functionality)**

---

## 📁 Project Structure

```
job-finder-web/
├── backend/
│   ├── app.py                   # FastAPI async app
│   ├── config.py                # Env vars, conservative defaults
│   ├── security.py              # Encryption, XSS, validation
│   ├── database.py              # SQLite + migrations
│   ├── logging_config.py        # File + console logging
│   ├── routes/
│   │   ├── candidates.py        # Candidate CRUD
│   │   ├── candidate_parser.py  # AI parsing (job titles, skills)
│   │   ├── skills.py            # Skills management [NEW]
│   │   ├── preferences.py       # Search preferences [NEW]
│   │   ├── platform_accounts.py # Cookie management [NEW]
│   │   ├── documents.py         # Document upload/management
│   │   ├── chat.py              # AI Chat interface
│   │   ├── llm_config.py        # LLM provider config
│   │   ├── llm_functions.py     # Function-to-model mappings
│   │   ├── llm_test.py          # LLM test endpoint
│   │   └── health.py            # Health check
│   ├── services/
│   │   ├── llm_service.py       # Canonical LLM utilities [NEW]
│   │   ├── document_parser.py   # Document parsing service
│   │   ├── job_title_parser.py  # Job title extraction
│   │   ├── init_prompts.py      # Initialize system prompts
│   │   └── init_function_mappings.py # Init LLM mappings [NEW]
│   ├── models/
│   │   ├── candidate.py         # Candidate model
│   │   ├── job.py               # Job & JobApplication models
│   │   ├── llm_provider.py      # LLMProvider & LLMModel
│   │   ├── supporting.py        # JobTitle, Skill, Preferences
│   │   ├── platform_account.py  # Platform accounts [NEW]
│   │   └── document.py          # Documents & parse prompts
│   ├── utils/
│   │   └── claude_code_auth.py  # OAuth for Claude Code [NEW]
│   └── database/
│       ├── migrate_add_job_title_fields.py
│       └── migrate_add_oauth_auth.py
├── frontend/
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── chat.html
│   │   ├── candidates/
│   │   │   ├── list.html
│   │   │   ├── detail.html      # With inline model selectors
│   │   │   └── edit.html
│   │   ├── skills/
│   │   │   ├── modal.html       # Skills manager [NEW]
│   │   │   └── parse_result.html # AI parse results [NEW]
│   │   ├── preferences/
│   │   │   └── edit.html        # Search preferences [NEW]
│   │   ├── accounts/
│   │   │   └── list.html        # Platform accounts [NEW]
│   │   ├── settings/
│   │   │   ├── llm.html         # Provider config
│   │   │   ├── functions.html   # Function mappings
│   │   │   └── llm_test_result.html
│   │   └── errors/
│   │       ├── 404.html
│   │       └── 500.html
│   └── static/
│       ├── css/
│       └── js/
├── data/
│   ├── jobs.db                  # Main database
│   ├── candidates/
│   │   └── {uuid}/
│   │       ├── documents/
│   │       └── exports/
│   ├── cookies/                 # ENCRYPTED .enc files
│   └── backups/
├── logs/
│   └── app.log
├── migrate_skills.py            # Skills migration [NEW]
├── migrate_platform_accounts.py # Accounts migration [NEW]
├── .env.example
├── requirements.txt
├── run.py                       # Entry point
└── Dockerfile                   # Phase 5
```

---

## 🔐 Security Architecture

### Cookie Encryption (Critical)

```python
from cryptography.fernet import Fernet

# Generate key (one-time setup)
ENCRYPTION_KEY = Fernet.generate_key()

# Encrypt cookies before saving
cipher = Fernet(ENCRYPTION_KEY)
encrypted = cipher.encrypt(json.dumps(cookies).encode())

# Save to file
with open(f"cookies/{candidate_id}_{platform}.enc", "wb") as f:
    f.write(encrypted)

# Decrypt when loading
decrypted = cipher.decrypt(encrypted)
cookies = json.loads(decrypted)
```

### XSS Protection (Critical)

```python
from bleach import clean

# Sanitize job descriptions before saving
clean_description = clean(raw_description, tags=[], strip=True)
```

### Input Validation (Critical)

```python
from pydantic import validator, Field

class SearchQueryCreate(BaseModel):
    query: str = Field(..., min_length=3, max_length=100)
    
    @validator('query')
    def validate_query(cls, v):
        if any(c in v for c in ["'", '"', ";", "--"]):
            raise ValueError("Invalid characters")
        return v.strip()
```

---

## 🛡️ Anti-Detection (Ultra-Conservative)

### Rate Limiting (Persistent, SQLite-Backed)

```python
LINKEDIN_DELAY_BETWEEN_REQUESTS = (8, 15)  # seconds
LINKEDIN_MAX_REQUESTS_PER_HOUR = 20
LINKEDIN_MAX_REQUESTS_PER_DAY = 100

GLASSDOOR_DELAY_BETWEEN_REQUESTS = (10, 20)  # seconds
GLASSDOOR_MAX_REQUESTS_PER_HOUR = 10
GLASSDOOR_MAX_REQUESTS_PER_DAY = 50

OPERATING_HOURS_START = 8  # 8 AM
OPERATING_HOURS_END = 22   # 10 PM

COOLDOWN_ON_FAILURE_MINUTES = 60
COOLDOWN_ON_CAPTCHA_MINUTES = 120  # 2 hours
```

### Global Search Lock (File-Based)

```python
import fcntl

class GlobalSearchLock:
    def __init__(self, lock_file="data/search.lock"):
        self.lock_file = lock_file
    
    def acquire(self):
        self.lock_fd = open(self.lock_file, 'w')
        fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
    
    def release(self):
        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        self.lock_fd.close()
```

---

## 📊 Database Schema (Key Tables)

```sql
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    folder_path TEXT,
    timezone TEXT DEFAULT 'Asia/Yerevan',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    title TEXT,
    company TEXT,
    platform TEXT,
    description_hash TEXT,
    description_path TEXT,
    ai_remote_score INTEGER,
    custom_fit_score INTEGER,
    status TEXT DEFAULT 'active',
    found_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE request_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE llm_providers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    api_key_encrypted TEXT,
    api_url TEXT,
    model_name TEXT,
    is_global_default BOOLEAN DEFAULT 0
);
```

---

## 🤖 AI Analysis

### Remote Work Score (100 points)

```python
def calculate_ai_remote_score(ai_analysis):
    score = 0
    score += 40 if ai_analysis.remote_type == "Fully Remote" else 20
    score += 25 if ai_analysis.location == "Worldwide" else 15
    score += 20 if ai_analysis.citizenship_required is None else 10
    score += 15 if ai_analysis.office_visits == "Never" else 0
    return score
```

### Armenia Compatibility

```python
def is_armenia_compatible(ai_analysis):
    red_flags = ["US citizens only", "must relocate", "onsite required"]
    return not any(flag in ai_analysis.red_flags for flag in red_flags)
```

---

## 📝 Configuration

### Environment Variables (.env.example)

```bash
# Security (REQUIRED)
ENCRYPTION_KEY=your-generated-key-here
SECRET_KEY=your-secret-key

# LLM (optional)
OLLAMA_URL=http://localhost:11434
OPENROUTER_API_KEY=

# App (optional)
DEBUG=true
HOST=0.0.0.0
PORT=8000
DEFAULT_TIMEZONE=Asia/Yerevan
```

---

## 📋 Requirements.txt

```txt
# Web Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
jinja2>=3.1.3

# Database
sqlalchemy>=2.0.25

# Browser Automation
playwright>=1.40.0
playwright-stealth>=1.0.0

# AI/LLM
litellm>=1.30.0

# Security
cryptography>=42.0.0
bleach>=6.1.0
itsdangerous>=2.1.2

# Validation
pydantic>=2.5.0

# Utilities
pyyaml>=6.0
python-dotenv>=1.0.0
fuzzywuzzy>=0.18.0
python-levenshtein>=0.23.0
pytz>=2024.1
psutil>=5.9.0
```

---

## 🚀 Usage Flow

### Candidate Creation
1. Dashboard → "Add Candidate"
2. Fill form: name, location, timezone, experience
3. System creates database record + UUID folder
4. Configure job titles, skills, search queries

### Job Search
1. Select candidate from dropdown
2. Click "Search Jobs"
3. Backend: acquire lock → check rate limits → scrape → analyze → save
4. View results in dashboard

### Daily Usage
- Morning (5 min): Review new jobs, bookmark interesting
- Evening (15 min): Update application status, add notes

---

## ⚠️ Risk Acknowledgments

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LinkedIn account ban | 2-5% (6 months) | Catastrophic | Conservative limits, stop on CAPTCHA |
| Glassdoor IP ban | 5-10% (3 months) | Medium | Use phone hotspot |
| Ollama too slow | 30% | Low | Fallback to OpenRouter |
| Data corruption | <1% | High | Safe backups |

---

## 📞 Getting Started

**Next Step:** Phase 1.1 - Project Skeleton

**Say "Start Phase 1" when ready to begin.**

---

## 📌 Related Documents

| File | Description |
|------|-------------|
| `linkedin-profile.md` | Your professional profile |
| `prefered-job-titles.md` | Your preferred job titles |
| `my-role-claude-gold.md` | Detailed role description |
| `job-search-platforms.md` | Job platform research |
| `PROJECT_PLAN.md` | This file - complete plan |

---

**END OF PROJECT PLAN v7.0**
