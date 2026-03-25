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
from typing import Optional

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.platform_account import PlatformAccount
from backend.security import encrypt_json, decrypt_json, encrypt_data
from backend.services.browser_manager import get_browser_pool

router = APIRouter(prefix="/candidates/{candidate_id}/accounts", tags=["platform_accounts"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)
PLATFORM_LOGIN_URLS = {
    "linkedin": "https://www.linkedin.com/login",
    "glassdoor": "https://www.glassdoor.com/profile/login_input.htm",
    "indeed": "https://secure.indeed.com/auth",
}


def _get_cookie_file_path(candidate: Candidate, platform: str) -> Path:
    return Path(f"data/cookies/{candidate.uuid}_{platform}.enc")


def _to_bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode()
    raise ValueError("Unsupported encrypted cookie format")


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
    cookies_path.write_bytes(encrypt_data(json.dumps(cookies)))
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
        payload = decrypt_json(_to_bytes(account.cookies_encrypted))
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
            current_url = (page.url or "").lower()
            is_valid = all(marker not in current_url for marker in ["/login", "signin", "challenge", "captcha"])
        finally:
            await page.close()

        if not is_valid:
            account.status = "expired"
            db.commit()
            return JSONResponse({
                "success": False,
                "message": f"{account.platform.capitalize()} session appears expired. Please login again."
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
        payload = decrypt_json(_to_bytes(account.cookies_encrypted))
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

    cookies_path = _get_cookie_file_path(candidate, platform)
    manager = await get_browser_pool(headless=False).get_manager()
    page = await manager.new_page(platform, str(cookies_path))

    try:
        await page.goto(PLATFORM_LOGIN_URLS[platform], wait_until="domcontentloaded", timeout=60000)
        await page.bring_to_front()
    except Exception as e:
        await page.close()
        return JSONResponse({"success": False, "message": f"Failed to open login page: {e}"}, status_code=500)

    return JSONResponse({
        "success": True,
        "message": f"{platform.capitalize()} login opened. Complete login in the browser, then click 'Finish Browser Login'."
    })


@router.post("/finish-browser-login", response_class=JSONResponse)
async def finish_browser_login(
    candidate_id: int,
    platform: str = Form(...),
    email: str = Form(None),
    db: Session = Depends(get_db),
):
    """Save cookies from active Playwright context after manual login."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if platform not in PLATFORM_LOGIN_URLS:
        return JSONResponse({"success": False, "message": "Invalid platform"}, status_code=400)

    cookies_path = _get_cookie_file_path(candidate, platform)
    manager = await get_browser_pool(headless=False).get_manager()

    await manager.save_cookies(platform, str(cookies_path))
    state = await manager.get_storage_state(platform)
    state = _normalize_storage_state(state if state else [])
    cookies = state["cookies"]
    if not cookies:
        return JSONResponse({
            "success": False,
            "message": "No session cookies found. Please complete login in browser first."
        }, status_code=400)

    if not _is_likely_authenticated(platform, cookies):
        return JSONResponse({
            "success": False,
            "message": f"{platform.capitalize()} login not detected yet. Make sure you are fully signed in, then click Finish again."
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
        if email:
            account.email_encrypted = encrypt_data(email)
        account.status = "active"
        account.last_used_at = datetime.utcnow()

        _persist_cookie_file(candidate, platform, cookies)
        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)

    return JSONResponse({
        "success": True,
        "message": f"{platform.capitalize()} login saved successfully ({len(cookies)} cookies)"
    })
