# Model Selector — Current Functionality

**Date:** March 24, 2026

---

## ✅ Current Functionality

### What's Stored
- **Last selected model** is persisted to database
- Stored in `LLMFunctionMapping` table
- Per function (e.g., `job_title_parser`, `skill_extractor`)

### What's Displayed
- **Status badge** shows if model is configured:
  - 🟢 Green "Ready" - Model is configured
  - 🟡 Yellow "Not configured" - No model selected
- **Dropdown** - Shows all available models
- **Selected value** - Last used model is highlighted in dropdown

### Data Flow
```
User selects model
    ↓
JavaScript saves to backend (POST /api/llm/function/{name}/model)
    ↓
Backend saves to LLMFunctionMapping table
    ↓
Page reload → Backend reads from database
    ↓
Template renders with selected_model_id
    ↓
JavaScript highlights selected model in dropdown
```

---

## 📊 Example

**Job Title Parser:**
- Last selected: `qwen3-coder:480b-cloud` (ID: 3)
- Database: `LLMFunctionMapping { function_name: "job_title_parser", model_id: 3 }`
- UI shows:
  - Dropdown: "qwen3-coder:480b-cloud" is selected
  - Badge: 🟢 "Ready"

**Skill Extractor:**
- Last selected: `null` (never set)
- Database: `LLMFunctionMapping { function_name: "skill_extractor", model_id: null }`
- UI shows:
  - Dropdown: No selection
  - Badge: 🟡 "Not configured"

---

## 🔧 Recent Improvements

### Added: Model ID in Status Badge
**Before:**
```html
<span id="status-job_title_parser">
    <span class="badge bg-success">✓ Ready</span>
</span>
```

**After:**
```html
<span id="status-job_title_parser" data-model-id="3">
    <span class="badge bg-success">✓ Ready</span>
</span>
```

**Why:** JavaScript now reads `data-model-id` to highlight the selected model in dropdown.

### Added: Dropdown Auto-Select
**JavaScript:**
```javascript
// Get currently selected model ID from status badge
const currentModelId = statusElement?.getAttribute('data-model-id');

// When populating dropdown...
if (currentModelId && model.id == currentModelId) {
    option.selected = true;  // Highlight last used model
}
```

---

## 💾 Database Schema

```sql
CREATE TABLE llm_function_mappings (
    id INTEGER PRIMARY KEY,
    function_name TEXT UNIQUE,      -- e.g., "job_title_parser"
    display_name TEXT,              -- e.g., "Job Title Parser"
    model_id INTEGER,               -- References llm_models.id
    is_active BOOLEAN DEFAULT 1
);
```

**Example Data:**
```
id | function_name      | display_name        | model_id | is_active
---|-------------------|---------------------|----------|----------
1  | job_title_parser  | Job Title Parser    | 3        | 1
2  | skill_extractor   | Skill Extractor     | NULL     | 1
3  | ai_chat           | AI Chat Assistant   | 1        | 1
```

---

## 🎯 User Experience

### First Time Use
1. User sees dropdown with all models
2. Status badge shows "Not configured" 🟡
3. User selects model
4. Badge changes to "Ready" 🟢
5. Selection saved to database

### Returning User
1. Dropdown shows last selected model highlighted
2. Status badge shows "Ready" 🟢
3. User can change model if desired
4. New selection saved immediately

### No Selection
1. Dropdown shows "-- Select Model --"
2. Status badge shows "Not configured" 🟡
3. AI parsing still works (uses fallback Ollama)
4. User can proceed without selecting

---

## 📝 Summary

**Q: Does it remember the last selected value?**  
✅ **Yes** - Saved to database in `LLMFunctionMapping` table

**Q: Is there a default value?**  
✅ **Yes and No** - 
- No hardcoded default
- Last selected value acts as "default"
- If never selected, shows "-- Select Model --"

**Q: What happens if no model is selected?**  
✅ **Fallback logic** - Uses direct Ollama call (`ollama/llama3`)

**Q: Where is it stored?**  
✅ **Database** - `llm_function_mappings` table, `model_id` column

---

**The model selector fully persists user preferences!** 🎉
