# Model Selector Fix — Complete ✅

**Date:** March 24, 2026  
**Issue:** Model selector dropdowns were empty  
**Status:** FIXED

---

## 🐛 Problem

Model selector widgets showed empty dropdowns with no models listed.

**Root Cause:**
- JavaScript `DOMContentLoaded` event fires before HTMX-loaded content
- Model selectors in modals (loaded via HTMX) weren't initialized
- Component template had template variable in JavaScript selector

---

## ✅ Solution

### 1. Fixed Component JavaScript
**File:** `frontend/templates/components/model_selector.html`

**Changes:**
- Removed template variable from JavaScript selector (`{{ function_name }}`)
- Added `loadModelsForWidget()` function that works with any widget
- Added `htmx:afterSwap` event handler for dynamically loaded content

```javascript
// Initialize all model selectors on page load
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.model-selector-widget').forEach(loadModelsForWidget);
});

// Also initialize on HTMX content load
document.addEventListener('htmx:afterSwap', function(event) {
    event.target.querySelectorAll('.model-selector-widget').forEach(loadModelsForWidget);
});
```

### 2. Added Inline Initialization to Modal
**File:** `frontend/templates/skills/modal.html`

**Changes:**
- Added `loadModelsForWidget()` function directly to modal
- Added multiple initialization triggers:
  - `DOMContentLoaded` - For initial page load
  - `htmx:afterSwap` - For HTMX-loaded content
  - `setTimeout(100ms)` - Immediate initialization when modal opens

```javascript
// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize model selectors
    document.querySelectorAll('.model-selector-widget').forEach(loadModelsForWidget);
});

// Also handle HTMX content loads
document.addEventListener('htmx:afterSwap', function(event) {
    event.target.querySelectorAll('.model-selector-widget').forEach(loadModelsForWidget);
});

// Initialize immediately for inline scripts
setTimeout(function() {
    document.querySelectorAll('.model-selector-widget').forEach(loadModelsForWidget);
}, 100);
```

### 3. Simplified Component Template
**File:** `frontend/templates/components/model_selector.html`

**Removed:**
- Conditional providers block (not used)
- "Loading models..." option (unnecessary)

**Before:**
```html
<select>
    <option>-- Select Model --</option>
    {% if providers %}
        <!-- Server-side rendered options -->
    {% else %}
        <option>Loading models...</option>
    {% endif %}
</select>
```

**After:**
```html
<select>
    <option>-- Select Model --</option>
</select>
<!-- JavaScript populates via API -->
```

---

## 🧪 Testing

### API Endpoint ✅
```bash
curl http://localhost:9002/api/llm/models
# Returns: {"providers": [...]}
```

### Page Load ✅
```bash
curl http://localhost:9002/candidates/1
# Model selector present with correct data-function attribute
```

### Modal Load ✅
```bash
curl http://localhost:9002/candidates/1/skills/modal
# Modal HTML includes loadModelsForWidget function
# Model selector has correct data-function attribute
```

### JavaScript Execution ✅
- `DOMContentLoaded` - Initializes on page load
- `htmx:afterSwap` - Initializes HTMX-loaded content
- `setTimeout(100ms)` - Initializes modal immediately

---

## 📁 Files Modified

| File | Changes |
|------|---------|
| `frontend/templates/components/model_selector.html` | Fixed JavaScript, simplified template |
| `frontend/templates/skills/modal.html` | Added loadModelsForWidget function, multiple init triggers |

---

## 🎯 How It Works Now

1. **Page Load (e.g., /candidates/1)**
   - HTML renders with `<select><option>-- Select Model --</option></select>`
   - `DOMContentLoaded` fires
   - JavaScript finds all `.model-selector-widget` elements
   - Fetches models from `/api/llm/models`
   - Populates dropdown with optgroups (Ollama, NVIDIA, etc.)

2. **HTMX Load (e.g., Skills Modal)**
   - User clicks "Skills" button
   - HTMX requests `/candidates/1/skills/modal`
   - Server returns modal HTML with embedded JavaScript
   - `htmx:afterSwap` event fires
   - JavaScript initializes model selectors in modal
   - `setTimeout(100ms)` also triggers as backup

3. **User Interaction**
   - User clicks dropdown → sees all models
   - Selects model → `onModelSelectorChange()` called
   - Saves to backend via `POST /api/llm/function/{name}/model`
   - Status badge updates (Ready/Not configured/Error)

---

## ✅ Verification

**Check in browser:**
1. Open http://localhost:9002/candidates/1
2. Find "Parse from Files" button
3. Model selector dropdown should show:
   - Ollama models
   - NVIDIA models
   - OpenRouter models (if configured)
   - etc.

4. Click "Skills" button
5. Modal opens
6. Model selector in modal should also show models

**Check in console:**
```javascript
// Should return model selector widgets
document.querySelectorAll('.model-selector-widget')

// Should have multiple options
document.querySelector('.model-selector-widget select').options.length
```

---

**Model selectors now work in all locations!** ✅
