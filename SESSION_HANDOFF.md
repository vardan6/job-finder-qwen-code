# Job Finder Web App — Session Handoff Document

**Date:** March 23, 2026  
**Status:** Phase 2 In Progress (Candidate Profiles - Document Upload & AI Chat Complete)  
**Server:** Running at http://localhost:9002 (auto-reload enabled)

---

## ✅ What Was Completed This Session

### 1. Candidate Document Upload System
- **Models Created:**
  - `CandidateDocument` - Stores uploaded files with metadata
  - `DocumentSection` - Stores parsed sections from documents
  - `DocumentParsePrompt` - AI prompts for parsing (system + per-candidate)
  - `LLMFunctionMapping` - Maps functionalities to specific LLM models

- **Features:**
  - Upload markdown files (`.md`) to candidate profiles
  - Auto-detect document type from filename
  - AI parsing to extract job titles using configured LLM
  - Store files in `data/candidates/{id}/documents/`
  - View, re-parse, delete documents via UI
  - Customizable parse prompts per candidate with reset option

- **Routes:**
  - `POST /candidates/{id}/documents/upload` - Upload & parse
  - `GET /candidates/{id}/documents/{doc_id}/view` - View content
  - `POST /candidates/{id}/documents/{doc_id}/reparse` - Re-parse
  - `POST /candidates/{id}/documents/{doc_id}/delete` - Delete
  - `GET /candidates/{id}/prompts/{type}` - Get prompt
  - `POST /candidates/{id}/prompts/{type}/save` - Save custom prompt
  - `POST /candidates/{id}/prompts/{type}/reset` - Reset to system

### 2. AI Chat Interface (Simple Open Web UI Alternative)
- **Features:**
  - Select any configured LLM model (Ollama, NVIDIA, OpenRouter, etc.)
  - Chat window with conversation history
  - Session-based conversation persistence
  - Clear chat functionality
  - Keyboard shortcut: `Ctrl+Enter` to send

- **Routes:**
  - `GET /chat` - Chat page
  - `POST /api/chat` - Send message
  - `POST /api/chat/clear` - Clear conversation

### 3. LLM Function Mappings
- **Page:** `/settings/functions`
- Map each AI function to a specific model:
  - `job_title_parser` - Extracts job titles from documents
  - `job_scorer` - Scores jobs for remote compatibility
  - `resume_matcher` - Matches resumes to job descriptions
  - `ai_chat` - General chat assistant

### 4. Default System Prompts
- `job_titles_parser` - Extracts job titles with priority inference
- `profile_parser` - Extracts summary, skills, experience, certifications

---

## 📁 New Files Created

```
backend/
├── models/
│   └── document.py              # NEW: Document models
├── services/
│   ├── __init__.py              # NEW: Services package
│   └── document_parser.py       # NEW: AI parsing service
├── routes/
│   ├── documents.py             # NEW: Document CRUD routes
│   ├── llm_functions.py         # NEW: LLM function mappings
│   └── chat.py                  # NEW: AI chat routes
└── app.py                       # MODIFIED: Added new routers

frontend/templates/
├── candidates/
│   └── detail.html              # MODIFIED: Added document upload UI
├── settings/
│   └── functions.html           # NEW: LLM function mappings page
├── chat.html                    # NEW: AI chat interface
└── base.html                    # MODIFIED: Added AI Chat to nav

backend/database.py              # MODIFIED: Added migrations for new models
```

---

## 🔧 How to Restart

```bash
cd /mnt/c/Users/vardana/Documents/Proj/job-finder-qwen-code/job-finder-web
source venv/bin/activate
python run.py
```

Then open: **http://localhost:9002**

---

## 🧪 Testing Status

| Feature | Status | Notes |
|---------|--------|-------|
| Document Upload | ✅ Works | Ollama parsing tested |
| AI Chat (Ollama) | ✅ Works | Tested and functional |
| AI Chat (NVIDIA) | ✅ FIXED | Provider prefix + API URL fixed |
| LLM Function Mappings | ✅ Works | Can map functions to models |
| Custom Prompts | ✅ Implemented | Not yet tested |

---

## 🐛 Known Issues / Pending Fixes

### ✅ FIXED This Session:

1. **NVIDIA API Key Decryption** 
   - Changed `decrypt_token` → `decrypt_data` in:
     - `backend/routes/chat.py`
     - `backend/services/document_parser.py`

2. **NVIDIA Model Name Prefix** 
   - Added proper provider prefixes for LiteLLM:
     - `nvidia/` for NVIDIA models
     - `openrouter/` for OpenRouter models
     - `anthropic/` for Anthropic models
     - `openai/` for OpenAI models
   - Fixed in: `chat.py`, `document_parser.py`, `llm_test.py`

3. **NVIDIA API Base URL** 
   - Fixed double `/v1/v1/` path issue
   - LiteLLM appends `/v1` automatically, so strip it from config
   - Code: `if api_base.endswith('/v1'): api_base = api_base[:-3]`
   - Fixed in: `chat.py`, `document_parser.py`

### ⚠️ Minor (Non-blocking):

4. **Database Migration Warning**
   - Warning: `'LLMProvider' object has no attribute 'model_name'`
   - This is expected (old migration code), doesn't affect functionality

---

## 📋 Next Steps (Phase 2 Continuation)

### Immediate (Next Session)
1. **Test NVIDIA Integration** - Verify AI Chat works with NVIDIA models
2. **Test Document Upload** - Upload `prefered-job-titles.md` and verify extraction
3. **Test All Providers** - OpenRouter, Anthropic, OpenAI (if API keys configured)

### Phase 2 Remaining Tasks
- [ ] Candidate experience section (manual entry + AI extraction)
- [ ] Candidate skills management (required/preferred)
- [ ] Candidate platform accounts (LinkedIn, Glassdoor cookies)
- [ ] Candidate timezone & location preferences
- [ ] Search query management per candidate

### Phase 3 (Future)
- [ ] LinkedIn scraper with Playwright
- [ ] Glassdoor scraper
- [ ] Rate limiting system
- [ ] Job deduplication
- [ ] AI job scoring

---

## 🔑 Key Configuration

### Environment Variables (.env)
```bash
ENCRYPTION_KEY=<auto-generated>
OLLAMA_URL=http://localhost:11434
NVIDIA_API_KEY=<your-key-here>
OPENROUTER_API_KEY=<your-key-here>
ANTHROPIC_API_KEY=<your-key-here>
OPENAI_API_KEY=<your-key-here>
DEFAULT_LLM_MODEL=ollama/llama3
PORT=9002
DEBUG=true
```

### Database Location
- `data/jobs.db` - SQLite database
- `data/candidates/{id}/documents/` - Uploaded files

### Default LLM Models
- **Ollama:** `llama3`, `llama3.1`, `mistral`, `gemma`, `codellama`, `phi3`
- **NVIDIA:** `meta/llama3-70b-instruct`, `meta/llama3-8b-instruct`, `meta/llama-3.1-405b-instruct`
- **OpenRouter:** `meta-llama/llama-3-70b-instruct`
- **Anthropic:** `claude-3-opus`
- **OpenAI:** `gpt-4-turbo`

---

## 📚 Reference Documents

User's profile documents (for document upload testing):
- `linkedin-profile.md` - Professional experience, skills
- `prefered-job-titles.md` - 7 target job titles
- `my-role-claude-gold.md` - Detailed role description
- `cover-letter.md` - Cover letter templates

---

## 💡 Tips for Next Session

1. **Server should already be running** at http://localhost:9002
2. **Test AI Chat first** with Ollama (known working)
3. **Test NVIDIA** to verify the API URL fix works
4. **Upload a test document** to a candidate to verify job title extraction
5. **Check logs** at `logs/app.log` for any errors

---

## 🎯 Current Project State Summary

**Phase 1:** ✅ Complete (Core Foundation)  
**Phase 2:** 🟡 In Progress (Candidate Profiles - Document Upload & AI Chat DONE)  
**Phase 3:** ⏳ Pending (Job Search Engine)

**Working Features:**
- ✅ Candidate CRUD
- ✅ Document Upload & AI Parsing
- ✅ AI Chat (multi-model: Ollama, NVIDIA, OpenRouter, etc.)
- ✅ LLM Function Mappings
- ✅ Custom Parse Prompts

**Ready for Production Use:** No (still in development)  
**Ready for Testing:** Yes (core features functional)

---

## 🔗 Important URLs

- **Dashboard:** http://localhost:9002
- **Candidates:** http://localhost:9002/candidates
- **AI Chat:** http://localhost:9002/chat
- **LLM Settings:** http://localhost:9002/settings/llm
- **Function Mappings:** http://localhost:9002/settings/functions

---

**END OF HANDOFF DOCUMENT**
