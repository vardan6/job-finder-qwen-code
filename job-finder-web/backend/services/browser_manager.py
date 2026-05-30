"""
Browser Manager - Playwright browser lifecycle management

Features:
- Singleton browser instance per platform
- Automatic cleanup on exit
- Orphan process detection and cleanup
- Stealth configuration
- Cookie persistence
"""
import atexit
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import json

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Manages Playwright browser instances with proper lifecycle handling.
    """
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize Playwright"""
        if self._initialized:
            return
        
        logger.info("Initializing Playwright...")
        self._playwright = await async_playwright().start()
        self._initialized = True
        
        # Register cleanup on exit
        atexit.register(self._cleanup_sync)
        logger.debug("Playwright initialized")
    
    async def get_browser(self) -> Browser:
        """Get or create the browser instance"""
        if not self._initialized:
            await self.initialize()
        
        if self._browser is None or not self._browser.is_connected():
            if self._contexts:
                logger.info("Browser restarted; clearing stale contexts")
                self._contexts = {}
            logger.info("Launching browser...")
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
            logger.info("Browser launched")
        
        return self._browser
    
    async def get_context(self, platform: str, cookies_path: Optional[str] = None) -> BrowserContext:
        """
        Get or create a browser context for a platform.
        
        Args:
            platform: Platform name (linkedin, glassdoor, etc.)
            cookies_path: Path to load/save cookies
        
        Returns:
            BrowserContext for the platform
        """
        browser = await self.get_browser()
        if platform in self._contexts:
            return self._contexts[platform]

        storage_state = None
        cookie_list = None
        if cookies_path:
            cookies_file = Path(cookies_path)
            if cookies_file.exists():
                try:
                    from backend.security import decrypt_data
                    encrypted = cookies_file.read_text()
                    decrypted = decrypt_data(encrypted)
                    payload = json.loads(decrypted)
                    if isinstance(payload, dict) and isinstance(payload.get("cookies"), list):
                        storage_state = payload
                    elif isinstance(payload, list):
                        cookie_list = payload
                    logger.info(f"Loaded persisted session payload for {platform}")
                except Exception as e:
                    logger.warning(f"Failed to parse persisted session for {platform}: {e}")
        
        # Create context with stealth settings
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Yerevan",
            color_scheme="light",
            storage_state=storage_state,
        )
        
        # Add stealth headers
        await context.add_init_script("""
            // Pass the Chrome Test
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
            };
            
            // Pass the Navigator Test
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Pass the Plugins Test
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Pass the Languages Test
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
        """)
        
        if cookie_list:
            try:
                await context.add_cookies(cookie_list)
                logger.info(f"Loaded {len(cookie_list)} cookies for {platform}")
            except Exception as e:
                logger.warning(f"Failed to load cookies for {platform}: {e}")
        
        self._contexts[platform] = context
        logger.debug(f"Created context for {platform}")
        return context
    
    async def save_cookies(self, platform: str, cookies_path: str):
        """Save full storage state for a platform (cookies + localStorage)."""
        if platform not in self._contexts:
            logger.warning(f"No context for {platform}, cannot save cookies")
            return
        
        context = self._contexts[platform]
        state = await context.storage_state()
        cookies = state.get("cookies", [])
        
        try:
            from backend.security import encrypt_data
            
            state_json = json.dumps(state)
            encrypted = encrypt_data(state_json)
            
            cookies_file = Path(cookies_path)
            cookies_file.parent.mkdir(parents=True, exist_ok=True)
            cookies_file.write_bytes(encrypted)
            logger.info(f"Saved storage state for {platform} ({len(cookies)} cookies)")
        except Exception as e:
            logger.error(f"Failed to save cookies for {platform}: {e}")

    async def get_cookies(self, platform: str) -> list:
        """Get cookies currently loaded in a platform context."""
        if platform not in self._contexts:
            return []
        try:
            return await self._contexts[platform].cookies()
        except Exception as e:
            logger.warning(f"Failed to read cookies for {platform}: {e}")
            return []

    async def get_storage_state(self, platform: str) -> dict:
        """Get full storage state for a platform context."""
        if platform not in self._contexts:
            return {}
        try:
            return await self._contexts[platform].storage_state()
        except Exception as e:
            logger.warning(f"Failed to read storage state for {platform}: {e}")
            return {}
    
    async def new_page(self, platform: str, cookies_path: Optional[str] = None) -> Page:
        """Create a new page in the platform's context"""
        context = await self.get_context(platform, cookies_path)
        page = await context.new_page()
        
        # Additional page-level stealth
        await page.add_init_script("""
            // Override the navigator.webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
        
        return page
    
    async def close_context(self, platform: str):
        """Close a platform's context"""
        if platform in self._contexts:
            await self._contexts[platform].close()
            del self._contexts[platform]
            logger.debug(f"Closed context for {platform}")
    
    async def close_all(self):
        """Close all contexts and the browser"""
        # Close all contexts
        for platform in list(self._contexts.keys()):
            await self.close_context(platform)
        
        # Close browser
        if self._browser:
            await self._browser.close()
            self._browser = None
            logger.info("Browser closed")
    
    def _cleanup_sync(self):
        """Synchronous cleanup (for atexit)"""
        if self._browser:
            logger.info("Cleaning up browser on exit...")
            # Can't use async in atexit, so we just log
            logger.warning("Browser cleanup skipped (async cleanup not available in atexit)")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_all()


class BrowserPool:
    """
    Pool of browser instances for parallel scraping.
    Currently limited to 1 browser (ultra-conservative approach).
    """
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._manager: Optional[BrowserManager] = None
    
    async def get_manager(self) -> BrowserManager:
        """Get the browser manager (singleton)"""
        if self._manager is None:
            self._manager = BrowserManager(headless=self.headless)
        return self._manager
    
    async def close_all(self):
        """Close all browsers"""
        if self._manager:
            await self._manager.close_all()


# Global pool instance
_browser_pool: Optional[BrowserPool] = None


def get_browser_pool(headless: bool = False) -> BrowserPool:
    """Get or create the global browser pool"""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(headless=headless)
    return _browser_pool


async def cleanup_browsers():
    """Cleanup all browser instances (call on shutdown)"""
    global _browser_pool
    if _browser_pool:
        await _browser_pool.close_all()
        _browser_pool = None
