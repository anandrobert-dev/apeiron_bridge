# Apeiron Bridge RA&C — Phase 1 Bug Fix Prompt

**Status:** Phase 1 scaffold confirmed working. Three bugs observed during first live test.
Fix all three in a single commit. Do not refactor anything else.

---

## Bug 1 — `NameError: name 're' is not defined` (CRITICAL — crashes on file browse)

**File:** `app/rate_analysis_comparison/ui/rac_window.py`
**Line:** 294 (approximately) — inside `browse_agreements()`
**Error:**
```
NameError: name 're' is not defined. Did you mean: 'e'?
```

**Root cause:** `import re` is missing from the top of `rac_window.py`.

**Fix:** Add `import re` to the import block at the top of the file, alongside the other
standard library imports. Do not add it inside the function — it belongs at module level
with everything else.

**Verify:** After fix, upload two PDF files via the Browse button without triggering any
NameError. The file names should appear in the upload list.

---

## Bug 2 — Card title and tile titles clipped (UI text overflow)

### 2A. Home screen card (Image 1)
**File:** `app/ui/welcome.py`
**Symptom:** The new "Rate Analysis & Comparison" card shows "ate Analysis & Compariso"
— the label is truncating instead of wrapping.

**Root cause:** The card title `QLabel` does not have word wrap enabled and/or the label
has a fixed width narrower than the text. The other two cards ("SOA Reconciliation" = 17
chars, "Multi-File Comparison" = 22 chars) happen to fit. "Rate Analysis & Comparison"
= 26 chars and overflows.

**Fix — two things together:**
1. On the title `QLabel` for the RA&C card, call `setWordWrap(True)`.
2. Set the title `QLabel` minimum width to match the card width, using
   `setMinimumWidth(card_width)` or by using a layout that lets it expand.
   Do NOT set a fixed pixel width that is less than the card width.
3. If the other cards use a shared helper function to build card widgets, apply
   `setWordWrap(True)` to ALL card title labels — this is a latent bug in every card,
   just not triggered yet. Fix them all now.

**Do NOT** shrink the font size to make it fit. The font must match the other cards exactly.

### 2B. Mode selector tiles (Image 2)
**File:** `app/rate_analysis_comparison/ui/rac_window.py`
**Symptom:** The "Terms & Conditions Comparison" tile shows "s & Conditions Compar"
— same truncation problem inside the mode selector.

**Fix:**
1. All three tile title `QLabel` widgets must have `setWordWrap(True)` enabled.
2. Each tile must expand to its content. If tiles use a fixed height, increase it enough
   to show two lines of title text (e.g. "Terms &\nConditions Comparison").
3. Tile widths must be equal and large enough to contain the longest title
   ("Terms & Conditions Comparison" ≈ 30 characters). At the project's standard font size
   (~13–14px), this needs approximately 200px minimum tile width. Check with
   `setMinimumWidth(200)` or use a stretching layout.
4. Do NOT hard-code abbreviated titles like "T&C Comparison". The full name must appear.
   If it needs two lines, that is correct — two lines is better than truncation.

**Verify:** At the app's default window size, all three tile titles are fully readable with
zero clipping. Resize the window narrower — titles should wrap, not truncate.

---

## Bug 3 — PostgreSQL not running: graceful degradation (IMPORTANT — affects usability)

**Symptom:**
```
Error fetching carriers for autocomplete: (psycopg.OperationalError) connection failed:
connection to server at "127.0.0.1", port 5432 failed: Connection refused
```

This error appears in the terminal every time the upload screen is opened. The app does
not crash, but the error is silent to the user — they see no feedback about why
autocomplete is not working.

**Root cause:** PostgreSQL is not running as a system service. The app tries to connect,
fails silently (terminal only), and continues in a degraded state the user cannot diagnose.

**This is a two-part fix: code fix + install fix.**

---

### Part A — Code fix: surface the DB status in the UI

**File:** `app/rate_analysis_comparison/db/engine.py`
**Add:** A module-level function `is_db_available() -> bool` that returns `True` if the
last connection check succeeded, `False` otherwise. This must NOT raise — it catches the
exception and returns `False`. It must be cheap to call (cache the result; re-check at
most once per app launch).

```python
_db_available: bool = False

def check_db_connection() -> bool:
    """Attempt a lightweight connection check. Returns True if reachable."""
    global _db_available
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _db_available = True
    except Exception:
        _db_available = False
    return _db_available

def is_db_available() -> bool:
    return _db_available
```

**File:** `app/rate_analysis_comparison/ui/rac_window.py`

At the top of `RateAnalysisComparisonWindow.__init__()`, after building the UI, call
`check_db_connection()`. If it returns `False`:
1. Show a non-blocking warning banner at the top of the window (amber/yellow background,
   visible but not a blocking dialog). The banner text must be:

   ```
   PostgreSQL is not running. Carrier autocomplete and nearby-lane matching are disabled.
   To enable: open a terminal and run:  sudo systemctl start postgresql
   Then re-launch the application.
   ```

2. Disable (grey out, not hide) any UI elements that strictly require the DB:
   - Carrier name autocomplete field → disable autocomplete, allow free-text entry
   - Nearby-lane matching toggle → disabled with tooltip "Requires database"

3. Do NOT disable parsing or file upload. The app must still be able to parse files and
   show raw results without the DB. The DB is required for autocomplete and
   nearby-lane lookup, not for basic parsing.

4. The terminal error `"Error fetching carriers for autocomplete: ..."` must be replaced
   with a `logger.warning(...)` call (no raw `print`, no unhandled exception to terminal).
   The user sees the banner; the developer sees the log.

**File:** `app/rate_analysis_comparison/ui/rac_window.py`
In the carrier autocomplete fetch (wherever the `psycopg.OperationalError` is currently
being caught and printed), change to:

```python
try:
    carriers = get_carriers()          # existing DB call
    self.carrier_name_input.addItems(carriers)
except Exception as e:
    logger.warning("DB unavailable for carrier autocomplete: %s", e)
    # banner is already shown; no further action needed here
```

---

### Part B — Install fix: enable PostgreSQL to auto-start on boot

**File:** `install.sh`

After the existing `apt install postgresql postgresql-contrib` step, add:

```bash
# Enable PostgreSQL to start automatically on boot and start it now
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Verify it is running before proceeding
if ! sudo systemctl is-active --quiet postgresql; then
    echo "ERROR: PostgreSQL failed to start. Check: sudo journalctl -xe"
    exit 1
fi
```

**File:** `BUILD_UBUNTU_22_04.md`

Add a "PostgreSQL Service" section documenting:
- How to check status: `sudo systemctl status postgresql`
- How to start manually: `sudo systemctl start postgresql`
- How to enable on boot: `sudo systemctl enable postgresql`
- What the error looks like if not running (copy the connection refused message)

---

## Verification checklist

After all three fixes:

1. Launch the app from a cold start (`venv/bin/python main.py`).
2. **With PostgreSQL not running:**
   - Home screen card shows "Rate Analysis & Comparison" in full — no clipping.
   - Clicking Launch opens the mode selector. All three tile titles show in full.
   - Clicking "Rate Comparison" opens the upload screen.
   - A yellow/amber warning banner is visible explaining the DB is not running.
   - Carrier name field accepts free text but shows no autocomplete suggestions.
   - Browse for two PDF files — no NameError, files appear in the list.
   - No raw tracebacks in the terminal (warnings in the log are acceptable).
3. **Start PostgreSQL (`sudo systemctl start postgresql`) and re-launch:**
   - No warning banner.
   - Carrier autocomplete works.
   - All previous functionality intact.
4. **Run the full test suite:**
   ```
   venv/bin/python -m unittest discover tests
   ```
   All 8 tests must still pass. Do not break existing tests.

---

## What NOT to change

- Do not modify `app/soa_reconciliation/` or `app/multi_file_comparison/`.
- Do not change the parsing logic, DB schema, or agent code.
- Do not add new dependencies.
- Do not rename any files or classes.
- These are targeted fixes only.
