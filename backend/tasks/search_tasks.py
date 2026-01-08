"""Search orchestration tasks"""
from celery import chain, group, chord
from tasks.celery_app import celery_app
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_db_session():
    """Get synchronous database session for Celery tasks"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os

    database_url = os.getenv("DATABASE_URL", "sqlite:///./title_search.db")
    # Convert async URL to sync
    sync_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def orchestrate_search(self, search_id: int):
    """
    Main orchestration task that coordinates the entire title search workflow.

    Workflow:
    1. Initialize search and get property info
    2. Scrape county recorder records
    3. Scrape court records (if available)
    4. Download all discovered documents
    5. OCR and AI analysis (parallel)
    6. Build chain of title
    7. Identify encumbrances
    8. Generate title report
    9. Finalize search
    """
    from app.models.search import TitleSearch, SearchStatus
    from app.models.property import Property

    db = get_db_session()

    try:
        # Get search record
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        if not search:
            logger.error(f"Search {search_id} not found")
            return {"success": False, "error": "Search not found"}

        # Update status to processing
        search.status = SearchStatus.QUEUED
        search.started_at = datetime.utcnow()
        search.celery_task_id = self.request.id
        search.status_message = "Search queued for processing"
        db.commit()

        # Get property info
        property_obj = search.property
        county = property_obj.county
        parcel = property_obj.parcel_number
        address = property_obj.street_address

        logger.info(f"Starting search {search_id} for {address}, {county} County")

        # Build the workflow chain
        workflow = chain(
            # Step 1: Scrape county recorder
            scrape_county_recorder.s(search_id, county, parcel, address),

            # Step 2: Scrape court records
            scrape_court_records.s(search_id, county),

            # Step 3: Download all documents
            download_all_documents.s(search_id),

            # Step 4: Analyze documents (will be called after download)
            analyze_all_documents.s(search_id),

            # Step 5: Build chain of title
            build_chain_of_title.s(search_id),

            # Step 6: Calculate risk and generate report
            generate_report.s(search_id),

            # Step 7: Finalize
            finalize_search.s(search_id),
        )

        # Execute workflow
        result = workflow.apply_async()

        return {
            "success": True,
            "search_id": search_id,
            "workflow_id": result.id
        }

    except Exception as e:
        logger.exception(f"Search orchestration failed for {search_id}: {e}")

        # Update search status
        try:
            search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
            if search:
                search.status = SearchStatus.FAILED
                search.status_message = f"Orchestration error: {str(e)}"
                search.error_log = search.error_log or []
                search.error_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "task": "orchestrate_search",
                    "error": str(e)
                })
                db.commit()
        except Exception:
            pass

        # Retry if not max retries
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

        return {"success": False, "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True)
def scrape_county_recorder(self, search_id: int, county: str, parcel: str, address: str):
    """Scrape county recorder website for documents"""
    from app.models.search import TitleSearch, SearchStatus

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        search.status = SearchStatus.SCRAPING
        search.status_message = f"Scraping {county} County recorder records..."
        search.progress_percent = 10
        db.commit()

        # Import and run scraping
        from tasks.scraping_tasks import scrape_county_records
        result = scrape_county_records.delay(search_id, county, parcel, address)

        # Wait for result (with timeout)
        scrape_result = result.get(timeout=300)

        search.progress_percent = 30
        search.status_message = f"Found {scrape_result.get('document_count', 0)} documents from recorder"
        db.commit()

        return scrape_result

    except Exception as e:
        logger.error(f"County recorder scraping failed: {e}")
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        if search:
            search.error_log = search.error_log or []
            search.error_log.append({
                "timestamp": datetime.utcnow().isoformat(),
                "task": "scrape_county_recorder",
                "error": str(e)
            })
            db.commit()
        return {"success": False, "error": str(e), "document_count": 0}

    finally:
        db.close()


@celery_app.task(bind=True)
def scrape_court_records(self, previous_result: dict, search_id: int, county: str):
    """Scrape court records for judgments, lis pendens, etc."""
    from app.models.search import TitleSearch

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        search.status_message = f"Searching {county} County court records..."
        search.progress_percent = 35
        db.commit()

        # TODO: Implement court records scraping
        # For now, return placeholder
        logger.info(f"Court records scraping for {county} County (not yet implemented)")

        search.progress_percent = 40
        db.commit()

        return {
            "success": True,
            "court_records_count": 0,
            "previous_result": previous_result
        }

    except Exception as e:
        logger.error(f"Court records scraping failed: {e}")
        return {"success": False, "error": str(e), "court_records_count": 0}

    finally:
        db.close()


@celery_app.task(bind=True)
def download_all_documents(self, previous_result: dict, search_id: int):
    """Download all discovered documents"""
    from app.models.search import TitleSearch
    from app.models.document import Document

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        search.status_message = "Downloading documents..."
        search.progress_percent = 45
        db.commit()

        # Get documents that need downloading
        documents = db.query(Document).filter(
            Document.search_id == search_id,
            Document.file_path.is_(None),
            Document.source_url.isnot(None)
        ).all()

        downloaded = 0
        for doc in documents:
            try:
                # Import download task
                from tasks.scraping_tasks import download_document
                result = download_document.delay(doc.id, doc.source_url)
                result.get(timeout=60)
                downloaded += 1
            except Exception as e:
                logger.warning(f"Failed to download document {doc.id}: {e}")

        search.progress_percent = 55
        search.status_message = f"Downloaded {downloaded} documents"
        db.commit()

        return {
            "success": True,
            "downloaded_count": downloaded,
            "total_documents": len(documents)
        }

    except Exception as e:
        logger.error(f"Document download failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True)
def analyze_all_documents(self, previous_result: dict, search_id: int):
    """Analyze all documents with OCR and AI"""
    from app.models.search import TitleSearch, SearchStatus
    from app.models.document import Document

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        search.status = SearchStatus.ANALYZING
        search.status_message = "Analyzing documents with AI..."
        search.progress_percent = 60
        db.commit()

        # Get documents that need analysis
        documents = db.query(Document).filter(
            Document.search_id == search_id,
            Document.ai_analysis_at.is_(None)
        ).all()

        analyzed = 0
        for doc in documents:
            try:
                from tasks.ai_tasks import analyze_document
                result = analyze_document.delay(doc.id)
                result.get(timeout=120)
                analyzed += 1
            except Exception as e:
                logger.warning(f"Failed to analyze document {doc.id}: {e}")

        search.progress_percent = 70
        search.status_message = f"Analyzed {analyzed} documents"
        db.commit()

        return {
            "success": True,
            "analyzed_count": analyzed,
            "total_documents": len(documents)
        }

    except Exception as e:
        logger.error(f"Document analysis failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True)
def build_chain_of_title(self, previous_result: dict, search_id: int):
    """Build the chain of title from analyzed documents"""
    from app.models.search import TitleSearch
    from app.models.document import Document, DocumentType
    from app.models.chain_of_title import ChainOfTitleEntry

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        search.status_message = "Building chain of title..."
        search.progress_percent = 75
        db.commit()

        # Get deed documents ordered by date
        deeds = db.query(Document).filter(
            Document.search_id == search_id,
            Document.document_type.in_([
                DocumentType.DEED,
                DocumentType.DEED_OF_TRUST,
            ])
        ).order_by(Document.recording_date.asc()).all()

        # Create chain entries
        sequence = 1
        for deed in deeds:
            entry = ChainOfTitleEntry(
                search_id=search_id,
                document_id=deed.id,
                sequence_number=sequence,
                transaction_type=deed.document_type.value,
                transaction_date=deed.recording_date,
                grantor_names=deed.grantor or [],
                grantee_names=deed.grantee or [],
                recording_reference=deed.instrument_number,
                description=deed.ai_summary
            )
            db.add(entry)
            sequence += 1

        db.commit()

        search.progress_percent = 80
        search.status_message = f"Built chain with {sequence - 1} entries"
        db.commit()

        return {
            "success": True,
            "chain_entries": sequence - 1
        }

    except Exception as e:
        logger.error(f"Chain of title building failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True)
def generate_report(self, previous_result: dict, search_id: int):
    """Generate the title report"""
    from app.models.search import TitleSearch, SearchStatus

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        search.status = SearchStatus.GENERATING
        search.status_message = "Generating title report..."
        search.progress_percent = 85
        db.commit()

        # Import and run report generation
        from tasks.report_tasks import generate_title_report
        result = generate_title_report.delay(search_id)
        report_result = result.get(timeout=180)

        search.progress_percent = 95
        search.status_message = "Report generated"
        db.commit()

        return report_result

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True)
def finalize_search(self, previous_result: dict, search_id: int):
    """Finalize the search and mark as complete"""
    from app.models.search import TitleSearch, SearchStatus

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()

        search.status = SearchStatus.COMPLETED
        search.status_message = "Search completed successfully"
        search.progress_percent = 100
        search.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Search {search_id} completed successfully")

        return {
            "success": True,
            "search_id": search_id,
            "completed_at": search.completed_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Search finalization failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


@celery_app.task
def cleanup_stale_searches():
    """Cleanup searches that have been stuck for too long"""
    from app.models.search import TitleSearch, SearchStatus

    db = get_db_session()

    try:
        # Find searches stuck in processing for more than 2 hours
        cutoff = datetime.utcnow() - timedelta(hours=2)

        stale_searches = db.query(TitleSearch).filter(
            TitleSearch.status.in_([
                SearchStatus.QUEUED,
                SearchStatus.SCRAPING,
                SearchStatus.ANALYZING,
                SearchStatus.GENERATING
            ]),
            TitleSearch.started_at < cutoff
        ).all()

        for search in stale_searches:
            search.status = SearchStatus.FAILED
            search.status_message = "Search timed out after 2 hours"
            search.error_log = search.error_log or []
            search.error_log.append({
                "timestamp": datetime.utcnow().isoformat(),
                "task": "cleanup_stale_searches",
                "error": "Timeout"
            })

        db.commit()

        logger.info(f"Cleaned up {len(stale_searches)} stale searches")

        return {"cleaned_up": len(stale_searches)}

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"error": str(e)}

    finally:
        db.close()
