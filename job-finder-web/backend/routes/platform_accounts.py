"""
Platform Accounts Routes - Manage LinkedIn/Glassdoor credentials
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
import json
import re
import shutil
from typing import Optional

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.platform_account import PlatformAccount
from backend.security import decrypt_data, encrypt_json, decrypt_json, encrypt_data
from backend.services.browser_manager import get_browser_pool
from backend.services.rate_limiter import normalize_linkedin_settings

router = APIRouter(prefix="/candidates/{candidate_id}/accounts", tags=["platform_accounts"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)
PLATFORM_LOGIN_URLS = {
    "linkedin": "https://www.linkedin.com/login",
    "glassdoor": "https://www.glassdoor.com/profile/login_input.htm",
    "indeed": "https://secure.indeed.com/auth",
}


VALID_PLATFORMS = {"linkedin", "glassdoor", "indeed"}


def _get_cookie_file_path(candidate: Candidate, platform: str) -> Path:
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"Invalid platform: {platform}")
    from backend.config import DATA_DIR
    return DATA_DIR / "cookies" / f"{candidate.uuid}_{platform}.enc"


def _get_manual_login_profile_path(candidate: Candidate, platform: str) -> Path:
    """Return the transient, per-account Chromium profile for manual login."""
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"Invalid platform: {platform}")
    from backend.config import DATA_DIR
    return DATA_DIR / "browser-login-profiles" / f"{candidate.uuid}_{platform}"


def _manual_login_session_key(candidate: Candidate, platform: str) -> str:
    return f"{candidate.uuid}:{platform}"




def _email_from_value(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip())
    return match.group(0) if match else None


def _detect_account_email(state: dict) -> Optional[str]:
    """Read an email only when a provider labels it as identity data."""
    for origin in state.get("origins", []):
        if not isinstance(origin, dict):
            continue
        for item in origin.get("localStorage", []):
            if not isinstance(item, dict):
                continue
            key = str(item.get("name", "")).lower()
            if "email" in key or "username" in key or "login" in key:
                email = _email_from_value(item.get("value"))
                if email:
                    return email
    for cookie in state.get("cookies", []):
        if not isinstance(cookie, dict):
            continue
        key = str(cookie.get("name", "")).lower()
        if "email" in key or "username" in key:
            email = _email_from_value(cookie.get("value"))
            if email:
                return email
    return None


def _display_account_email(account: Optional[PlatformAccount]) -> Optional[str]:
    if not account or not account.email_encrypted:
        return None
    try:
        return decrypt_data(account.email_encrypted)
    except Exception:
        return None


def _remove_saved_login_files(candidate: Candidate, platform: str) -> None:
    """Remove this app's saved session and manual-login browser profile."""
    _get_cookie_file_path(candidate, platform).unlink(missing_ok=True)
    profile_path = _get_manual_login_profile_path(candidate, platform)
    if profile_path.exists():
        shutil.rmtree(profile_path)


def _linkedin_rate_settings(account: Optional[PlatformAccount]) -> dict:
    try:
        raw = json.loads(account.rate_limit_settings) if account and account.rate_limit_settings else {}
    except (TypeError, ValueError):
        raw = {}
    return normalize_linkedin_settings(raw)


def _normalize_cookies(cookies_raw):
    if isinstance(cookies_raw, list):
        return cookies_raw
    if isinstance(cookies_raw, dict):
        if "cookies" in cookies_raw and isinstance(cookies_raw["cookies"], list):
            return cookies_raw["cookies"]
        raise ValueError("Cookies object must contain a 'cookies' array")
    raise ValueError("Cookies must be a JSON array or object with a 'cookies' array")


def _normalize_storage_state(payload) -> dict:
    if isinstance(payload, dict):
        cookies = payload.get("cookies")
        origins = payload.get("origins", [])
        if isinstance(cookies, list):
            return {"cookies": cookies, "origins": origins if isinstance(origins, list) else []}
    if isinstance(payload, list):
        return {"cookies": payload, "origins": []}
    raise ValueError("Storage payload must be a cookie list or Playwright storage_state object")


def _upsert_platform_account(
    db: Session,
    candidate_id: int,
    platform: str,
    cookies: list,
    email: Optional[str] = None,
) -> PlatformAccount:
    account = db.query(PlatformAccount).filter(
        PlatformAccount.candidate_id == candidate_id,
        PlatformAccount.platform == platform
    ).first()

    if not account:
        account = PlatformAccount(candidate_id=candidate_id, platform=platform)
        db.add(account)

    account.cookies_encrypted = encrypt_json({"cookies": cookies})
    if email:
        account.email_encrypted = encrypt_data(email)
    account.status = "active"
    account.last_used_at = datetime.utcnow()
    return account


def _persist_cookie_file(candidate: Candidate, platform: str, cookies: list) -> Path:
    cookies_path = _get_cookie_file_path(candidate, platform)
    cookies_path.parent.mkdir(parents=True, exist_ok=True)
    cookies_path.write_text(encrypt_data(json.dumps(cookies)))
    return cookies_path


def _is_likely_authenticated(platform: str, cookies: list) -> bool:
    if not cookies:
        return False
    cookie_names = {c.get("name", "") for c in cookies if isinstance(c, dict)}
    if platform == "linkedin":
        return "li_at" in cookie_names
    if platform == "glassdoor":
        # Glassdoor auth cookie names vary by rollout; keep broad but meaningful.
        markers = {"at", "g_state", "JSESSIONID", "optimizelyEndUserId"}
        return len(cookie_names.intersection(markers)) > 0
    return len(cookie_names) > 0


def _account_guidance(account: Optional[PlatformAccount]) -> dict:
    """Describe the saved-session state without attempting a live login check.

    Account status is deliberately kept separate from a live session probe: a
    saved cookie is not proof that the provider still accepts it.
    """
    status = account.status if account else "not_connected"
    if status == "active":
        return {
            "label": "Saved session present",
            "detail": "Run Test Connection before searching; re-login if it reports an expired session.",
            "action": "Test Connection",
            "tone": "success",
        }
    if status == "login_pending":
        return {
            "label": "Manual login in progress",
            "detail": "Complete sign-in yourself in the opened browser, including any 2FA or provider challenge, then finish the browser login.",
            "action": "Finish Browser Login",
            "tone": "primary",
        }
    if status == "login_failed":
        return {
            "label": "Manual login needs attention",
            "detail": "The browser login was not completed. Open Browser Login again, complete sign-in yourself, then finish the browser login.",
            "action": "Open Browser Login",
            "tone": "warning",
        }
    if status == "captcha_required":
        return {
            "label": "CAPTCHA or verification required",
            "detail": "Open Browser Login and complete the provider's challenge yourself, then finish the browser login.",
            "action": "Re-login in browser",
            "tone": "danger",
        }
    if status == "expired":
        return {
            "label": "Session expired — re-login required",
            "detail": "Open Browser Login, sign in yourself, then finish the browser login to replace the saved session.",
            "action": "Re-login in browser",
            "tone": "warning",
        }
    return {
        "label": "No saved session",
        "detail": "Open Browser Login, sign in yourself, then finish the browser login to save the session.",
        "action": "Open Browser Login",
        "tone": "secondary",
    }


def _platform_status(account: Optional[PlatformAccount]) -> dict:
    """Build display-only saved-session information for the account UI."""
    return {"session": _account_guidance(account)}


def _session_probe_outcome(current_url: str) -> tuple[bool, str, str]:
    """Classify a completed user-operated session probe without guessing."""
    url = (current_url or "").lower()
    if "captcha" in url or "challenge" in url or "checkpoint" in url:
        return False, "captcha_required", "A provider challenge or CAPTCHA is required. Complete it yourself in the browser, then re-login."
    if "/login" in url or "signin" in url:
        return False, "expired", "The saved session has expired. Open Browser Login and sign in yourself."
    return True, "active", "Session is valid"


@router.get("/", response_class=HTMLResponse)
async def list_accounts(request: Request, candidate_id: int, db: Session = Depends(get_db)):
    """Show platform accounts management page"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get all platform accounts for this candidate
    accounts = db.query(PlatformAccount).filter(
        PlatformAccount.candidate_id == candidate_id
    ).all()
    
    # Prepare account info by platform
    platforms = {
        "linkedin": {"name": "LinkedIn", "icon": "bi-linkedin", "color": "primary", "account": None},
        "glassdoor": {"name": "Glassdoor", "icon": "bi-building", "color": "success", "account": None},
        "indeed": {"name": "Indeed", "icon": "bi-briefcase", "color": "info", "account": None}
    }
    
    for account in accounts:
        if account.platform in platforms:
            platforms[account.platform]["account"] = account

    for platform, platform_info in platforms.items():
        platform_info.update(_platform_status(platform_info["account"]))
        platform_info["login_email"] = _display_account_email(platform_info["account"])
        if platform == "linkedin":
            platform_info["rate_limits"] = _linkedin_rate_settings(platform_info["account"])
    
    return templates.TemplateResponse("accounts/list.html", {
        "request": request,
        "candidate": candidate,
        "platforms": platforms
    })


@router.post("/save-cookies")
async def save_cookies(
    request: Request,
    candidate_id: int,
    platform: str = Form(...),
    cookies_json: str = Form(...),
    email: str = Form(None),
    db: Session = Depends(get_db)
):
    """Save session cookies for a platform"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    if platform not in ["linkedin", "glassdoor", "indeed"]:
        return JSONResponse({"success": False, "message": "Invalid platform"}, status_code=400)
    
    try:
        # Validate cookies JSON
        cookies_input = json.loads(cookies_json)
        cookies = _normalize_cookies(cookies_input)

        _upsert_platform_account(db, candidate_id, platform, cookies, email=email)
        _persist_cookie_file(candidate, platform, cookies)
        
        db.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"{platform.capitalize()} cookies saved successfully ({len(cookies)} cookies)"
        })
        
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/{account_id}/delete")
async def delete_account(request: Request, candidate_id: int, account_id: int, db: Session = Depends(get_db)):
    """Delete a platform account"""
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.candidate_id == candidate_id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        platform = account.platform
        db.delete(account)
        db.commit()
        
        return RedirectResponse(
            url=f"/candidates/{candidate_id}/accounts?success=deleted&platform={platform}",
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{account_id}/logout", response_class=JSONResponse)
async def logout_account(candidate_id: int, account_id: int, db: Session = Depends(get_db)):
    """Forget this platform login locally, including its saved browser profile."""
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.candidate_id == candidate_id,
    ).first()
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not account or not candidate:
        raise HTTPException(status_code=404, detail="Account not found")

    platform = account.platform
    try:
        manager = await get_browser_pool(headless=False).get_manager()
        await manager.close_manual_context(_manual_login_session_key(candidate, platform))
        _remove_saved_login_files(candidate, platform)
        db.delete(account)
        db.commit()
        return JSONResponse({"success": True, "message": f"{platform.capitalize()} login removed"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/{account_id}/rate-limits", response_class=JSONResponse)
async def save_linkedin_rate_limits(
    candidate_id: int,
    account_id: int,
    hourly_limit: int = Form(...),
    daily_limit: int = Form(...),
    min_delay_seconds: int = Form(...),
    max_delay_seconds: int = Form(...),
    operating_hours_start: int = Form(...),
    operating_hours_end: int = Form(...),
    db: Session = Depends(get_db),
):
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.candidate_id == candidate_id,
        PlatformAccount.platform == "linkedin",
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="LinkedIn account not found")
    settings = normalize_linkedin_settings({
        "hourly_limit": hourly_limit, "daily_limit": daily_limit,
        "min_delay_seconds": min_delay_seconds, "max_delay_seconds": max_delay_seconds,
        "operating_hours_start": operating_hours_start, "operating_hours_end": operating_hours_end,
    })
    account.rate_limit_settings = json.dumps(settings)
    db.commit()
    return JSONResponse({"success": True, "settings": settings})


@router.post("/{account_id}/rate-limits/reset", response_class=JSONResponse)
async def reset_linkedin_rate_limits(candidate_id: int, account_id: int, db: Session = Depends(get_db)):
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.candidate_id == candidate_id,
        PlatformAccount.platform == "linkedin",
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="LinkedIn account not found")
    from backend.services.rate_limiter import get_rate_limiter
    get_rate_limiter().reset(f"linkedin:{candidate_id}")
    return JSONResponse({"success": True, "message": "LinkedIn rate-limit usage reset"})


@router.post("/{account_id}/test")
async def test_account(request: Request, candidate_id: int, account_id: int, db: Session = Depends(get_db)):
    """Test if stored cookies are still valid"""
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.candidate_id == candidate_id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if not account.cookies_encrypted:
        return JSONResponse({
            "success": False,
            "message": "No cookies stored for this account"
        })

    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Decrypt cookies
        payload = decrypt_json(account.cookies_encrypted)
        state = _normalize_storage_state(payload)
        cookies = state["cookies"]
        
        if not cookies:
            return JSONResponse({
                "success": False,
                "message": "Invalid cookie data"
            })

        # Ensure file exists for search service compatibility
        _persist_cookie_file(candidate, account.platform, cookies)

        if not _is_likely_authenticated(account.platform, cookies):
            account.status = "expired"
            db.commit()
            return JSONResponse({
                "success": False,
                "message": f"{account.platform.capitalize()} session appears missing auth cookies. Please login again."
            })

        # Live validity check with Playwright
        manager = await get_browser_pool(headless=False).get_manager()
        page = await manager.new_page(account.platform, str(_get_cookie_file_path(candidate, account.platform)))
        try:
            auth_check_url = "https://www.linkedin.com/feed/" if account.platform == "linkedin" else "https://www.glassdoor.com/"
            await page.goto(auth_check_url, wait_until="domcontentloaded", timeout=45000)
            is_valid, outcome_status, outcome_message = _session_probe_outcome(page.url)
        finally:
            await page.close()

        if not is_valid:
            account.status = outcome_status
            db.commit()
            return JSONResponse({
                "success": False,
                "state": outcome_status,
                "message": f"{account.platform.capitalize()}: {outcome_message}"
            })

        account.status = "active"
        account.last_used_at = datetime.utcnow()
        db.commit()
        return JSONResponse({
            "success": True,
            "message": f"{account.platform.capitalize()} session is valid",
            "cookie_count": len(cookies)
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"Failed to load cookies: {str(e)}"
        })


@router.get("/{account_id}/cookies", response_class=JSONResponse)
async def get_cookies(candidate_id: int, account_id: int, db: Session = Depends(get_db)):
    """Get decrypted cookies for a platform account"""
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.candidate_id == candidate_id
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if not account.cookies_encrypted:
        return JSONResponse({"success": False, "message": "No cookies stored"})
    
    try:
        payload = decrypt_json(account.cookies_encrypted)
        state = _normalize_storage_state(payload)
        cookies = state["cookies"]
        return JSONResponse({"success": True, "cookies": cookies})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)


@router.post("/start-browser-login", response_class=JSONResponse)
async def start_browser_login(
    candidate_id: int,
    platform: str = Form(...),
    db: Session = Depends(get_db),
):
    """Open Playwright browser for manual platform login."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if platform not in PLATFORM_LOGIN_URLS:
        return JSONResponse({"success": False, "message": "Invalid platform"}, status_code=400)

    manager = await get_browser_pool(headless=False).get_manager()
    session_key = _manual_login_session_key(candidate, platform)
    page = await manager.new_manual_page(
        session_key,
        str(_get_manual_login_profile_path(candidate, platform)),
    )

    try:
        await page.goto(PLATFORM_LOGIN_URLS[platform], wait_until="domcontentloaded", timeout=60000)
        await page.bring_to_front()
    except Exception as e:
        await page.close()
        return JSONResponse({"success": False, "message": f"Failed to open login page: {e}"}, status_code=500)

    account = db.query(PlatformAccount).filter(
        PlatformAccount.candidate_id == candidate_id,
        PlatformAccount.platform == platform,
    ).first()
    if not account:
        account = PlatformAccount(candidate_id=candidate_id, platform=platform)
        db.add(account)
    account.status = "login_pending"
    db.commit()

    return JSONResponse({
        "success": True,
        "state": "login_pending",
        "message": f"{platform.capitalize()} login opened. Complete sign-in yourself in the browser, including 2FA or any provider challenge, then click 'Finish Browser Login'."
    })


@router.post("/finish-browser-login", response_class=JSONResponse)
async def finish_browser_login(
    candidate_id: int,
    platform: str = Form(...),
    db: Session = Depends(get_db),
):
    """Save cookies from active Playwright context after manual login."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if platform not in PLATFORM_LOGIN_URLS:
        return JSONResponse({"success": False, "message": "Invalid platform"}, status_code=400)

    manager = await get_browser_pool(headless=False).get_manager()
    session_key = _manual_login_session_key(candidate, platform)
    profile_path = _get_manual_login_profile_path(candidate, platform)
    state = await manager.get_manual_storage_state(session_key, str(profile_path))
    state = _normalize_storage_state(state if state else [])
    cookies = state["cookies"]
    if not cookies:
        return JSONResponse({
            "success": False,
            "state": "login_pending",
            "message": "No session cookies found. Complete sign-in yourself in the opened browser, then try Finish Browser Login again."
        }, status_code=400)

    if not _is_likely_authenticated(platform, cookies):
        return JSONResponse({
            "success": False,
            "state": "login_pending",
            "message": f"{platform.capitalize()} sign-in is not detected yet. Complete any 2FA or provider challenge yourself, then click Finish Browser Login again."
        }, status_code=400)

    try:
        # Store complete Playwright state in DB; keep cookies file for scraper compatibility.
        account = db.query(PlatformAccount).filter(
            PlatformAccount.candidate_id == candidate_id,
            PlatformAccount.platform == platform
        ).first()
        if not account:
            account = PlatformAccount(candidate_id=candidate_id, platform=platform)
            db.add(account)
        account.cookies_encrypted = encrypt_json(state)
        detected_email = _detect_account_email(state)
        if detected_email:
            account.email_encrypted = encrypt_data(detected_email)
        account.status = "active"
        account.last_used_at = datetime.utcnow()

        _persist_cookie_file(candidate, platform, cookies)
        db.commit()
        await manager.close_manual_context(session_key)
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)

    return JSONResponse({
        "success": True,
        "state": "active",
        "message": f"{platform.capitalize()} login saved successfully ({len(cookies)} cookies)"
    })
