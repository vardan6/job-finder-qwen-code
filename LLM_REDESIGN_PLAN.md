# LLM Configuration Redesign Plan

**Created:** March 24, 2026  
**Goal:** Improve LLM model selection UX by adding inline dropdowns near AI action buttons while keeping the central LLM mappings page

---

## 📊 Current State Analysis

### Current AI Functions (5 total)

| Function Name | Display Name | Used By | Current Config |
|---------------|--------------|---------|----------------|
| `job_title_parser` | Job Title Parser (AI) | `/candidates/{id}/parse-job-titles` | LLM Function Mappings page |
| `skill_extractor` | Skill Extractor (AI) | `/candidates/{id}/skills/parse` | LLM Function Mappings page |
| `job_scorer` | Job Scorer (AI) | (Phase 3 - job search) | LLM Function Mappings page |
| `resume_matcher` | Resume-Job Matcher (AI) | (Phase 3 - job matching) | LLM Function Mappings page |
| `ai_chat` | AI Chat Assistant | `/chat` | LLM Function Mappings page |

### Current GUI Locations

1. **LLM Provider Configuration** (`/settings/llm`)
   - Configure providers (Ollama, NVIDIA, OpenRouter, etc.)
   - Add/remove models per provider
   - Set default provider

2. **LLM Function Mappings** (`/settings/functions`)
   - Map each function to a specific model
   - Reset to default (Ollama)
   - No per-button override

3. **Candidate Detail Page** (`/candidates/{id}`)
   - "Parse from Files" button (job titles) - line 265
   - No model selector next to button

4. **Skills Modal** (`/candidates/{id}/skills/modal`)
   - "Parse from Documents" button - line 44
   - No model selector next to button

---

## 🎯 Design Goals

1. **Keep LLM Mappings Page** - Central place to see/configure all function mappings
2. **Add Inline Model Selectors** - Dropdown next to each AI action button
3. **Unified Configuration** - "Last used" = "Default" (single source of truth)
4. **Visual Feedback** - Show which model is currently selected
5. **Minimal Disruption** - Reuse existing `LLMFunctionMapping` table

---

## 🏗️ Proposed Architecture

### Database Schema (No Changes Required)

We continue using the existing `LLMFunctionMapping` table:

```sql
CREATE TABLE llm_function_mappings (
    id INTEGER PRIMARY KEY,
    function_name TEXT UNIQUE,
    display_name TEXT,
    model_id INTEGER REFERENCES llm_models(id),
    is_active BOOLEAN DEFAULT 1
);
```

**Key Insight:** The `model_id` field serves as **both** "default" and "last used" - they are the same value.

### Component Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│  LLM Function Mappings Page (/settings/functions)       │
│  - Shows all 5 functions with current model selection   │
│  - Dropdown to change any function's model              │
│  - "Reset to Default" button                            │
└─────────────────────────────────────────────────────────┘
                          │
                          │ reads/updates
                          ▼
              ┌───────────────────────┐
              │ LLMFunctionMapping    │
              │ (database table)      │
              └───────────────────────┘
                          │
                          │ read by
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Inline Model Selectors (next to AI buttons)            │
│  - Job Titles: "Parse from Files" + dropdown            │
│  - Skills: "Parse from Documents" + dropdown            │
│  - Future: Job Scorer, Resume Matcher, etc.             │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 Implementation Tasks

### Phase 1: Backend API Enhancements

#### Task 1.1: Create Reusable Model Selector Component
**File:** `backend/routes/llm_functions.py` (new endpoint)

```python
@router.get("/api/llm/models")
async def get_available_models(db: Session = Depends(get_db)):
    """
    Get all available LLM models grouped by provider.
    Used by inline model selectors throughout the app.
    """
    providers = db.query(LLMProvider).filter(LLMProvider.is_active == True).all()
    
    result = []
    for provider in providers:
        provider_data = {
            "name": provider.name,
            "models": []
        }
        for model in provider.models:
            if model.is_active:
                provider_data["models"].append({
                    "id": model.id,
                    "name": model.model_name,
                    "display_name": model.display_name or model.model_name,
                    "is_default": model.is_default_for_provider
                })
        result.append(provider_data)
    
    return {"providers": result}


@router.get("/api/llm/function/{function_name}/model")
async def get_function_model(
    function_name: str,
    db: Session = Depends(get_db)
):
    """Get the currently configured model for a specific function"""
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name
    ).first()
    
    if not mapping or not mapping.model_id:
        return {"function_name": function_name, "model_id": None, "model": None}
    
    model = mapping.model
    return {
        "function_name": function_name,
        "model_id": mapping.model_id,
        "model": {
            "id": model.id,
            "name": model.model_name,
            "provider_name": model.provider.name
        }
    }


@router.post("/api/llm/function/{function_name}/model")
async def set_function_model(
    function_name: str,
    model_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Set the model for a specific function (updates LLMFunctionMapping)"""
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name
    ).first()
    
    if mapping:
        mapping.model_id = model_id
    else:
        # Create new mapping
        display_names = {
            "job_title_parser": "Job Title Parser",
            "skill_extractor": "Skill Extractor",
            # ... etc
        }
        mapping = LLMFunctionMapping(
            function_name=function_name,
            display_name=display_names.get(function_name, function_name),
            model_id=model_id
        )
        db.add(mapping)
    
    db.commit()
    
    return {"success": True, "function_name": function_name, "model_id": model_id}
```

---

### Phase 2: Frontend Components

#### Task 2.1: Create Reusable Model Selector Widget
**File:** `frontend/templates/components/model_selector.html`

```html
<!-- Reusable Model Selector Component -->
<!-- Usage: Include this next to any AI action button -->

<div class="model-selector-widget" data-function="{{ function_name }}">
    <select class="form-select form-select-sm" 
            style="width: 200px;"
            onchange="onModelSelectorChange('{{ function_name }}', this.value)">
        <option value="">-- Select Model --</option>
        {% for provider in providers %}
            {% if provider.models %}
            <optgroup label="{{ provider.name | title }}">
                {% for model in provider.models %}
                    {% if model.is_active %}
                    <option value="{{ model.id }}"
                            {% if selected_model_id == model.id %}selected{% endif %}>
                        {{ model.model_name }}
                        {% if model.is_default_for_provider %} (default){% endif %}
                    </option>
                    {% endif %}
                {% endfor %}
            </optgroup>
            {% endif %}
        {% endfor %}
    </select>
    <span class="model-selector-status ms-2">
        {% if selected_model_id %}
            <span class="badge bg-success">
                <i class="bi bi-check-circle"></i> Ready
            </span>
        {% else %}
            <span class="badge bg-warning">
                <i class="bi bi-exclamation-triangle"></i> Not configured
            </span>
        {% endif %}
    </span>
</div>

<script>
function onModelSelectorChange(functionName, modelId) {
    // Save selection to backend
    fetch(`/api/llm/function/${functionName}/model`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({model_id: modelId})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update status badge
            const widget = document.querySelector(`[data-function="${functionName}"]`);
            const statusSpan = widget.querySelector('.model-selector-status');
            statusSpan.innerHTML = `
                <span class="badge bg-success">
                    <i class="bi bi-check-circle"></i> Ready
                </span>
            `;
        }
    })
    .catch(error => console.error('Error saving model selection:', error));
}
</script>
```

---

#### Task 2.2: Update Job Titles Parser Button
**File:** `frontend/templates/candidates/detail.html`

**Current (line 262-270):**
```html
<div class="d-flex justify-content-between align-items-center">
    <h5 class="mb-0">
        <i class="bi bi-robot text-primary me-2"></i>
        Preferred Job Titles (AI Extracted)
    </h5>
    <button class="btn btn-primary btn-sm" type="button"
            hx-post="/candidates/{{ candidate.id }}/parse-job-titles"
            ...>
        <i class="bi bi-magic"></i> Parse from Files
    </button>
</div>
```

**New:**
```html
<div class="d-flex justify-content-between align-items-center">
    <h5 class="mb-0">
        <i class="bi bi-robot text-primary me-2"></i>
        Preferred Job Titles (AI Extracted)
    </h5>
    <div class="d-flex align-items-center gap-2">
        <!-- Inline Model Selector -->
        {% include "components/model_selector.html" with {
            'function_name': 'job_title_parser',
            'selected_model_id': job_title_parser_model_id
        } %}
        
        <!-- Parse Button -->
        <button class="btn btn-primary btn-sm" type="button"
                hx-post="/candidates/{{ candidate.id }}/parse-job-titles"
                ...>
            <i class="bi bi-magic"></i> Parse from Files
        </button>
    </div>
</div>
```

**Backend Change:** Update `backend/routes/candidate_parser.py` to load current model:
```python
@router.post("/{candidate_id}/parse-job-titles")
async def parse_job_titles(candidate_id: int, db: Session, request: Request):
    # Get current model for job_title_parser
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == "job_title_parser"
    ).first()
    current_model_id = mapping.model_id if mapping else None
    
    # Pass to template
    return templates.TemplateResponse("candidates/detail.html", {
        "request": request,
        "candidate": candidate,
        "job_title_parser_model_id": current_model_id,
        # ... other context
    })
```

---

#### Task 2.3: Update Skills Parser Button
**File:** `frontend/templates/skills/modal.html`

**Current (line 42-46):**
```html
<button class="btn btn-primary"
        hx-post="/candidates/{{ candidate.id }}/skills/parse"
        hx-target="#skillsModalBody"
        hx-swap="innerHTML">
    <i class="bi bi-robot"></i> Parse from Documents
</button>
```

**New:**
```html
<div class="d-flex align-items-center gap-2">
    <!-- Inline Model Selector -->
    {% include "components/model_selector.html" with {
        'function_name': 'skill_extractor',
        'selected_model_id': skill_extractor_model_id
    } %}
    
    <!-- Parse Button -->
    <button class="btn btn-primary"
            hx-post="/candidates/{{ candidate.id }}/skills/parse"
            hx-target="#skillsModalBody"
            hx-swap="innerHTML">
        <i class="bi bi-robot"></i> Parse from Documents
    </button>
</div>
```

**Backend Change:** Update `backend/routes/skills.py`:
```python
@router.get("/skills/modal", response_class=HTMLResponse)
async def skills_modal(request: Request, candidate_id: int, db: Session):
    # Get current model for skill_extractor
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == "skill_extractor"
    ).first()
    current_model_id = mapping.model_id if mapping else None
    
    return templates.TemplateResponse("skills/modal.html", {
        "request": request,
        "candidate": candidate,
        "skill_extractor_model_id": current_model_id,
        # ... other context
    })
```

---

### Phase 3: Enhanced LLM Function Mappings Page

#### Task 3.1: Update Functions Page Layout
**File:** `frontend/templates/settings/functions.html`

**Add "Last Used" Column:**

Current table shows:
- Function Name
- Select Model dropdown
- Reset button

New table shows:
- Function Name
- **Last Used** (timestamp - future enhancement)
- Select Model dropdown
- Reset button

**Template Changes:**
```html
<div class="list-group list-group-flush">
    {% for mapping in mappings %}
    <div class="list-group-item p-4">
        <div class="row align-items-center">
            <div class="col-md-4">
                <h6 class="mb-1">
                    <i class="bi bi-lightning-charge-fill text-warning me-2"></i>
                    {{ mapping.display_name or mapping.function_name }}
                </h6>
                <small class="text-muted">Function: <code>{{ mapping.function_name }}</code></small>
                <small class="text-muted d-block">
                    Last used: <span class="last-used-time">Never</span>
                </small>
            </div>
            <div class="col-md-8">
                <!-- Same dropdown as before, but with better styling -->
                ...
            </div>
        </div>
    </div>
    {% endfor %}
</div>
```

**Note:** "Last Used" timestamp tracking is optional future enhancement (would require adding `last_used_at` column to `LLMFunctionMapping`).

---

### Phase 4: Testing & Polish

#### Task 4.1: Test All Scenarios
1. ✅ Change model via inline selector → Verify LLMFunctionMapping updated
2. ✅ Change model via functions page → Verify inline selector reflects change
3. ✅ Parse job titles → Verify uses selected model
4. ✅ Parse skills → Verify uses selected model
5. ✅ Reset mapping → Verify both inline selector and functions page show default

#### Task 4.2: Add Visual Feedback
- Show loading spinner when changing model
- Show success/error toast notifications
- Add tooltip showing model details on hover

#### Task 4.3: Documentation
- Update `QWEN.md` with new LLM configuration workflow
- Add inline comments in templates

---

## 📅 Implementation Order

| Priority | Task | Estimated Time | Dependencies |
|----------|------|----------------|--------------|
| 1 | Task 1.1: Backend API endpoints | 30 min | None |
| 2 | Task 2.1: Model selector component | 30 min | Task 1.1 |
| 3 | Task 2.2: Job titles inline selector | 20 min | Task 2.1 |
| 4 | Task 2.3: Skills inline selector | 20 min | Task 2.1 |
| 5 | Task 3.1: Enhanced functions page | 30 min | None |
| 6 | Task 4: Testing & polish | 30 min | All above |

**Total Estimated Time:** ~2.5 hours

---

## 🎨 UI Mockups

### Inline Model Selector (Next to Parse Button)

```
┌────────────────────────────────────────────────────────────┐
│  Preferred Job Titles (AI Extracted)                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  [Model: llama3 (Ollama) ▼]  [🪄 Parse from Files]        │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Expanded Dropdown

```
┌────────────────────────────────────────────────┐
│ Model: llama3 (Ollama)              ▼          │
├────────────────────────────────────────────────┤
│ Ollama                                         │
│   ├─ llama3 (default)                          │
│   ├─ llama3.1                                  │
│   └─ mistral                                   │
│ NVIDIA                                         │
│   ├─ meta/llama3-70b-instruct (free)           │
│   └─ qwen/qwen3-coder-480b-a35b-instruct       │
│ OpenRouter                                     │
│   └─ meta-llama/llama-3-70b-instruct           │
└────────────────────────────────────────────────┘
```

### LLM Functions Page (Enhanced)

```
┌─────────────────────────────────────────────────────────────┐
│  LLM Function Mappings                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Job Title Parser (AI)         [llama3 ▼]  [↺ Reset]       │
│  Function: job_title_parser    Last used: 2 min ago        │
│                                                             │
│  Skill Extractor (AI)          [qwen3-coder:480b ▼]        │
│  Function: skill_extractor     Last used: 5 min ago        │
│                                                             │
│  Job Scorer (AI)               [Select Model ▼] [↺ Reset]  │
│  Function: job_scorer          Last used: Never            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Technical Notes

### 1. Single Source of Truth
- `LLMFunctionMapping.model_id` is the **only** model configuration
- No separate "default" vs "last used" - they are the same
- Changing model anywhere updates the database immediately

### 2. Backward Compatibility
- Existing code continues to work (reads from `LLMFunctionMapping`)
- `get_llm_for_function()` helper already exists in `llm_service.py`
- No breaking changes to existing AI parsing logic

### 3. Future Enhancements (Optional)
- Add `last_used_at` timestamp to `LLMFunctionMapping`
- Track API usage/costs per function
- Add "Test Model" button next to each selector
- Show model capabilities (context window, speed, cost)

---

## ✅ Acceptance Criteria

- [ ] Inline model selector appears next to "Parse from Files" button
- [ ] Inline model selector appears next to "Parse from Documents" button
- [ ] Changing model in selector immediately updates database
- [ ] LLM Functions page shows current selections
- [ ] Changing model on functions page updates inline selectors
- [ ] AI parsing uses the currently selected model
- [ ] Reset button works and sets back to default Ollama
- [ ] Visual feedback shows which model is active

---

## 🚀 Next Steps

1. **Review this plan** - Confirm approach makes sense
2. **Start with Task 1.1** - Create backend API endpoints
3. **Build incrementally** - Test each component before moving to next
4. **Document changes** - Update `QWEN.md` when complete

---

**END OF REDESIGN PLAN**
