import json

import pytest

from backend.security import decrypt_data
from backend.services.browser_manager import BrowserManager


class _StorageStateContext:
    async def storage_state(self):
        return {
            "cookies": [{"name": "li_at", "value": "not-a-real-session"}],
            "origins": [],
        }


class _PersistentContext(_StorageStateContext):
    def __init__(self):
        self.cookies = []

    async def add_init_script(self, script):
        self.script = script

    async def add_cookies(self, cookies):
        self.cookies.extend(cookies)

    async def new_page(self):
        return _ManualPage()


class _ManualPage:
    async def goto(self, url, **kwargs):
        self.url = url

    async def bring_to_front(self):
        self.focused = True


class _SourceContext:
    async def storage_state(self):
        return {"cookies": [{"name": "li_at", "value": "session"}], "origins": []}


class _SourcePage:
    context = _SourceContext()
    url = "https://www.linkedin.com/checkpoint/challenge"


class _Chromium:
    def __init__(self):
        self.calls = []
        self.context = _PersistentContext()

    async def launch_persistent_context(self, profile_path, **kwargs):
        self.calls.append((profile_path, kwargs))
        return self.context


class _Playwright:
    def __init__(self):
        self.chromium = _Chromium()


@pytest.mark.asyncio
async def test_save_cookies_persists_encrypted_storage_state_as_text(tmp_path):
    manager = BrowserManager()
    manager._contexts["linkedin"] = _StorageStateContext()
    cookies_path = tmp_path / "linkedin.enc"

    await manager.save_cookies("linkedin", str(cookies_path))

    saved_state = json.loads(decrypt_data(cookies_path.read_text()))
    assert saved_state["cookies"][0]["name"] == "li_at"


@pytest.mark.asyncio
async def test_manual_login_context_uses_reopenable_persistent_profile(tmp_path):
    manager = BrowserManager()
    manager._initialized = True
    manager._playwright = _Playwright()

    state = await manager.get_manual_storage_state("candidate:linkedin", str(tmp_path / "profile"))
    same_context = await manager.get_manual_context("candidate:linkedin", str(tmp_path / "profile"))

    assert state["cookies"][0]["name"] == "li_at"
    assert same_context is manager._playwright.chromium.context
    assert len(manager._playwright.chromium.calls) == 1


@pytest.mark.asyncio
async def test_captcha_handoff_copies_session_into_manual_browser(tmp_path):
    manager = BrowserManager()
    manager._initialized = True
    manager._playwright = _Playwright()

    page = await manager.handoff_page_to_manual_login(
        _SourcePage(), "candidate:linkedin", str(tmp_path / "profile"),
    )

    assert manager._playwright.chromium.context.cookies == [{"name": "li_at", "value": "session"}]
    assert page.url.endswith("/checkpoint/challenge")
    assert page.focused is True
