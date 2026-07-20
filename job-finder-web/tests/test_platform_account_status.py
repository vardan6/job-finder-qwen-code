from backend.models.platform_account import PlatformAccount

from backend.routes.platform_accounts import (
    _account_guidance,
    _detect_account_email,
    _platform_status,
    _session_probe_outcome,
)


def test_expired_account_has_explicit_manual_relogin_guidance():
    status = _platform_status(PlatformAccount(platform="linkedin", status="expired"))

    assert status["session"]["label"] == "Session expired — re-login required"
    assert "sign in yourself" in status["session"]["detail"]
    assert status["session"]["action"] == "Re-login in browser"

def test_pending_manual_login_has_a_clear_next_step():
    guidance = _account_guidance(PlatformAccount(platform="indeed", status="login_pending"))

    assert guidance["label"] == "Manual login in progress"
    assert "yourself" in guidance["detail"]
    assert guidance["action"] == "Finish Browser Login"


def test_detect_account_email_uses_only_explicitly_labelled_storage():
    assert _detect_account_email({
        "cookies": [],
        "origins": [{"localStorage": [{"name": "accountEmail", "value": "person@example.com"}]}],
    }) == "person@example.com"
    assert _detect_account_email({
        "cookies": [],
        "origins": [{"localStorage": [{"name": "last_page", "value": "person@example.com"}]}],
    }) is None


def test_failed_manual_login_has_a_clear_recovery_step():
    guidance = _account_guidance(PlatformAccount(platform="indeed", status="login_failed"))

    assert guidance["label"] == "Manual login needs attention"
    assert guidance["action"] == "Open Browser Login"
    assert guidance["tone"] == "warning"

def test_session_probe_distinguishes_provider_challenge_from_expiry():
    valid, status, message = _session_probe_outcome("https://www.linkedin.com/checkpoint/challenge")

    assert valid is False
    assert status == "captcha_required"
    assert "yourself" in message
