# File Selection for Parse — Plan

**Date:** March 25, 2026  
**Feature:** Allow users to select which files to parse for job titles

---

## 🎯 Requirements

1. **UI:** Show file selection before parsing
2. **Default:** Remember last selection
3. **Display:** Show file name + size + upload date
4. **Backend:** Accept list of document IDs to parse

---

## 📊 Proposed Design

### Option 1: Modal Dialog (Recommended) ✅

```
┌─────────────────────────────────────────────────────────┐
│  Select Files to Parse                            [X]   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Model: [qwen3-coder:480b ▼] ✓ Ready                   │
│                                                         │
│  ☑️ linkedin-profile.md                        ☑️ ☑️   │
│     Profile • 9.6 KB • Mar 23, 2026                    │
│                                                         │
│  ☑️ prefered-job-titles.md                     ☑️ ☑️   │
│     Job Titles • 2.1 KB • Mar 23, 2026                 │
│                                                         │
│  ☐  cover-letter.md                            ☐  ☐    │
│     Cover Letter • 4.5 KB • Mar 23, 2026               │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ [Select All] [Clear]                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│                    [Cancel] [Parse 2 Files]             │
└─────────────────────────────────────────────────────────┘
```

**Benefits:**
- Clear, focused interaction
- Shows all file details
- Easy to select/deselect
- Can show model selector in modal

---

## 🔧 Implementation Plan

### Phase 1: Backend API

#### 1.1 Update Parse Endpoint
**File:** `backend/routes/candidate_parser.py`

**Current:**
```python
@router.post("/{candidate_id}/parse-job-titles")
async def parse_job_titles(candidate_id: int, db: Session):
    # Parses ALL documents
    success, job_titles, error = parse_all_candidate_documents(db, candidate_id)
```

**New:**
```python
@router.post("/{candidate_id}/parse-job-titles")
async def parse_job_titles(
    candidate_id: int,
    request: Request,
    db: Session
):
    body = await request.json()
    document_ids = body.get("document_ids", [])  # Optional list
    
    if document_ids:
        # Parse selected documents only
        success, job_titles, error = parse_selected_documents(
            db, candidate_id, document_ids
        )
    else:
        # Parse all (backward compatible)
        success, job_titles, error = parse_all_candidate_documents(
            db, candidate_id
        )
```

#### 1.2 Add New Service Function
**File:** `backend/services/job_title_parser.py`

```python
def parse_selected_documents(
    db: Session,
    candidate_id: int,
    document_ids: List[int]
) -> Tuple[bool, List[Dict], Optional[str]]:
    """Parse only selected documents"""
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.id.in_(document_ids),
        CandidateDocument.is_active == True
    ).all()
    
    # ... same parsing logic as parse_all_candidate_documents
```

#### 1.3 Add Get Documents Endpoint
```python
@router.get("/{candidate_id}/documents")
async def get_candidate_documents(candidate_id: int, db: Session):
    """Get list of parseable documents with metadata"""
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.is_active == True,
        CandidateDocument.document_type.in_(["job_titles", "profile", "resume", "cover_letter"])
    ).all()
    
    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat(),
                "parse_status": doc.parse_status
            }
            for doc in documents
        ]
    }
```

---

### Phase 2: Frontend UI

#### 2.1 Create File Selection Modal
**File:** `frontend/templates/components/file_selector.html`

```html
<!-- File Selection Modal -->
<div class="modal fade" id="fileSelectorModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">
                    <i class="bi bi-file-earmark-check"></i>
                    Select Files to Parse
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <!-- Model Selector -->
                {% include "components/model_selector.html" %}
                
                <!-- File List -->
                <div id="fileList" class="list-group">
                    <!-- Populated by JavaScript -->
                </div>
                
                <!-- Quick Actions -->
                <div class="btn-group mt-3">
                    <button class="btn btn-sm btn-outline-primary" onclick="selectAllFiles()">
                        Select All
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" onclick="clearSelection()">
                        Clear
                    </button>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                    Cancel
                </button>
                <button type="button" class="btn btn-primary" onclick="parseSelectedFiles()">
                    <i class="bi bi-magic"></i> Parse <span id="fileCount">0</span> Files
                </button>
            </div>
        </div>
    </div>
</div>
```

#### 2.2 Update Parse Button
**File:** `frontend/templates/candidates/detail.html`

**Current:**
```html
<button class="btn btn-primary btn-sm"
        hx-post="/candidates/{{ candidate.id }}/parse-job-titles">
    <i class="bi bi-magic"></i> Parse from Files
</button>
```

**New:**
```html
<button class="btn btn-primary btn-sm" onclick="showFileSelector()">
    <i class="bi bi-magic"></i> Parse from Files
</button>
```

#### 2.3 JavaScript Functions
**File:** `frontend/templates/candidates/detail.html` (in `<script>`)

```javascript
let availableFiles = [];
let lastSelection = [];

// Show file selector modal
function showFileSelector() {
    // Fetch available files
    fetch(`/candidates/{{ candidate.id }}/documents`)
        .then(response => response.json())
        .then(data => {
            availableFiles = data.documents;
            
            // Load last selection from localStorage
            const saved = localStorage.getItem(`parse_selection_{{ candidate.id }}`);
            lastSelection = saved ? JSON.parse(saved) : [];
            
            // Render file list
            renderFileList();
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('fileSelectorModal'));
            modal.show();
        });
}

// Render file list with checkboxes
function renderFileList() {
    const container = document.getElementById('fileList');
    container.innerHTML = availableFiles.map(file => `
        <label class="list-group-item">
            <div class="d-flex align-items-start">
                <input type="checkbox" class="form-check-input me-2"
                       value="${file.id}"
                       ${lastSelection.includes(file.id) ? 'checked' : ''}
                       onchange="updateFileCount()">
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between">
                        <strong>${file.filename}</strong>
                        <span class="badge bg-secondary">${formatFileSize(file.file_size)}</span>
                    </div>
                    <div class="text-muted small">
                        ${file.document_type} • ${formatDate(file.created_at)}
                    </div>
                </div>
            </div>
        </label>
    `).join('');
    
    updateFileCount();
}

// Update file count in button
function updateFileCount() {
    const checked = document.querySelectorAll('#fileList input:checked');
    document.getElementById('fileCount').textContent = checked.length;
}

// Select all files
function selectAllFiles() {
    document.querySelectorAll('#fileList input').forEach(cb => cb.checked = true);
    updateFileCount();
}

// Clear selection
function clearSelection() {
    document.querySelectorAll('#fileList input').forEach(cb => cb.checked = false);
    updateFileCount();
}

// Parse selected files
function parseSelectedFiles() {
    const checked = document.querySelectorAll('#fileList input:checked');
    const documentIds = Array.from(checked).map(cb => parseInt(cb.value));
    
    // Save selection for next time
    localStorage.setItem(`parse_selection_{{ candidate.id }}`, JSON.stringify(documentIds));
    
    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('fileSelectorModal'));
    modal.hide();
    
    // Start parsing
    showParsingStatus();
    parseWithSelection(documentIds);
}

// Parse with selected files
function parseWithSelection(documentIds) {
    fetch(`/candidates/{{ candidate.id }}/parse-job-titles`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({document_ids: documentIds})
    })
    .then(response => response.json())
    .then(data => handleParseResponse({detail: data}));
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
    });
}
```

---

### Phase 3: Backend Implementation

#### 3.1 Add Get Documents Route
**File:** `backend/routes/candidate_parser.py`

```python
@router.get("/{candidate_id}/documents")
async def get_candidate_documents(candidate_id: int, db: Session = Depends(get_db)):
    """Get list of parseable documents with metadata"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.is_active == True,
        CandidateDocument.document_type.in_(["job_titles", "profile", "resume", "cover_letter"])
    ).order_by(CandidateDocument.created_at.desc()).all()
    
    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "file_size": doc.file_size,
                "created_at": doc.created_at.isoformat(),
                "parse_status": doc.parse_status
            }
            for doc in documents
        ]
    }
```

#### 3.2 Update Parse Route
**File:** `backend/routes/candidate_parser.py`

```python
@router.post("/{candidate_id}/parse-job-titles")
async def parse_job_titles(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Parse selected or all documents"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Parse request body
    try:
        body = await request.json()
        document_ids = body.get("document_ids", [])
    except:
        document_ids = []
    
    # Parse selected or all documents
    if document_ids:
        success, job_titles, error = parse_selected_documents(db, candidate_id, document_ids)
        message = f"Extracted {len(job_titles)} job titles from {len(document_ids)} file(s)"
    else:
        success, job_titles, error = parse_all_candidate_documents(db, candidate_id)
        message = f"Extracted {len(job_titles)} job titles from documents"
    
    if not success:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": error, "job_titles": []}
        )
    
    return {
        "success": True,
        "message": message,
        "job_titles": job_titles,
        "warning": error
    }
```

#### 3.3 Add Service Function
**File:** `backend/services/job_title_parser.py`

```python
def parse_selected_documents(
    db: Session,
    candidate_id: int,
    document_ids: List[int]
) -> Tuple[bool, List[Dict], Optional[str]]:
    """
    Parse only selected documents for job titles.
    
    Returns:
        (success, job_titles_list, error_message)
    """
    documents = db.query(CandidateDocument).filter(
        CandidateDocument.candidate_id == candidate_id,
        CandidateDocument.id.in_(document_ids),
        CandidateDocument.is_active == True
    ).all()
    
    if not documents:
        return False, [], "No documents found"
    
    all_job_titles = []
    errors = []
    
    for doc in documents:
        success, titles, error = parse_document_for_job_titles(db, doc)
        if success:
            all_job_titles.extend(titles)
        else:
            errors.append(f"{doc.filename}: {error}")
    
    if not all_job_titles:
        return False, [], f"All documents failed: {'; '.join(errors)}"
    
    # Deduplicate by title
    deduplicated = {}
    for title_data in all_job_titles:
        title = title_data["title"]
        if title not in deduplicated or title_data["priority"] < deduplicated[title]["priority"]:
            deduplicated[title] = title_data
    
    result = sorted(deduplicated.values(), key=lambda x: x["priority"])
    
    warning = f"Warning: {'; '.join(errors)}" if errors else None
    return True, result, warning
```

---

## 📋 Files to Modify

| File | Changes |
|------|---------|
| `backend/routes/candidate_parser.py` | Add GET /documents, update POST /parse-job-titles |
| `backend/services/job_title_parser.py` | Add parse_selected_documents() |
| `frontend/templates/candidates/detail.html` | Add file selector modal, update parse button |
| `frontend/templates/components/file_selector.html` | NEW - File selection modal component |

---

## 🧪 Testing

1. **No selection (backward compatible)**
   - Click "Parse from Files"
   - Modal shows with last selection
   - Click "Parse" without changes
   - Parses selected files

2. **Select specific files**
   - Click "Parse from Files"
   - Uncheck some files
   - Click "Parse 2 Files"
   - Only parses checked files

3. **Remember selection**
   - Select files and parse
   - Refresh page
   - Click "Parse from Files" again
   - Same files are pre-selected

4. **Select All / Clear**
   - Click "Select All" → all checked
   - Click "Clear" → none checked

---

## 🎯 User Flow

```
1. User clicks "Parse from Files"
   ↓
2. Modal opens showing:
   - Model selector
   - List of files with checkboxes
   - File name, type, size, date
   - Select All / Clear buttons
   ↓
3. User selects files:
   - Checkboxes for each file
   - Last selection remembered
   ↓
4. User clicks "Parse X Files"
   ↓
5. Modal closes
   - Selection saved to localStorage
   - Parsing starts with selected files only
   ↓
6. Results shown in editable table
```

---

**Ready to implement?**
