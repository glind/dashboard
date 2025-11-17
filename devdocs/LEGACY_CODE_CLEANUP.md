# Legacy Code Cleanup

**Date:** November 17, 2025

## Summary
Removed **6,201 lines** of legacy embedded HTML from `src/main.py` to prevent confusion and ensure a single source of truth for the dashboard UI.

## Changes Made

### 1. Removed Embedded HTML from main.py
- **Before:** 11,597 lines
- **After:** 5,396 lines
- **Removed:** 6,201 lines (lines 453-6653)

The embedded HTML was a fallback that was never used because the modern template exists. This caused confusion when updates were made to the wrong location.

### 2. Single Source of Truth
**Dashboard UI is now ONLY in:**
- `/src/templates/dashboard_modern.html` - HTML structure
- `/src/static/dashboard.js` - JavaScript functionality
- `/src/static/dashboard*.js` - Feature-specific JS modules

**NEVER edit HTML in:**
- ❌ `src/main.py` (no longer contains HTML)

### 3. Template Loading Logic
Updated the dashboard endpoint to:
1. Load from `templates/dashboard_modern.html` ONLY
2. Return 500 error if template not found (no fallback)
3. Removed all embedded HTML strings

```python
@app.get("/", response_class=HTMLResponse)
async def dashboard(code: str = None, state: str = None, error: str = None):
    """Serve the main dashboard page or handle OAuth callbacks"""
    
    # Serve the modern template (ONLY SOURCE OF TRUTH)
    src_dir = Path(__file__).parent
    template_path = src_dir / "templates" / "dashboard_modern.html"
    
    if not template_path.exists():
        return HTMLResponse(content="<h1>Error: Dashboard template not found</h1>", status_code=500)
    
    with open(template_path, 'r') as f:
        return HTMLResponse(content=f.read())
```

## Benefits

1. **No More Confusion:** Only one place to edit the dashboard UI
2. **Smaller File:** main.py is now 54% smaller (5,396 vs 11,597 lines)
3. **Faster Development:** Clear separation between backend (main.py) and frontend (templates/)
4. **Better Maintainability:** Template files are easier to work with than embedded strings

## File Structure (After Cleanup)

```
src/
├── main.py                      # Backend logic ONLY (no HTML)
├── templates/
│   ├── dashboard_modern.html    # ✅ Main dashboard UI
│   └── leads.html               # Leads page UI
└── static/
    ├── dashboard.js             # ✅ Main dashboard JS
    ├── dashboards_modern.js     # Dashboards feature
    ├── leads.js                 # Leads feature
    ├── leads_modern.js          # Leads modern version
    └── tasks.js                 # Tasks feature
```

## Verification

After cleanup, the dashboard:
- ✅ Starts successfully
- ✅ Serves from template correctly
- ✅ Contains all new features (Google auth button, suggested todos, dismiss alerts)
- ✅ No syntax errors
- ✅ File size reduced by 6,201 lines

## Prevention

To prevent this from happening again:
1. **Never** add HTML to Python files
2. **Always** use template files for UI
3. **No fallback** HTML - if template is missing, show error instead of outdated content
4. All HTML edits go to `src/templates/`
5. All JS edits go to `src/static/`
