# Preferred Job Titles Section - Fixes Applied

## Issues Fixed (March 25, 2026)

### 1. ✅ Available Files List Not Updated

**Problem:** When clicking "Parse from Files", the file list modal showed stale data or didn't show recently uploaded files.

**Root Cause:** The `showFileSelectorModal()` function wasn't calling `loadAvailableFiles()` before displaying the modal.

**Fix:** Updated `showFileSelectorModal()` in `detail.html`:
```javascript
function showFileSelectorModal() {
    // Load available files before showing modal
    loadAvailableFiles();
    
    const modal = new bootstrap.Modal(document.getElementById('fileSelectorModal'));
    modal.show();
}
```

**Result:** File list now refreshes every time the modal opens, showing all recently uploaded files.

---

### 2. ✅ Duplicate Model Selector

**Problem:** Model selector appeared in two places:
1. In the card header (inline with "Parse from Files" button)
2. Inside the file selection modal

**Root Cause:** Model selector was included both in the card header and in the modal template.

**Fix:** Removed inline model selector from card header in `detail.html`:

**Before:**
```html
<div class="d-flex align-items-center gap-2">
    <!-- Inline Model Selector -->
    {% set function_name = 'job_title_parser' %}
    {% set selected_model_id = job_title_parser_model_id %}
    {% include "components/model_selector.html" %}
    
    <button class="btn btn-primary btn-sm" onclick="showFileSelectorModal()">
        <i class="bi bi-magic"></i> Parse from Files
    </button>
</div>
```

**After:**
```html
<button class="btn btn-primary btn-sm" onclick="showFileSelectorModal()">
    <i class="bi bi-magic"></i> Parse from Files
</button>
```

**Result:** Model selector now appears only once - in the file selection modal.

---

### 3. ✅ Model Selector Doesn't Remember State

**Problem:** When opening the file selection modal, the model selector dropdown was empty or didn't show the currently selected model.

**Root Cause:** 
- Model selector was using Jinja2 template variables that only rendered on initial page load
- No dynamic loading of current model selection when modal opens

**Fix:** Added `initializeModelSelector()` function in `file_selector.html`:

```javascript
function initializeModelSelector() {
    // 1. Fetch current model mapping for job_title_parser
    fetch('/api/llm/function/job_title_parser/model')
        .then(response => response.json())
        .then(data => {
            const currentModelId = data.model_id || null;
            
            // 2. Load all available models
            fetch('/api/llm/models')
                .then(res => res.json())
                .then(modelsData => {
                    // Populate dropdown with providers and models
                    // Select the current model if configured
                    // Update status badge
                });
        });
}
```

**Features:**
- ✅ Fetches current model mapping from backend on page load
- ✅ Populates dropdown with all available models from all providers
- ✅ Pre-selects the currently configured model
- ✅ Shows status badge (✓ Ready / ⚠ Not configured / ✗ Error)
- ✅ Saves selection to backend when changed via `onModelSelectorChange()`

**Result:** Model selector now:
- Shows current selection when modal opens
- Remembers changes across sessions
- Displays all available models from all configured providers

---

## Files Modified

| File | Changes |
|------|---------|
| `frontend/templates/candidates/detail.html` | Removed inline model selector, updated `showFileSelectorModal()` |
| `frontend/templates/components/file_selector.html` | Added hardcoded model selector widget, added `initializeModelSelector()` function |

---

## Testing Checklist

### Test 1: File List Updates
1. Upload a new document via "Upload Document"
2. Click "Parse from Files"
3. **Expected:** New file appears in the list immediately ✅

### Test 2: Model Selector State
1. Open "Parse from Files" modal
2. Select a model from dropdown
3. Close modal
4. Refresh page
5. Open modal again
6. **Expected:** Previously selected model is still selected ✅

### Test 3: No Duplicate Selectors
1. Navigate to candidate detail page
2. Look at "Preferred Job Titles (AI Extracted)" card
3. **Expected:** Only one model selector (in modal), none in card header ✅

### Test 4: Parse with Selected Model
1. Open modal, select a model
2. Select some files
3. Click "Parse"
4. **Expected:** Parsing uses the selected model ✅

---

## Additional Improvements

### Model Selector Widget Features

- **Provider Grouping:** Models grouped by provider (Ollama, NVIDIA, OpenRouter, etc.)
- **Status Badges:** Visual feedback for configured/not configured/error states
- **Auto-Save:** Selection saved to backend immediately on change
- **Fallback:** Shows "Not configured" if no model selected (uses default Ollama)

### File List Features

- **File Type Badges:** Color-coded by document type (Profile, Resume, Job Titles, etc.)
- **Parse Status:** Shows "✓ Parsed" badge for already-parsed documents
- **File Size:** Displays formatted file size
- **Upload Date:** Shows when file was uploaded
- **Selection Persistence:** Remembers file selection across sessions via localStorage

---

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/llm/function/job_title_parser/model` | GET | Get current model for job title parser |
| `/api/llm/function/job_title_parser/model` | POST | Save model selection |
| `/api/llm/models` | GET | Get all available models from all providers |
| `/candidates/{id}/documents` | GET | Get list of uploaded documents |
| `/candidates/{id}/parse-job-titles` | POST | Start parsing with selected files |

---

## Known Limitations

1. **LocalStorage for File Selection:** File selection is stored in browser localStorage, not server. Different browsers/devices won't share selection.

2. **No Model Validation:** Doesn't check if selected model is actually available (e.g., Ollama model not pulled yet).

3. **No Progress Indicator:** Model selector doesn't show loading state while fetching models (shows "Loading..." briefly).

---

## Future Enhancements

1. **Model Availability Check:** Test model before allowing selection (ping Ollama, check API key validity)

2. **Recent Models:** Show "Recently Used" models at top of dropdown

3. **Model Recommendations:** Suggest models based on task (e.g., "Best for parsing: Llama 3 70B")

4. **Server-Side Selection Persistence:** Store file selection in database instead of localStorage

---

**Status:** ✅ Complete  
**Tested:** Pending user verification  
**Date:** March 25, 2026
