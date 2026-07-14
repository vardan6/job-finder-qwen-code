# Job Search Page Redesign - Implementation Summary

**Date:** March 29, 2026  
**Status:** ✅ Complete

---

## Overview

The job search page (`/jobs/search`) has been completely redesigned to **automatically use candidate profile data** instead of requiring manual input. All search parameters now come from the candidate's setup:

- ✅ **Job Titles** → Auto-generated search query
- ✅ **Skills** → Used for AI analysis matching
- ✅ **Location** → Pre-filled from candidate profile
- ✅ **Platform Accounts** → Auto-detected connection status
- ✅ **Remote Preference** → Loaded from candidate settings
- ✅ **LLM Configuration** → AI analysis auto-enabled if configured

---

## Key Changes

### 1. Backend Changes

#### New API Endpoint: `/jobs/api/candidates/{candidate_id}/search-config`

**Purpose:** Returns auto-generated search configuration for a candidate.

**Response:** HTML partial (for HTMX swapping) containing:
- Search query (combined from active job titles)
- Location (from candidate profile)
- Platform status (connected/disconnected for each platform)
- AI analysis availability (based on LLM provider configuration)
- Statistics (job titles count, skills count)

**Code Location:** `backend/routes/jobs.py`

```python
@router.get("/api/candidates/{candidate_id}/search-config")
async def get_candidate_search_config(...)
```

#### Updated Search Form Handler

**Changes:**
- Now accepts string booleans (`"true"`/`"false"`) from form
- Parses `analyze`, `headless`, and `remote_only` as strings
- Logs search parameters including boolean flags

**Code Location:** `backend/routes/jobs.py` - `perform_job_search()`

---

### 2. Frontend Changes

#### New Template: `jobs/search.html`

**Purpose:** Main search page with candidate selector and auto-loaded config.

**Features:**
- Candidate dropdown selector
- HTMX-based dynamic loading of search config
- Auto-loads config on page load if candidate is pre-selected via URL parameter
- Clean, modern UI with gradient preview card

**Key JavaScript Function:**
```javascript
function loadSearchConfig(candidateId) {
    htmx.ajax('GET', `/jobs/api/candidates/${candidateId}/search-config`, {
        target: '#searchConfigPanel',
        swap: 'innerHTML'
    });
}
```

#### New Template: `jobs/search_config_partial.html`

**Purpose:** HTMX partial rendered when candidate is selected.

**Sections:**

1. **Search Preview Card** (Gradient header)
   - Job titles count
   - Skills count
   - Link to edit candidate profile

2. **Search Query Card**
   - Auto-generated query from job titles
   - Info message explaining auto-generation

3. **Platform Status Cards**
   - LinkedIn card (green if connected, red if not)
   - Glassdoor card (green if connected, red if not)
   - Toggle switches (disabled if not connected)

4. **Location & Remote Settings**
   - Location input (pre-filled, editable)
   - Remote-only toggle (from candidate preferences)

5. **AI Analysis Card**
   - Shows LLM configuration status
   - Shows skills count for matching
   - Toggle (disabled if no LLM configured)

6. **Max Jobs Input**
   - Default: 20
   - Range: 1-100

7. **Advanced Options** (Collapsible)
   - Custom query override (textarea)
   - Headless mode toggle
   - Human-readable descriptions

8. **Candidate Summary Sidebar**
   - Name, job titles count, skills count
   - Location, remote-only status

9. **Tips Sidebar**
   - Search strategy explanation
   - Remote jobs info
   - Rate limits warning

10. **Confirmation Modal**
    - Shows search summary before starting
    - Estimated time warning
    - Cancel/Start buttons

11. **Progress Modal**
    - Spinner animation
    - "Do not close this page" message

---

## User Flow

### Before (Old Design)

1. User visits `/jobs/search`
2. Manually selects candidate from dropdown
3. Manually types search query
4. Manually enters location
5. Manually checks platform checkboxes
6. Manually toggles AI analysis
7. Clicks "Start Search"

**Problem:** All candidate data already exists but wasn't used!

### After (New Design)

1. User visits `/jobs/search?candidate_id=1` (or selects from dropdown)
2. **Search config auto-loads from candidate profile**
3. **Query pre-filled from job titles**
4. **Location pre-filled from profile**
5. **Platforms auto-selected based on connected accounts**
6. **AI analysis auto-enabled if LLM configured**
7. User reviews auto-generated config (can override in Advanced Options)
8. Clicks "Start Search" → Confirms in modal → Search begins

**Benefit:** Zero manual input required!

---

## Search Parameter Mapping

| Candidate Data | Search Parameter | How Used |
|----------------|------------------|----------|
| `candidate.job_titles` (active) | `query` | Combined: "Staff SDET, Principal SDET, Lead SDET" |
| `candidate.location` | `location` | Pre-filled: "United States" or "Armenia" |
| `candidate.preferences.remote_only` | `remote_only` | Toggle state |
| `candidate.platform_accounts` | `platforms` | Only connected accounts shown as available |
| `candidate.skills` (enabled) | AI analysis | Used for job matching score |
| LLMProvider (global default) | `analyze` | Auto-enabled if LLM configured |

---

## Technical Details

### HTMX Integration

**Dynamic Loading:**
```html
<select onchange="loadSearchConfig(this.value)">
  <option value="1">Vardan Arakelyan</option>
</select>

<div id="searchConfigPanel">
  <!-- Loaded via HTMX AJAX -->
</div>

<script>
function loadSearchConfig(candidateId) {
    htmx.ajax('GET', `/jobs/api/candidates/${candidateId}/search-config`, {
        target: '#searchConfigPanel',
        swap: 'innerHTML'
    });
}
</script>
```

### Form Submission

**Hidden Form (not visible to user):**
```html
<form id="searchForm" hx-post="/jobs/search" style="display: none;">
    <input name="candidate_id" value="1">
    <input name="query" id="hiddenQuery" value="Staff SDET, Principal SDET">
    <input name="location" id="hiddenLocation" value="United States">
    <input name="remote_only" id="hiddenRemoteOnly" value="true">
    <input name="max_jobs" id="hiddenMaxJobs" value="20">
    <input name="analyze" id="hiddenAnalyze" value="true">
    <input name="headless" id="hiddenHeadless" value="false">
    <!-- Platforms added dynamically from checkboxes -->
</form>
```

**JavaScript Submission Flow:**
1. User clicks "Start Job Search" button
2. `startSearch()` validates and updates hidden fields from visible inputs
3. Confirmation modal shows summary
4. User confirms → `submitSearch()` called
5. Platform checkboxes added to form dynamically
6. HTMX submits form via AJAX
7. Progress modal shown
8. Server processes search (5-15 minutes)
9. Result page displayed

---

## Files Changed

### Backend
- `backend/routes/jobs.py`
  - Added: `get_candidate_search_config()` endpoint
  - Modified: `perform_job_search()` to parse string booleans
  - Added: Import for `LLMProvider` model

### Frontend
- `frontend/templates/jobs/search.html` (Complete rewrite)
  - New candidate selector with JavaScript integration
  - Search config panel with HTMX auto-load
  - Rate limit info section
  - Removed: Manual input form

- `frontend/templates/jobs/search_config_partial.html` (New file)
  - Search preview card
  - Platform status cards
  - Query, location, remote settings
  - AI analysis toggle
  - Advanced options collapsible
  - Confirmation and progress modals
  - JavaScript for form submission

---

## Testing

### Manual Test Steps

1. **Test with candidate pre-selected:**
   ```
   http://localhost:9002/jobs/search?candidate_id=1
   ```
   Expected: Config auto-loads via `/jobs/api/candidates/1/search-config`, shows 16 job titles, 43 skills

2. **Test candidate switch:**
   - Select different candidate from dropdown
   - Expected: Config reloads with new candidate data

3. **Test platform status:**
   - Candidate with connected LinkedIn account
   - Expected: LinkedIn card green, checkbox enabled
   - Candidate without Glassdoor account
   - Expected: Glassdoor card red, checkbox disabled

4. **Test AI analysis toggle:**
   - Candidate with LLM configured
   - Expected: Toggle enabled, shows "LLM configured (43 skills)"
   - Candidate without LLM
   - Expected: Toggle disabled, shows "No LLM provider configured"

5. **Test advanced options:**
   - Click "Advanced Options"
   - Expected: Collapsible panel opens
   - Custom query textarea editable
   - Headless mode toggle functional

6. **Test form submission:**
   - Click "Start Job Search"
   - Expected: Confirmation modal appears with summary
   - Click "Start Search"
   - Expected: Progress modal appears

---

## Future Enhancements

### Potential Improvements

1. **Multi-Query Search:**
   - Search each job title separately
   - Better coverage, slower execution

2. **Query Builder:**
   - Visual job title selector
   - Include/exclude specific titles
   - Priority weighting

3. **Saved Searches:**
   - Save search configurations
   - Schedule recurring searches
   - Email notifications for new jobs

4. **Platform-Specific Settings:**
   - LinkedIn: Salary range, experience level
   - Glassdoor: Company ratings, job type

5. **Search History:**
   - View past searches
   - Re-run previous searches
   - Compare results over time

---

## Migration Notes

- **No database schema changes required**
- **Backward compatible** - old form fields still accepted
- **Existing searches unaffected**
- **Candidate data unchanged**

---

## Known Limitations

1. **Remote Filter:**
   - LinkedIn: Hardcoded `f_AL=true` in scraper (always remote)
   - Glassdoor: No built-in remote filter, relies on AI analysis
   - Candidate `remote_only` preference currently informational only

2. **Platform Selection:**
   - Disabled platforms (not connected) cannot be selected
   - User must connect platform accounts first

3. **Query Length:**
   - Limited to 5 job titles to avoid URL length issues
   - Could be enhanced with pagination or batching

---

## Conclusion

The job search page redesign **eliminates manual input** by leveraging existing candidate profile data. Users can now start a search with a single click, while still having the option to override parameters via Advanced Options.

**Key Benefits:**
- ✅ Faster search initiation (no manual input)
- ✅ Consistent searches (uses standardized job titles)
- ✅ Better UX (visual platform status, clear summaries)
- ✅ Safer searches (auto-uses connected accounts only)
- ✅ AI-ready (auto-enables analysis when LLM configured)
