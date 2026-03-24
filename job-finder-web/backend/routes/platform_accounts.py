"""
Platform Accounts Routes - Manage LinkedIn/Glassdoor credentials
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
import json

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.platform_account import PlatformAccount
from backend.security import encrypt_json, decrypt_json

router = APIRouter(prefix="/candidates/{candidate_id}/accounts", tags=["platform_accounts"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)


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
        cookies = json.loads(cookies_json)
        if not isinstance(cookies, dict):
            raise ValueError("Cookies must be a JSON object")
        
        # Get or create account
        account = db.query(PlatformAccount).filter(
            PlatformAccount.candidate_id == candidate_id,
            PlatformAccount.platform == platform
        ).first()
        
        if not account:
            account = PlatformAccount(
                candidate_id=candidate_id,
                platform=platform
            )
            db.add(account)
        
        # Encrypt and save cookies
        account.cookies_encrypted = encrypt_json(cookies)
        
        # Encrypt email if provided
        if email:
            from backend.security import encrypt_data
            account.email_encrypted = encrypt_data(email)
        
        account.status = "active"
        
        db.commit()
        db.refresh(account)
        
        return JSONResponse({
            "success": True,
            "message": f"{platform.capitalize()} cookies saved successfully"
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
        # Decrypt cookies
        cookies = decrypt_json(account.cookies_encrypted.encode())
        
        # Basic validation - check if cookies have expected structure
        if not cookies:
            return JSONResponse({
                "success": False,
                "message": "Invalid cookie data"
            })
        
        # TODO: Actually test cookies against the platform
        # For now, just check if they exist
        return JSONResponse({
            "success": True,
            "message": f"Cookies loaded successfully for {account.platform}",
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
        cookies = decrypt_json(account.cookies_encrypted.encode())
        return JSONResponse({"success": True, "cookies": cookies})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)
