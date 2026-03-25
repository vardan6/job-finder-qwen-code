# File Selection for Parse — Complete ✅

**Date:** March 25, 2026  
**Feature:** Select which files to parse for job titles  
**Status:** IMPLEMENTED AND TESTED

---

## 🎯 What Was Implemented

Users can now select which files to include when parsing job titles, with:
- ✅ Modal dialog with file checkboxes
- ✅ File name + type + size + upload date
- ✅ Remembers last selection (localStorage)
- ✅ Select All / Clear buttons
- ✅ Model selector in modal
- ✅ Backward compatible (works without selection)

---

## 📊 User Interface

### Modal Dialog
```
┌─────────────────────────────────────────────────────────┐
│  Select Files to Parse                            [X]   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  AI Model                                               │
│  [qwen3-coder:480b ▼] ✓ Ready                          │
│                                                         │
│  Available Files                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ☑️ linkedin-profile.md                   9.5 KB   │  │
│  │    Profile • Uploaded Mar 23, 2026  ✓ Parsed     │  │
│  │                                                  │  │
│  │ ☑️ prefered-job-titles.md                1.8 KB   │  │
│  │    Job Titles • Uploaded Mar 23, 2026  ✓ Parsed  │  │
│  │                                                  │  │
│  │ ☐  cover-letter.md                       4.0 KB   │  │
│  │    Cover Letter • Uploaded Mar 23, 2026          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [Select All] [Clear]             2 files selected      │
│                                                         │
│            [Cancel]        [Parse 2 File(s)]            │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Technical Implementation

### Backend (3 files modified)

#### 1. New Service Function
**File:** `backend/services/job_title_parser.py`

```python
def parse_selected_documents(
    db: Session,
    candidate_id: int,
    document_ids: List[int]
) -> Tuple[bool, List[Dict], Optional[str]]:
    """Parse only selected documents for job titles"""
    # Filters documents by provided IDs
    # Same parsing logic as parse_all_candidate_documents
```

#### 2. New GET Endpoint
**File:** `backend/routes/candidate_parser.py`

```python
@router.get("/{candidate_id}/documents")
async def get_candidate_documents(candidate_id: int, db: Session):
    """Get list of parseable documents with metadata"""
    # Returns: id, filename, document_type, file_size, created_at, parse_status
```

#### 3. Updated POST Endpoint
**File:** `backend/routes/candidate_parser.py`

```python
@router.post("/{candidate_id}/parse-job-titles")
async def parse_job_titles(request: Request, db: Session):
    body = await request.json()
    document_ids = body.get("document_ids", [])
    
    if document_ids:
        # Parse selected files only
        success, job_titles, error = parse_selected_documents(db, candidate_id, document_ids)
    else:
        # Parse all files (backward compatible)
        success, job_titles, error = parse_all_candidate_documents(db, candidate_id)
```

### Frontend (3 files created/modified)

#### 1. File Selector Modal Component
**File:** `frontend/templates/components/file_selector.html` (NEW)

Features:
- Bootstrap modal with file list
- Checkboxes for each file
- File metadata display (name, type, size, date)
- Select All / Clear buttons
- Model selector integration
- localStorage for remembering selection

#### 2. Candidate Detail Page
**File:** `frontend/templates/candidates/detail.html`

Changes:
- Parse button now opens modal (not direct HTMX call)
- Added `showFileSelectorModal()` function
- Includes file selector modal

#### 3. JavaScript Functions
```javascript
// Load available files from API
function loadAvailableFiles() { ... }

// Render file list with checkboxes
function renderFileList() { ... }

// Toggle file selection
function toggleFileSelection(fileId, isChecked) { ... }

// Save/load selection from localStorage
localStorage.setItem(`parse_selection_${candidate_id}`, JSON.stringify(ids))

// Parse selected files
function parseSelectedFiles() {
    fetch('/candidates/{id}/parse-job-titles', {
        method: 'POST',
        body: JSON.stringify({document_ids: selectedFileIds})
    })
}
```

---

## 🧪 Testing Results

### Test 1: Get Documents
```bash
curl http://localhost:9002/candidates/1/documents

# Response:
{
  "documents": [
    {
      "id": 1,
      "filename": "linkedin-profile.md",
      "document_type": "profile",
      "file_size": 9682,
      "created_at": "2026-03-23T22:32:19",
      "parse_status": "completed"
    },
    ...
  ]
}
```

### Test 2: Parse Selected Files
```bash
curl -X POST http://localhost:9002/candidates/1/parse-job-titles \
  -H "Content-Type: application/json" \
  -d '{"document_ids": [1]}'

# Response:
{
  "success": true,
  "message": "Extracted 5 job titles from 1 file(s)",
  "job_titles": [
    {"title": "Application Engineer", "priority": 1},
    {"title": "Lead QA Engineer", "priority": 1},
    {"title": "Senior QA Engineer", "priority": 2},
    {"title": "R&D Engineer", "priority": 3},
    {"title": "IT Administrator", "priority": 3}
  ]
}
```

### Test 3: Parse All Files (Backward Compatible)
```bash
curl -X POST http://localhost:9002/candidates/1/parse-job-titles

# Response:
{
  "success": true,
  "message": "Extracted 12 job titles from documents",
  "job_titles": [...]
}
```

---

## 🎯 User Flow

### First Time Use
1. User clicks "Parse from Files"
2. Modal opens, loading all available files
3. All files selected by default
4. User can deselect files
5. Click "Parse X File(s)"
6. Selection saved to localStorage
7. Parsing starts with selected files

### Returning User
1. User clicks "Parse from Files"
2. Modal opens, loading files
3. **Last selection is remembered** (from localStorage)
4. User can modify selection
5. Click "Parse X File(s)"
6. New selection saved
7. Parsing starts

### Quick Actions
- **Select All** → Check all file checkboxes
- **Clear** → Uncheck all
- **File count badge** → Shows how many files selected

---

## 📁 Files Modified

| File | Type | Changes |
|------|------|---------|
| `backend/services/job_title_parser.py` | Modified | Added `parse_selected_documents()` |
| `backend/routes/candidate_parser.py` | Modified | Added GET /documents, updated POST /parse-job-titles |
| `frontend/templates/components/file_selector.html` | NEW | File selection modal component |
| `frontend/templates/candidates/detail.html` | Modified | Updated parse button, added modal include |

---

## 💡 Features

### File Information Display
- **File name** - Full filename
- **File type badge** - Profile, Job Titles, Resume, Cover Letter
- **File size** - Formatted (KB, MB)
- **Upload date** - Formatted date
- **Parse status** - Shows "✓ Parsed" if already parsed

### Selection Persistence
- **localStorage key:** `parse_selection_{candidate_id}`
- **Default:** All files selected
- **Remembers:** Last user selection
- **Cleared:** Never (persists across sessions)

### Model Selection
- Model selector embedded in modal
- Uses same `job_title_parser` function mapping
- Selection saved to database (not localStorage)

---

## ✅ Acceptance Criteria - ALL MET

- [x] Modal dialog with file checkboxes
- [x] Shows file name + size + date
- [x] Remembers last selection
- [x] Select All / Clear buttons
- [x] File count badge
- [x] Model selector in modal
- [x] Backend accepts document_ids array
- [x] Backward compatible (works without selection)
- [x] Parses only selected files
- [x] localStorage persistence

---

## 🎉 Summary

**The file selection feature is fully implemented and working!**

Users can now:
1. ✅ Choose which files to parse
2. ✅ See file details before parsing
3. ✅ Reuse last selection automatically
4. ✅ Quick select/clear all
5. ✅ Still works without selection (backward compatible)

**Tested and verified:**
- GET /candidates/1/documents ✅
- POST /candidates/1/parse-job-titles with document_ids ✅
- POST /candidates/1/parse-job-titles without document_ids ✅
- File selector modal renders correctly ✅
- localStorage persistence works ✅

---

**Ready to use!** Open http://localhost:9002/candidates/1 and click "Parse from Files" to see the new modal.
