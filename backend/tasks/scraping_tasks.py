"""Scraping-related Celery tasks"""
from tasks.celery_app import celery_app
from datetime import datetime, timedelta
import asyncio
import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)


def get_db_session():
    """Get synchronous database session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    database_url = os.getenv("DATABASE_URL", "sqlite:///./title_search.db")
    sync_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def run_async(coro):
    """Run async coroutine in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    max_retries=settings.SCRAPING_MAX_RETRIES,
    default_retry_delay=settings.SCRAPING_RETRY_DELAY_SECONDS
)
def scrape_county_records(self, search_id: int, county: str, parcel: str, address: str):
    """
    Scrape county recorder website for documents.

    This is the main scraping task that uses the browser pool
    and county-specific adapters.
    """
    from app.models.search import TitleSearch
    from app.models.document import Document, DocumentType, DocumentSource
    from app.models.county import CountyConfig

    db = get_db_session()

    try:
        logger.info(f"Starting scrape for search {search_id}, {county} County")

        # Get county configuration
        county_config = db.query(CountyConfig).filter(
            CountyConfig.county_name.ilike(county)
        ).first()

        if not county_config:
            logger.warning(f"No configuration for {county} County, using defaults")
            config = {
                "county_name": county,
                "recorder_url": None,
                "requests_per_minute": 10,
                "delay_between_requests_ms": 2000,
            }
        else:
            config = {
                "county_name": county_config.county_name,
                "recorder_url": county_config.recorder_url,
                "requests_per_minute": county_config.requests_per_minute,
                "delay_between_requests_ms": county_config.delay_between_requests_ms,
                "requires_auth": county_config.requires_auth,
                "auth_config": county_config.auth_config,
            }

        # Run the async scraping
        results = run_async(_do_scrape(config, parcel, address))

        # Store results in database
        document_count = 0
        for result in results:
            doc = Document(
                search_id=search_id,
                document_type=DocumentType(result.document_type) if result.document_type in [e.value for e in DocumentType] else DocumentType.OTHER,
                instrument_number=result.instrument_number,
                recording_date=result.recording_date,
                grantor=result.grantor or [],
                grantee=result.grantee or [],
                book=result.book,
                page=result.page,
                consideration=result.consideration,
                source=DocumentSource.COUNTY_RECORDER,
                source_url=result.download_url
            )
            db.add(doc)
            document_count += 1

        db.commit()

        # Update county health
        if county_config:
            county_config.last_successful_scrape = datetime.utcnow()
            county_config.consecutive_failures = 0
            county_config.is_healthy = True
            db.commit()

        logger.info(f"Scrape complete: found {document_count} documents")

        return {
            "success": True,
            "search_id": search_id,
            "county": county,
            "document_count": document_count
        }

    except Exception as e:
        logger.error(f"Scraping failed for {county}: {e}")

        # Update county health on failure
        if county_config:
            county_config.last_failed_scrape = datetime.utcnow()
            county_config.consecutive_failures += 1
            if county_config.consecutive_failures >= 5:
                county_config.is_healthy = False
            db.commit()

        # Retry if not max retries
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "success": False,
            "search_id": search_id,
            "county": county,
            "error": str(e),
            "document_count": 0
        }

    finally:
        db.close()


async def _do_scrape(config: dict, parcel: str, address: str):
    """Async scraping implementation"""
    from app.scraping.browser_pool import get_browser_pool
    from app.scraping.adapters import get_adapter_for_county

    county = config["county_name"]
    results = []

    # Get adapter
    adapter = get_adapter_for_county(county, config)
    if not adapter:
        logger.error(f"Could not get adapter for {county}")
        return results

    # Get browser from pool
    pool = await get_browser_pool()

    async with pool.acquire(county) as browser_instance:
        page = browser_instance.page

        # Initialize adapter
        initialized = await adapter.initialize(page)
        if not initialized:
            logger.error(f"Failed to initialize adapter for {county}")
            return results

        # Search by parcel if available
        search_years = settings.SCRAPING_DEFAULT_SEARCH_YEARS
        start_date = datetime.utcnow() - timedelta(days=365 * search_years)

        if parcel:
            parcel_results = await adapter.search_by_parcel(
                page,
                parcel,
                start_date=start_date
            )
            results.extend(parcel_results)

        # If no results from parcel, try address-based search
        if not results and address:
            logger.info(f"No parcel results, attempting address search for: {address}")
            address_results = await adapter.search_by_address(
                page,
                address,
                start_date=start_date
            )
            results.extend(address_results)

        await adapter.wait_between_requests()

    return results


@celery_app.task(bind=True, max_retries=2)
def download_document(self, document_id: int, source_url: str):
    """Download a single document"""
    from app.models.document import Document

    db = get_db_session()

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"success": False, "error": "Document not found"}

        # Get storage path
        storage_path = os.getenv("STORAGE_PATH", "./storage")
        download_path = os.path.join(storage_path, "documents", str(document.search_id))

        # Run async download
        result = run_async(_do_download(document, source_url, download_path))

        if result:
            document.file_path = result.file_path
            document.file_name = result.file_name
            document.file_size = result.file_size
            document.file_hash = result.content_hash
            db.commit()

            return {
                "success": True,
                "document_id": document_id,
                "file_path": result.file_path
            }

        return {"success": False, "error": "Download failed"}

    except Exception as e:
        logger.error(f"Document download failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"success": False, "error": str(e)}

    finally:
        db.close()


async def _do_download(document, source_url: str, download_path: str):
    """Async document download"""
    from app.scraping.browser_pool import get_browser_pool
    from app.scraping.adapters import get_adapter_for_county
    from app.scraping.base_adapter import SearchResult

    pool = await get_browser_pool()

    async with pool.acquire() as browser_instance:
        page = browser_instance.page

        # Create a SearchResult for the download
        search_result = SearchResult(
            instrument_number=document.instrument_number,
            document_type=document.document_type.value,
            download_url=source_url
        )

        # Get generic adapter for download
        from app.scraping.adapters.generic_adapter import GenericCountyAdapter
        adapter = GenericCountyAdapter({"county_name": "download"})

        return await adapter.download_document(page, search_result, download_path)


@celery_app.task
def check_county_health():
    """Periodic task to check health of all county configurations"""
    from app.models.county import CountyConfig

    db = get_db_session()

    try:
        counties = db.query(CountyConfig).filter(
            CountyConfig.scraping_enabled == True
        ).all()

        healthy_count = 0
        unhealthy_count = 0

        for county in counties:
            # Check if last successful scrape was within 7 days
            if county.last_successful_scrape:
                days_since = (datetime.utcnow() - county.last_successful_scrape).days
                if days_since > 7 and county.consecutive_failures >= 3:
                    county.is_healthy = False
                    unhealthy_count += 1
                else:
                    county.is_healthy = True
                    healthy_count += 1
            else:
                # Never successfully scraped
                if county.consecutive_failures >= 3:
                    county.is_healthy = False
                    unhealthy_count += 1

        db.commit()

        logger.info(f"Health check: {healthy_count} healthy, {unhealthy_count} unhealthy counties")

        return {
            "healthy": healthy_count,
            "unhealthy": unhealthy_count,
            "total": len(counties)
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task
def test_county_adapter(county_name: str):
    """Test a county adapter with a simple search"""

    try:
        result = run_async(_test_adapter(county_name))
        return result

    except Exception as e:
        logger.error(f"Adapter test failed: {e}")
        return {
            "success": False,
            "county": county_name,
            "error": str(e)
        }


async def _test_adapter(county_name: str):
    """Async adapter test"""
    from app.scraping.browser_pool import get_browser_pool
    from app.scraping.adapters import get_adapter_for_county

    config = {
        "county_name": county_name,
        "requests_per_minute": 5,
        "delay_between_requests_ms": 3000,
    }

    adapter = get_adapter_for_county(county_name, config)
    if not adapter:
        return {
            "success": False,
            "county": county_name,
            "error": "No adapter available"
        }

    pool = await get_browser_pool()

    async with pool.acquire(county_name) as browser_instance:
        page = browser_instance.page

        initialized = await adapter.initialize(page)

        return {
            "success": initialized,
            "county": county_name,
            "adapter": adapter.__class__.__name__,
            "message": "Initialization successful" if initialized else "Initialization failed"
        }
