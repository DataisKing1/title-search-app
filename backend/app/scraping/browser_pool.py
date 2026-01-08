"""Playwright browser pool for concurrent scraping"""
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from typing import Dict, Optional, List, AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import asyncio
import time
import logging

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BrowserInstance:
    """Represents a browser instance in the pool"""
    browser: Browser
    context: BrowserContext
    page: Page
    in_use: bool = False
    county: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    request_count: int = 0


class BrowserPoolManager:
    """
    Manages a pool of Playwright browser instances for parallel scraping.

    Features:
    - Configurable pool size
    - Stealth mode to avoid detection
    - Automatic cleanup and recycling
    - County-specific session persistence
    """

    def __init__(
        self,
        pool_size: int = None,
        headless: bool = None,
        proxy: Optional[Dict] = None
    ):
        self.pool_size = pool_size or settings.BROWSER_POOL_SIZE
        self.headless = headless if headless is not None else settings.BROWSER_HEADLESS
        self.proxy = proxy
        self.instances: List[BrowserInstance] = []
        self.lock = asyncio.Lock()
        self._playwright: Optional[Playwright] = None
        self._initialized = False
        self._max_requests_per_instance = settings.BROWSER_MAX_REQUESTS_PER_INSTANCE

    async def initialize(self):
        """Initialize the browser pool"""
        if self._initialized:
            return

        logger.info(f"Initializing browser pool with {self.pool_size} instances")

        self._playwright = await async_playwright().start()

        for i in range(self.pool_size):
            try:
                instance = await self._create_instance()
                self.instances.append(instance)
                logger.debug(f"Created browser instance {i + 1}/{self.pool_size}")
            except Exception as e:
                logger.error(f"Failed to create browser instance {i + 1}: {e}")

        self._initialized = True
        logger.info(f"Browser pool initialized with {len(self.instances)} instances")

    async def _create_instance(self) -> BrowserInstance:
        """Create a new browser instance with stealth configuration"""
        launch_options = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--window-size=1920,1080",
            ]
        }

        if self.proxy:
            launch_options["proxy"] = self.proxy

        browser = await self._playwright.chromium.launch(**launch_options)

        # Create context with realistic settings
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/Denver",
            geolocation={"latitude": 39.7392, "longitude": -104.9903},  # Denver
            permissions=["geolocation"],
        )

        # Add stealth scripts to evade detection
        await context.add_init_script("""
            // Overwrite navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Overwrite navigator.plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Overwrite navigator.languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

            // Mock chrome runtime
            window.chrome = {
                runtime: {}
            };
        """)

        page = await context.new_page()

        # Set default timeout
        page.set_default_timeout(settings.BROWSER_TIMEOUT)

        return BrowserInstance(
            browser=browser,
            context=context,
            page=page,
            in_use=False,
            created_at=time.time()
        )

    @asynccontextmanager
    async def acquire(self, county: Optional[str] = None) -> AsyncGenerator[BrowserInstance, None]:
        """
        Acquire a browser instance from the pool.

        Args:
            county: Optional county name for session persistence

        Yields:
            BrowserInstance: An available browser instance
        """
        if not self._initialized:
            await self.initialize()

        instance = None
        retry_count = 0
        max_retries = 10

        while instance is None and retry_count < max_retries:
            async with self.lock:
                # First, try to find an instance already initialized for this county
                if county:
                    for inst in self.instances:
                        if not inst.in_use and inst.county == county:
                            instance = inst
                            break

                # Otherwise, get any available instance
                if not instance:
                    for inst in self.instances:
                        if not inst.in_use:
                            instance = inst
                            break

                if instance:
                    instance.in_use = True
                    instance.county = county
                    instance.request_count += 1

            if not instance:
                retry_count += 1
                await asyncio.sleep(1)

        if not instance:
            # Create a new temporary instance
            logger.warning("Pool exhausted, creating temporary instance")
            instance = await self._create_instance()
            instance.in_use = True
            instance.county = county

        try:
            # Check if instance needs recycling
            if instance.request_count > self._max_requests_per_instance:
                await self._recycle_instance(instance)

            yield instance

        except Exception as e:
            logger.error(f"Error during browser operation: {e}")
            # Mark instance for recycling on error
            instance.request_count = self._max_requests_per_instance + 1
            raise

        finally:
            async with self.lock:
                instance.in_use = False

    async def _recycle_instance(self, instance: BrowserInstance):
        """Recycle a browser instance by creating a fresh one"""
        logger.info(f"Recycling browser instance (requests: {instance.request_count})")

        try:
            await instance.context.close()
            await instance.browser.close()
        except Exception as e:
            logger.warning(f"Error closing old browser: {e}")

        # Create new instance
        new_instance = await self._create_instance()
        new_instance.in_use = True
        new_instance.county = instance.county

        # Replace in pool
        async with self.lock:
            idx = self.instances.index(instance)
            self.instances[idx] = new_instance

        # Update reference
        instance.browser = new_instance.browser
        instance.context = new_instance.context
        instance.page = new_instance.page
        instance.request_count = 1
        instance.created_at = time.time()

    async def shutdown(self):
        """Shutdown all browser instances"""
        logger.info("Shutting down browser pool")

        for instance in self.instances:
            try:
                await instance.context.close()
                await instance.browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser instance: {e}")

        if self._playwright:
            await self._playwright.stop()

        self.instances.clear()
        self._initialized = False
        logger.info("Browser pool shut down")

    async def get_stats(self) -> Dict:
        """Get pool statistics"""
        async with self.lock:
            in_use = sum(1 for inst in self.instances if inst.in_use)
            return {
                "pool_size": len(self.instances),
                "in_use": in_use,
                "available": len(self.instances) - in_use,
                "initialized": self._initialized
            }


# Global pool instance (lazy initialization)
_browser_pool: Optional[BrowserPoolManager] = None
_browser_pool_lock: asyncio.Lock = asyncio.Lock()


async def get_browser_pool() -> BrowserPoolManager:
    """Get or create the global browser pool (thread-safe singleton)"""
    global _browser_pool

    # Fast path - already initialized
    if _browser_pool is not None and _browser_pool._initialized:
        return _browser_pool

    # Slow path - need to initialize with lock
    async with _browser_pool_lock:
        # Double-check after acquiring lock
        if _browser_pool is None:
            _browser_pool = BrowserPoolManager()
        if not _browser_pool._initialized:
            await _browser_pool.initialize()

    return _browser_pool


async def shutdown_browser_pool():
    """Shutdown the global browser pool"""
    global _browser_pool
    async with _browser_pool_lock:
        if _browser_pool:
            await _browser_pool.shutdown()
            _browser_pool = None
