"""
Integration tests for the title search workflow with actual database.

Run with: python -m tests.test_integration
"""
import os
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up test environment BEFORE importing anything that uses settings
TEST_DB = "sqlite+aiosqlite:///./test_title_search.db"
os.environ["DATABASE_URL"] = TEST_DB
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "True"
os.environ["STORAGE_PATH"] = "./test_storage"

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum, Float, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
import enum

# Create our own Base for testing (avoid async database module)
Base = declarative_base()


# Re-define models for sync testing
class SearchStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DocumentType(str, enum.Enum):
    DEED = "deed"
    MORTGAGE = "mortgage"
    DEED_OF_TRUST = "deed_of_trust"
    LIEN = "lien"
    JUDGMENT = "judgment"
    EASEMENT = "easement"
    PLAT = "plat"
    SURVEY = "survey"
    TAX_RECORD = "tax_record"
    COURT_FILING = "court_filing"
    UCC_FILING = "ucc_filing"
    LIS_PENDENS = "lis_pendens"
    BANKRUPTCY = "bankruptcy"
    RELEASE = "release"
    SATISFACTION = "satisfaction"
    ASSIGNMENT = "assignment"
    SUBORDINATION = "subordination"
    OTHER = "other"


class DocumentSource(str, enum.Enum):
    COUNTY_RECORDER = "county_recorder"
    COURT_RECORDS = "court_records"
    COMMERCIAL_API = "commercial_api"
    MANUAL_UPLOAD = "manual_upload"


class TransactionType(str, enum.Enum):
    WARRANTY_DEED = "warranty_deed"
    QUIT_CLAIM_DEED = "quit_claim_deed"
    SPECIAL_WARRANTY_DEED = "special_warranty_deed"
    TRUST_DEED = "trust_deed"
    DEED_OF_TRUST = "deed_of_trust"
    MORTGAGE = "mortgage"
    FORECLOSURE = "foreclosure"
    TAX_DEED = "tax_deed"
    SHERIFFS_DEED = "sheriffs_deed"
    COURT_ORDER = "court_order"


class EncumbranceType(str, enum.Enum):
    MORTGAGE = "mortgage"
    DEED_OF_TRUST = "deed_of_trust"
    TAX_LIEN = "tax_lien"
    MECHANICS_LIEN = "mechanics_lien"
    JUDGMENT_LIEN = "judgment_lien"
    HOA_LIEN = "hoa_lien"
    IRS_LIEN = "irs_lien"
    STATE_TAX_LIEN = "state_tax_lien"
    EASEMENT = "easement"
    RESTRICTION = "restriction"
    COVENANT = "covenant"
    LIS_PENDENS = "lis_pendens"
    BANKRUPTCY = "bankruptcy"
    UCC_FILING = "ucc_filing"
    ASSESSMENT = "assessment"
    OTHER = "other"


class EncumbranceStatus(str, enum.Enum):
    ACTIVE = "active"
    RELEASED = "released"
    SATISFIED = "satisfied"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class ReportStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ISSUED = "issued"


# Sync test models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    hashed_password = Column(String(255))
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)


class Property(Base):
    __tablename__ = "properties"
    id = Column(Integer, primary_key=True)
    street_address = Column(String(255))
    city = Column(String(100))
    county = Column(String(100))
    state = Column(String(2), default="CO")
    zip_code = Column(String(10))
    parcel_number = Column(String(50))
    legal_description = Column(Text)
    latitude = Column(String(20))
    longitude = Column(String(20))
    raw_address_input = Column(String(500))
    normalized_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TitleSearch(Base):
    __tablename__ = "title_searches"
    id = Column(Integer, primary_key=True)
    reference_number = Column(String(50), unique=True)
    property_id = Column(Integer, ForeignKey("properties.id"))
    requested_by = Column(Integer, ForeignKey("users.id"))
    search_type = Column(String(50), default="full")
    search_years = Column(Integer, default=40)
    priority = Column(Enum(SearchPriority), default=SearchPriority.NORMAL)
    status = Column(Enum(SearchStatus), default=SearchStatus.PENDING)
    status_message = Column(Text)
    progress_percent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    celery_task_id = Column(String(100))
    retry_count = Column(Integer, default=0)
    error_log = Column(JSON, default=list)
    preferred_source = Column(String(50), default="scraping")
    property = relationship("Property")


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"))
    document_type = Column(Enum(DocumentType))
    instrument_number = Column(String(100))
    recording_number = Column(String(100))
    book = Column(String(20))
    page = Column(String(20))
    recording_date = Column(DateTime)
    effective_date = Column(DateTime)
    grantor = Column(JSON, default=list)
    grantee = Column(JSON, default=list)
    consideration = Column(String(50))
    source = Column(Enum(DocumentSource))
    source_url = Column(String(500))
    file_path = Column(String(500))
    file_name = Column(String(255))
    file_size = Column(Integer)
    file_hash = Column(String(64))
    mime_type = Column(String(100), default="application/pdf")
    ocr_text = Column(Text)
    ocr_confidence = Column(Integer)
    ai_summary = Column(Text)
    ai_extracted_data = Column(JSON)
    ai_analysis_at = Column(DateTime)
    is_critical = Column(Boolean, default=False)
    needs_review = Column(Boolean, default=False)
    review_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ChainOfTitleEntry(Base):
    __tablename__ = "chain_of_title_entries"
    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"))
    document_id = Column(Integer, ForeignKey("documents.id"))
    sequence_number = Column(Integer)
    transaction_type = Column(String(100))
    transaction_date = Column(DateTime)
    grantor_names = Column(JSON, default=list)
    grantee_names = Column(JSON, default=list)
    consideration = Column(Float)
    recording_reference = Column(String(200))
    description = Column(Text)
    ai_narrative = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Encumbrance(Base):
    __tablename__ = "encumbrances"
    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"))
    document_id = Column(Integer, ForeignKey("documents.id"))
    encumbrance_type = Column(Enum(EncumbranceType))
    status = Column(Enum(EncumbranceStatus))
    holder_name = Column(String(255))
    original_amount = Column(Float)
    current_amount = Column(Float)
    recorded_date = Column(DateTime)
    effective_date = Column(DateTime)
    maturity_date = Column(DateTime)
    released_date = Column(DateTime)
    recording_reference = Column(String(200))
    description = Column(Text)
    risk_level = Column(String(20), default="medium")
    risk_notes = Column(Text)
    requires_action = Column(Boolean, default=True)
    action_description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TitleReport(Base):
    __tablename__ = "title_reports"
    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("title_searches.id"))
    report_number = Column(String(50), unique=True)
    report_type = Column(String(50), default="commitment")
    status = Column(Enum(ReportStatus), default=ReportStatus.DRAFT)
    effective_date = Column(DateTime)
    expiration_date = Column(DateTime)
    schedule_a = Column(JSON)
    schedule_b1 = Column(JSON)
    schedule_b2 = Column(JSON)
    chain_of_title_narrative = Column(Text)
    risk_assessment_summary = Column(Text)
    risk_score = Column(Integer)
    ai_recommendations = Column(JSON)
    pdf_path = Column(String(500))
    pdf_generated_at = Column(DateTime)
    json_export_path = Column(String(500))
    csv_export_path = Column(String(500))
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CountyConfig(Base):
    __tablename__ = "county_configs"
    id = Column(Integer, primary_key=True)
    county_name = Column(String(100))
    state = Column(String(2))
    recorder_url = Column(String(500))
    scraping_adapter = Column(String(50))
    scraping_enabled = Column(Boolean, default=True)
    is_healthy = Column(Boolean, default=True)
    requests_per_minute = Column(Integer, default=10)
    delay_between_requests_ms = Column(Integer, default=2000)


# Setup Celery eager mode
from tasks.celery_app import celery_app
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
)


def setup_database():
    """Create test database and tables"""
    print("Setting up test database...")

    # Remove existing test database
    if os.path.exists("test_title_search.db"):
        try:
            os.remove("test_title_search.db")
        except PermissionError:
            pass  # File in use, continue anyway

    # Use sync URL for setup
    sync_db = "sqlite:///./test_title_search.db"
    engine = create_engine(sync_db)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def teardown_database():
    """Clean up test database"""
    if os.path.exists("test_title_search.db"):
        os.remove("test_title_search.db")
    if os.path.exists("test_storage"):
        shutil.rmtree("test_storage", ignore_errors=True)


def seed_test_data(db):
    """Create test data"""
    print("Seeding test data...")

    # Create test user
    user = User(
        email="test@example.com",
        hashed_password="test_hash",
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    db.commit()

    # Create county config
    county = CountyConfig(
        county_name="Denver",
        state="CO",
        recorder_url="https://denver.coloradoview.net/",
        scraping_adapter="denver",
        scraping_enabled=True,
        is_healthy=True,
        requests_per_minute=10,
        delay_between_requests_ms=2000
    )
    db.add(county)
    db.commit()

    # Create property
    property_obj = Property(
        street_address="123 Test Street",
        city="Denver",
        county="Denver",
        state="CO",
        zip_code="80202",
        parcel_number="123-456-789",
        legal_description="Lot 1, Block 1, Test Subdivision"
    )
    db.add(property_obj)
    db.commit()

    # Create search
    search = TitleSearch(
        reference_number="TS-2026-TEST001",
        property_id=property_obj.id,
        requested_by=user.id,
        search_type="full",
        search_years=40,
        priority=SearchPriority.NORMAL,
        status=SearchStatus.PENDING
    )
    db.add(search)
    db.commit()

    return {
        "user": user,
        "property": property_obj,
        "search": search,
        "county": county
    }


def test_document_creation(db, search):
    """Test creating documents for a search"""
    print("\n=== Test: Document Creation ===")

    doc1 = Document(
        search_id=search.id,
        document_type=DocumentType.DEED,
        instrument_number="2020-123456",
        recording_date=datetime(2020, 5, 15),
        grantor=["John Smith"],
        grantee=["Jane Doe"],
        consideration="$350,000",
        source=DocumentSource.COUNTY_RECORDER
    )
    db.add(doc1)

    doc2 = Document(
        search_id=search.id,
        document_type=DocumentType.DEED_OF_TRUST,
        instrument_number="2020-123457",
        recording_date=datetime(2020, 5, 15),
        grantor=["Jane Doe"],
        grantee=["First Bank"],
        consideration="$280,000",
        source=DocumentSource.COUNTY_RECORDER
    )
    db.add(doc2)

    db.commit()

    docs = db.query(Document).filter(Document.search_id == search.id).all()
    assert len(docs) == 2, f"Expected 2 documents, got {len(docs)}"
    print(f"  Created {len(docs)} documents")
    print("[OK] Document creation works")


def test_chain_of_title_creation(db, search):
    """Test creating chain of title entries"""
    print("\n=== Test: Chain of Title Creation ===")

    entries = [
        ChainOfTitleEntry(
            search_id=search.id,
            sequence_number=1,
            grantor_names=["Original Owner LLC"],
            grantee_names=["John Smith", "Mary Smith"],
            transaction_type="warranty_deed",
            recording_reference="2015-100000",
            transaction_date=datetime(2015, 3, 20),
            consideration=250000.00
        ),
        ChainOfTitleEntry(
            search_id=search.id,
            sequence_number=2,
            grantor_names=["John Smith", "Mary Smith"],
            grantee_names=["Jane Doe"],
            transaction_type="warranty_deed",
            recording_reference="2020-123456",
            transaction_date=datetime(2020, 5, 15),
            consideration=350000.00
        )
    ]

    for entry in entries:
        db.add(entry)
    db.commit()

    chain = db.query(ChainOfTitleEntry).filter(
        ChainOfTitleEntry.search_id == search.id
    ).order_by(ChainOfTitleEntry.sequence_number).all()

    assert len(chain) == 2, f"Expected 2 chain entries, got {len(chain)}"
    assert chain[0].sequence_number == 1
    assert chain[1].sequence_number == 2

    print(f"  Created {len(chain)} chain of title entries")
    print("[OK] Chain of title creation works")


def test_encumbrance_creation(db, search):
    """Test creating encumbrances"""
    print("\n=== Test: Encumbrance Creation ===")

    enc1 = Encumbrance(
        search_id=search.id,
        encumbrance_type=EncumbranceType.DEED_OF_TRUST,
        status=EncumbranceStatus.ACTIVE,
        holder_name="First Bank",
        original_amount=280000.00,
        current_amount=280000.00,
        recording_reference="2020-123457",
        recorded_date=datetime(2020, 5, 15),
        description="First mortgage"
    )
    db.add(enc1)

    enc2 = Encumbrance(
        search_id=search.id,
        encumbrance_type=EncumbranceType.EASEMENT,
        status=EncumbranceStatus.ACTIVE,
        holder_name="City of Denver",
        recording_reference="2010-050000",
        recorded_date=datetime(2010, 1, 15),
        description="Utility easement along north boundary"
    )
    db.add(enc2)

    db.commit()

    encumbrances = db.query(Encumbrance).filter(
        Encumbrance.search_id == search.id
    ).all()

    assert len(encumbrances) == 2, f"Expected 2 encumbrances, got {len(encumbrances)}"
    print(f"  Created {len(encumbrances)} encumbrances")
    print("[OK] Encumbrance creation works")


def test_report_generation(db, search):
    """Test report generation task"""
    print("\n=== Test: Report Generation Task ===")

    from tasks.report_tasks import generate_title_report

    # Run the report generation task
    result = generate_title_report.delay(search.id)
    task_result = result.get()

    print(f"  Task result: {task_result}")

    assert task_result["success"] == True, f"Report generation failed: {task_result}"
    assert "report_id" in task_result

    # Check report was created
    report = db.query(TitleReport).filter(
        TitleReport.search_id == search.id
    ).first()

    db.refresh(report)

    assert report is not None, "Report not created"
    assert report.schedule_a is not None, "Schedule A not populated"
    assert report.schedule_b1 is not None, "Schedule B-1 not populated"
    assert report.schedule_b2 is not None, "Schedule B-2 not populated"
    assert report.risk_score is not None, "Risk score not calculated"

    print(f"  Report ID: {report.id}")
    print(f"  Risk Score: {report.risk_score}")
    print(f"  Schedule A: {bool(report.schedule_a)}")
    print(f"  Schedule B-1: {len(report.schedule_b1)} requirements")
    print(f"  Schedule B-2: {len(report.schedule_b2)} exceptions")
    print("[OK] Report generation works")

    return report


def test_risk_assessment(db, search):
    """Test risk assessment task"""
    print("\n=== Test: Risk Assessment Task ===")

    from tasks.ai_tasks import generate_risk_assessment

    result = generate_risk_assessment.delay(search.id)
    task_result = result.get()

    print(f"  Task result: {task_result}")

    assert task_result["success"] == True, f"Risk assessment failed: {task_result}"
    assert "risk_score" in task_result
    assert "risk_level" in task_result
    assert "risk_factors" in task_result

    print(f"  Risk Score: {task_result['risk_score']}")
    print(f"  Risk Level: {task_result['risk_level']}")
    print(f"  Risk Factors: {len(task_result['risk_factors'])}")
    print("[OK] Risk assessment works")


def test_search_status_updates(db, search):
    """Test search status progression"""
    print("\n=== Test: Search Status Updates ===")

    # Test status transitions
    statuses = [
        SearchStatus.QUEUED,
        SearchStatus.SCRAPING,
        SearchStatus.ANALYZING,
        SearchStatus.GENERATING,
        SearchStatus.COMPLETED
    ]

    for status in statuses:
        search.status = status
        search.progress_percent = (statuses.index(status) + 1) * 20
        db.commit()
        db.refresh(search)
        print(f"  Status: {search.status.value} - Progress: {search.progress_percent}%")

    assert search.status == SearchStatus.COMPLETED
    assert search.progress_percent == 100
    print("[OK] Search status updates work")


def run_integration_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("TITLE SEARCH INTEGRATION TESTS")
    print("Testing with SQLite database")
    print("=" * 60)

    db = None
    try:
        db = setup_database()
        test_data = seed_test_data(db)

        search = test_data["search"]

        test_document_creation(db, search)
        test_chain_of_title_creation(db, search)
        test_encumbrance_creation(db, search)
        test_search_status_updates(db, search)
        test_risk_assessment(db, search)
        test_report_generation(db, search)

        print("\n" + "=" * 60)
        print("ALL INTEGRATION TESTS PASSED!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n[FAILED] Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if db:
            db.close()
        teardown_database()


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
