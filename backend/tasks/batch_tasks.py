"""Batch processing Celery tasks"""
from tasks.celery_app import celery_app
from datetime import datetime
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


@celery_app.task(bind=True, max_retries=1)
def process_batch(self, batch_id: int):
    """
    Process a batch of title search requests.

    This task processes each item in the batch, creating title searches
    for each valid record.
    """
    from app.models.batch import BatchUpload, BatchItem, BatchStatus
    from app.models.property import Property
    from app.models.search import TitleSearch, SearchStatus, SearchPriority
    import secrets

    db = get_db_session()

    try:
        # Get batch
        batch = db.query(BatchUpload).filter(BatchUpload.id == batch_id).first()
        if not batch:
            logger.error(f"Batch {batch_id} not found")
            return {"success": False, "error": "Batch not found"}

        logger.info(f"Processing batch {batch.batch_number} with {batch.total_records} items")

        # Get all pending items
        items = db.query(BatchItem).filter(
            BatchItem.batch_id == batch_id,
            BatchItem.status == "pending"
        ).all()

        processed = 0
        successful = 0
        failed = 0

        for item in items:
            try:
                # Validate required fields
                if not item.street_address or not item.city or not item.county:
                    item.status = "failed"
                    item.error_message = "Missing required fields (street_address, city, county)"
                    item.processed_at = datetime.utcnow()
                    failed += 1
                    processed += 1
                    continue

                # Create or get property
                property_obj = db.query(Property).filter(
                    Property.street_address == item.street_address,
                    Property.city == item.city,
                    Property.county == item.county
                ).first()

                if not property_obj:
                    property_obj = Property(
                        street_address=item.street_address,
                        city=item.city,
                        county=item.county,
                        state="CO",  # Default to Colorado
                        parcel_number=item.parcel_number,
                        raw_address_input=f"{item.street_address}, {item.city}, CO"
                    )
                    db.add(property_obj)
                    db.flush()

                # Generate reference number
                year = datetime.utcnow().year
                ref_number = f"TS-{year}-{secrets.token_hex(4).upper()}"

                # Create search
                search = TitleSearch(
                    reference_number=ref_number,
                    property_id=property_obj.id,
                    requested_by=batch.uploaded_by,
                    search_type="full",
                    search_years=settings.SCRAPING_DEFAULT_SEARCH_YEARS,
                    priority=SearchPriority.NORMAL,
                    status=SearchStatus.PENDING
                )
                db.add(search)
                db.flush()

                # Update item
                item.search_id = search.id
                item.status = "completed"
                item.processed_at = datetime.utcnow()

                successful += 1
                processed += 1

                # Queue the search task
                try:
                    from tasks.search_tasks import orchestrate_search
                    orchestrate_search.apply_async(
                        args=[search.id],
                        queue="default",
                        countdown=processed  # Stagger the searches
                    )
                except Exception as e:
                    logger.warning(f"Failed to queue search task for item {item.id}: {e}")
                    # Search is created but not queued - can be retried

            except Exception as e:
                logger.error(f"Failed to process batch item {item.id}: {e}")
                item.status = "failed"
                item.error_message = str(e)
                item.processed_at = datetime.utcnow()
                failed += 1
                processed += 1

            # Update batch progress periodically
            if processed % 10 == 0:
                batch.processed_records = processed
                batch.successful_records = successful
                batch.failed_records = failed
                db.commit()

        # Finalize batch
        batch.processed_records = processed
        batch.successful_records = successful
        batch.failed_records = failed
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Batch {batch.batch_number} completed: "
            f"{successful} successful, {failed} failed out of {processed} processed"
        )

        return {
            "success": True,
            "batch_id": batch_id,
            "processed": processed,
            "successful": successful,
            "failed": failed
        }

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")

        # Mark batch as failed
        try:
            batch = db.query(BatchUpload).filter(BatchUpload.id == batch_id).first()
            if batch:
                batch.status = BatchStatus.FAILED
                db.commit()
        except Exception:
            pass

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {"success": False, "error": str(e)}

    finally:
        db.close()
