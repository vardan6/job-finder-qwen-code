# Job Titles Parse Fix — Complete ✅

**Date:** March 24, 2026  
**Issue:** "Parse from Files" button showed error: "LLM returned empty response"  
**Status:** FIXED

---

## 🐛 Problem

When clicking "Parse from Files" button for job titles:
- Error message: "An error occurred. Please try again"
- Server error: "LLM returned empty response"
- No job titles extracted

**Root Cause:**
- Configured model (`qwen3-coder:480b-cloud`) requires OAuth authentication
- OAuth token expired (Claude Code token refresh failed)
- No fallback to working Ollama models when LLM call fails
- Code only fell back if `model` was `None`, not if `call_llm()` returned `None`

---

## ✅ Solution

Added fallback to direct Ollama call when configured model fails, similar to the fix we did for skills extraction.

**File:** `backend/services/job_title_parser.py`

**Added Code:**
```python
# Call LLM
result = call_llm(db, model, full_prompt)

# Fallback to direct Ollama call if configured model failed
if not result:
    try:
        from litellm import completion
        response = completion(
            model="ollama/llama3",
            messages=[{"role": "user", "content": full_prompt}],
            api_base="http://localhost:11434"
        )
        result = response.choices[0].message.content if response else None
    except Exception as ollama_error:
        print(f"Direct Ollama fallback failed: {ollama_error}")
        return False, [], f"LLM call failed: {str(ollama_error)}"

if not result:
    return False, [], "LLM returned empty response"
```

**How It Works:**
1. Try to use configured model for `job_title_parser` function
2. If `call_llm()` returns `None` (OAuth failure, timeout, etc.)
3. Fallback to direct Ollama call with `ollama/llama3`
4. If Ollama also fails, return error message
5. Success → extract job titles from response

---

## 🧪 Testing Results

### Before Fix
```bash
curl -X POST http://localhost:9002/candidates/1/parse-job-titles

# Response:
{
  "success": false,
  "message": "All documents failed to parse: 
              linkedin-profile.md: LLM returned empty response; 
              prefered-job-titles.md: LLM returned empty response"
}
```

### After Fix
```bash
curl -X POST http://localhost:9002/candidates/1/parse-job-titles

# Response:
{
  "success": true,
  "message": "Extracted 12 job titles from documents",
  "job_titles": [
    {"title": "Application Engineer", "priority": 1},
    {"title": "Lead QA Engineer", "priority": 1},
    {"title": "Staff SDET", "priority": 1},
    {"title": "Principal SDET", "priority": 1},
    {"title": "Principal EDA Design Automation Engineer", "priority": 1},
    {"title": "Staff CAD Engineer (EDA Tools / Workflow Optimization)", "priority": 1},
    {"title": "Senior QA Engineer", "priority": 2},
    {"title": "Lead SDET – EDA/Semiconductor", "priority": 2},
    {"title": "Senior EDA Tools Engineer (Test Infrastructure)", "priority": 2},
    {"title": "R&D Engineer", "priority": 3},
    {"title": "IT Administrator", "priority": 3},
    {"title": "Test Infrastructure Architect / QA Automation Architect", "priority": 3}
  ]
}
```

---

## 📁 Files Modified

| File | Changes |
|------|---------|
| `backend/services/job_title_parser.py` | Added Ollama fallback in `parse_document_for_job_titles()` |

---

## 🎯 How to Test

### Via Web UI
1. Open http://localhost:9002/candidates/1
2. Find "Preferred Job Titles (AI Extracted)" section
3. Select a model from dropdown (optional)
4. Click "Parse from Files" button
5. Wait 30-90 seconds
6. See extracted job titles in editable table

### Via API
```bash
curl -X POST http://localhost:9002/candidates/1/parse-job-titles
```

### Via Python
```python
from backend.database import SessionLocal
from backend.services.job_title_parser import parse_all_candidate_documents

db = SessionLocal()
success, job_titles, error = parse_all_candidate_documents(db, 1)
print(f"Extracted {len(job_titles)} job titles")
```

---

## 🔧 Technical Details

### Why OAuth Was Failing
- Claude Code OAuth token expired
- Token refresh endpoint returned: `400 - {"error": "invalid_grant"}`
- Configured model (`qwen3-coder:480b-cloud`) tried to use OAuth
- `call_llm()` returned `None` when OAuth failed

### Why Fallback Works
- Ollama is running locally at `http://localhost:11434`
- Has working models: `llama3`, `gemma3`, `gpt-oss`, etc.
- Direct API call doesn't require OAuth
- Slower than cloud models but reliable

### Performance
- **Before:** Failed immediately with OAuth error
- **After:** ~60-90 seconds (Ollama is slower but works)
- **Trade-off:** Reliability over speed

---

## 💡 Recommendations

### Short Term (Optional)
1. **Re-import Claude Code OAuth token:**
   ```bash
   claude auth login
   curl -X POST http://localhost:9002/settings/1/claude-code/import
   ```

2. **Change default model for job_title_parser:**
   - Go to http://localhost:9002/settings/functions
   - Select "Ollama → llama3" for Job Title Parser
   - Saves immediately, no OAuth needed

### Long Term (Optional)
1. **Add model health check** - Test model before using
2. **Add timeout handling** - Don't wait forever for slow models
3. **Add model retry logic** - Try multiple models in order
4. **Cache parsed results** - Don't re-parse same documents

---

## ✅ Acceptance Criteria - ALL MET

- [x] "Parse from Files" button works without errors
- [x] Job titles extracted successfully
- [x] Fallback to Ollama when configured model fails
- [x] Error messages are clear and helpful
- [x] No page reload errors
- [x] Works via web UI and API

---

**The "Parse from Files" feature is now working reliably!** ✅
