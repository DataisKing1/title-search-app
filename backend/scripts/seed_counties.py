"""
Seed script for Colorado county configurations.

Run with: python -m scripts.seed_counties
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.county import CountyConfig


# Colorado counties with REAL recorder website information
# Updated with verified URLs for actual county recorder portals
COLORADO_COUNTIES = [
    # Major Front Range Counties
    {
        "county_name": "Denver",
        "state": "CO",
        "fips_code": "08031",
        "recorder_url": "https://denvergov.org/Government/Departments/Office-of-the-Clerk-and-Recorder/find-records",
        "assessor_url": "https://www.denvergov.org/property",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=2",
        "scraping_adapter": "denver",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://countyfusion3.kofiletech.us/countyweb/loginDisplay.action?countyname=Denver",
            "system": "kofile_countyfusion",
            "has_online_search": True,
            "guest_access": True,
            "search_by": ["name", "reception_number", "book_page", "date_range"],
            "document_types": ["deed", "mortgage", "lien", "release", "easement", "plat"],
            "frame_structure": {
                "body": "iframe[name='bodyframe']",
                "search": "iframe[name='dynSearchFrame']",
                "criteria": "iframe#criteriaframe",
                "results": "iframe[name='resultFrame']"
            },
            "selectors": {
                "name_input": "input#allNames",
                "from_date": "input#FROMDATE",
                "to_date": "input#TODATE",
                "search_btn": "img#imgSearch",
                "clear_btn": "img#imgClear",
                "party_all": "input#partyRBBoth",
                "party_grantor": "input#partyRB1",
                "party_grantee": "input#partyRB2"
            }
        },
        "notes": "Denver City and County - KoFile CountyFusion system with guest access"
    },
    {
        "county_name": "El Paso",
        "state": "CO",
        "fips_code": "08041",
        "recorder_url": "https://car.elpasoco.com/",
        "assessor_url": "https://assessor.elpasoco.com/",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=4",
        "scraping_adapter": "el_paso",
        "requests_per_minute": 8,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://car.elpasoco.com/",
            "has_online_search": True,
            "search_by": ["name", "reception_number", "legal_description"]
        },
        "notes": "El Paso County (Colorado Springs) - CAR online portal"
    },
    {
        "county_name": "Arapahoe",
        "state": "CO",
        "fips_code": "08005",
        "recorder_url": "https://www.arapahoegov.com/703/Recording",
        "assessor_url": "https://www.arapahoegov.com/159/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=18",
        "scraping_adapter": "arapahoe",
        "requests_per_minute": 8,
        "delay_between_requests_ms": 2500,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://countyfusion6.kofiletech.us/countyweb/loginDisplay.action?countyname=ArapahoeCounty",
            "system": "kofile",
            "has_online_search": True,
            "search_by": ["name", "parcel", "date_range"]
        },
        "notes": "Arapahoe County - Uses KoFile/CountyFusion system"
    },
    {
        "county_name": "Jefferson",
        "state": "CO",
        "fips_code": "08059",
        "recorder_url": "https://www.jeffco.us/588/Recording-Documents",
        "assessor_url": "https://www.jeffco.us/529/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=1",
        "scraping_adapter": "jefferson",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://recordings.jeffco.us/",
            "has_online_search": True,
            "search_by": ["name", "reception_number", "date_range"]
        },
        "notes": "Jefferson County (Lakewood/Golden) - Direct recordings portal"
    },
    {
        "county_name": "Adams",
        "state": "CO",
        "fips_code": "08001",
        "recorder_url": "https://www.adcogov.org/recording",
        "assessor_url": "https://www.adcogov.org/assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=17",
        "scraping_adapter": "adams",
        "requests_per_minute": 8,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://countyfusion2.kofiletech.us/countyweb/loginDisplay.action?countyname=AdamsCountyCO",
            "system": "kofile",
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Adams County (Brighton/Commerce City) - KoFile system"
    },
    {
        "county_name": "Douglas",
        "state": "CO",
        "fips_code": "08035",
        "recorder_url": "https://www.douglas.co.us/clerk/recording/",
        "assessor_url": "https://www.douglas.co.us/assessor/",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=18",
        "scraping_adapter": "douglas",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2500,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://apps.douglas.co.us/recorder/web/",
            "has_online_search": True,
            "search_by": ["name", "parcel", "reception_number"]
        },
        "notes": "Douglas County (Castle Rock/Highlands Ranch) - Direct portal"
    },
    {
        "county_name": "Boulder",
        "state": "CO",
        "fips_code": "08013",
        "recorder_url": "https://www.bouldercounty.gov/departments/clerk-recorder/",
        "assessor_url": "https://www.bouldercounty.gov/departments/assessor/",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=20",
        "scraping_adapter": "boulder",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://recording.bouldercounty.gov/countyweb/loginDisplay.action?countyname=BoulderCountyCO",
            "system": "kofile",
            "has_online_search": True,
            "search_by": ["name", "parcel", "reception_number"]
        },
        "notes": "Boulder County - KoFile/CountyFusion system"
    },
    {
        "county_name": "Larimer",
        "state": "CO",
        "fips_code": "08069",
        "recorder_url": "https://www.larimer.gov/clerk/recording",
        "assessor_url": "https://www.larimer.gov/assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=8",
        "scraping_adapter": "larimer",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://records.larimer.gov/LandmarkWeb/",
            "system": "landmark",
            "has_online_search": True,
            "search_by": ["name", "parcel", "reception_number", "legal"]
        },
        "notes": "Larimer County (Fort Collins/Loveland) - Landmark Web system"
    },
    {
        "county_name": "Weld",
        "state": "CO",
        "fips_code": "08123",
        "recorder_url": "https://www.weldgov.com/departments/clerk_and_recorder/recording",
        "assessor_url": "https://www.weldgov.com/departments/assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=19",
        "scraping_adapter": "weld",
        "requests_per_minute": 8,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "search_portal": "https://www.weldgov.com/departments/clerk_and_recorder/recording/search-recorded-documents",
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Weld County (Greeley) - Direct search portal"
    },
    {
        "county_name": "Pueblo",
        "state": "CO",
        "fips_code": "08101",
        "recorder_url": "https://www.pueblocounty.us/331/Recording",
        "assessor_url": "https://www.pueblocounty.us/147/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=10",
        "scraping_adapter": "pueblo",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2500,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Pueblo County - Online records available"
    },
    {
        "county_name": "Mesa",
        "state": "CO",
        "fips_code": "08077",
        "recorder_url": "https://clerk.mesacounty.us/recording/",
        "assessor_url": "https://assessor.mesacounty.us/",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=21",
        "scraping_adapter": "mesa",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Mesa County (Grand Junction) - Western Slope"
    },
    {
        "county_name": "Broomfield",
        "state": "CO",
        "fips_code": "08014",
        "recorder_url": "https://www.broomfield.org/201/Recording",
        "assessor_url": "https://www.broomfield.org/198/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=17",
        "scraping_adapter": "broomfield",
        "requests_per_minute": 10,
        "delay_between_requests_ms": 2000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "City and County of Broomfield - Combined city/county government"
    },
    # Mountain/Resort Counties
    {
        "county_name": "Eagle",
        "state": "CO",
        "fips_code": "08037",
        "recorder_url": "https://www.eaglecounty.us/Clerk/Recording/",
        "assessor_url": "https://www.eaglecounty.us/Assessor/",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=5",
        "scraping_adapter": "eagle",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Eagle County (Vail/Beaver Creek) - Resort area"
    },
    {
        "county_name": "Summit",
        "state": "CO",
        "fips_code": "08117",
        "recorder_url": "https://www.summitcountyco.gov/157/Clerk-Recorder",
        "assessor_url": "https://www.summitcountyco.gov/174/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=5",
        "scraping_adapter": "summit",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Summit County (Breckenridge/Keystone/Dillon) - Resort area"
    },
    {
        "county_name": "Pitkin",
        "state": "CO",
        "fips_code": "08097",
        "recorder_url": "https://www.pitkincounty.com/170/Clerk-Recorder",
        "assessor_url": "https://www.pitkincounty.com/152/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=9",
        "scraping_adapter": "pitkin",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Pitkin County (Aspen/Snowmass) - Resort area"
    },
    {
        "county_name": "Routt",
        "state": "CO",
        "fips_code": "08107",
        "recorder_url": "https://www.co.routt.co.us/158/Clerk-Recorder",
        "assessor_url": "https://www.co.routt.co.us/137/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=14",
        "scraping_adapter": "routt",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Routt County (Steamboat Springs) - Resort area"
    },
    {
        "county_name": "Garfield",
        "state": "CO",
        "fips_code": "08045",
        "recorder_url": "https://www.garfield-county.com/clerk-recorder/",
        "assessor_url": "https://www.garfield-county.com/assessor/",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=9",
        "scraping_adapter": "garfield",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Garfield County (Glenwood Springs) - I-70 corridor"
    },
    {
        "county_name": "La Plata",
        "state": "CO",
        "fips_code": "08067",
        "recorder_url": "https://co.laplata.co.us/departments/clerk_recorder/index.php",
        "assessor_url": "https://co.laplata.co.us/departments/assessor/index.php",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=6",
        "scraping_adapter": "la_plata",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "La Plata County (Durango) - Southwest Colorado"
    },
    # Other Counties
    {
        "county_name": "Morgan",
        "state": "CO",
        "fips_code": "08087",
        "recorder_url": "https://www.morgan-county.net/clerk",
        "assessor_url": "https://www.morgan-county.net/assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=13",
        "scraping_adapter": "morgan",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Morgan County (Fort Morgan) - Eastern Plains"
    },
    {
        "county_name": "Fremont",
        "state": "CO",
        "fips_code": "08043",
        "recorder_url": "https://www.fremontco.com/clerk-recorder",
        "assessor_url": "https://www.fremontco.com/assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=11",
        "scraping_adapter": "fremont",
        "requests_per_minute": 6,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Fremont County (Canon City) - Arkansas River Valley"
    },
    {
        "county_name": "Clear Creek",
        "state": "CO",
        "fips_code": "08019",
        "recorder_url": "https://www.clearcreekcounty.us/179/Clerk-Recorder",
        "assessor_url": "https://www.clearcreekcounty.us/180/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=1",
        "scraping_adapter": "clear_creek",
        "requests_per_minute": 5,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Clear Creek County (Georgetown/Idaho Springs) - I-70 corridor"
    },
    {
        "county_name": "Elbert",
        "state": "CO",
        "fips_code": "08039",
        "recorder_url": "https://www.elbertcounty-co.gov/203/Clerk-Recorder",
        "assessor_url": "https://www.elbertcounty-co.gov/173/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=18",
        "scraping_adapter": "elbert",
        "requests_per_minute": 5,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Elbert County - Rural county east of Denver metro"
    },
    {
        "county_name": "Park",
        "state": "CO",
        "fips_code": "08093",
        "recorder_url": "https://www.parkco.us/173/Clerk-Recorder",
        "assessor_url": "https://www.parkco.us/174/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=11",
        "scraping_adapter": "park",
        "requests_per_minute": 5,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Park County (Fairplay/Bailey) - South Park area"
    },
    {
        "county_name": "Teller",
        "state": "CO",
        "fips_code": "08119",
        "recorder_url": "https://www.co.teller.co.us/Clerk/",
        "assessor_url": "https://www.co.teller.co.us/Assessor/",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=4",
        "scraping_adapter": "teller",
        "requests_per_minute": 5,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": True,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": True,
            "search_by": ["name", "reception_number"]
        },
        "notes": "Teller County (Cripple Creek/Woodland Park)"
    },
    # Counties with limited/no online access
    {
        "county_name": "Alamosa",
        "state": "CO",
        "fips_code": "08003",
        "recorder_url": "https://www.alamosacounty.org/clerk",
        "assessor_url": "https://www.alamosacounty.org/assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=12",
        "scraping_adapter": None,
        "requests_per_minute": 5,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": False,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": False,
            "notes": "In-person or mail request required"
        },
        "notes": "Alamosa County - San Luis Valley, limited online access"
    },
    {
        "county_name": "Archuleta",
        "state": "CO",
        "fips_code": "08007",
        "recorder_url": "https://www.archuletacounty.org/169/Clerk-Recorder",
        "assessor_url": "https://www.archuletacounty.org/152/Assessor",
        "court_records_url": "https://www.courts.state.co.us/Courts/County/Index.cfm?County_ID=6",
        "scraping_adapter": None,
        "requests_per_minute": 5,
        "delay_between_requests_ms": 3000,
        "requires_auth": False,
        "scraping_enabled": False,
        "is_healthy": True,
        "scraping_config": {
            "has_online_search": False,
            "notes": "Limited online access"
        },
        "notes": "Archuleta County (Pagosa Springs) - Limited online access"
    },
]


def seed_counties():
    """Seed the database with Colorado county configurations"""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./title_search.db")
    sync_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    try:
        print("Seeding Colorado counties...")

        for county_data in COLORADO_COUNTIES:
            # Check if county already exists
            existing = db.query(CountyConfig).filter(
                CountyConfig.county_name == county_data["county_name"],
                CountyConfig.state == county_data["state"]
            ).first()

            if existing:
                # Update existing record
                for key, value in county_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                print(f"  Updated: {county_data['county_name']} County")
            else:
                # Create new record
                county = CountyConfig(**county_data)
                db.add(county)
                print(f"  Created: {county_data['county_name']} County")

        db.commit()

        # Print summary
        total = db.query(CountyConfig).filter(CountyConfig.state == "CO").count()
        enabled = db.query(CountyConfig).filter(
            CountyConfig.state == "CO",
            CountyConfig.scraping_enabled == True
        ).count()

        print(f"\nSeeding complete!")
        print(f"  Total Colorado counties: {total}")
        print(f"  Scraping enabled: {enabled}")
        print(f"  Scraping disabled: {total - enabled}")

    except Exception as e:
        print(f"Error seeding counties: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def list_counties():
    """List all county configurations"""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./title_search.db")
    sync_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    try:
        counties = db.query(CountyConfig).filter(
            CountyConfig.state == "CO"
        ).order_by(CountyConfig.county_name).all()

        print("\nColorado County Configurations:")
        print("-" * 80)

        for county in counties:
            status = "ENABLED" if county.scraping_enabled else "DISABLED"
            health = "HEALTHY" if county.is_healthy else "UNHEALTHY"
            adapter = county.scraping_adapter or "N/A"

            print(f"{county.county_name:20} | {status:10} | {health:10} | Adapter: {adapter}")

        print("-" * 80)
        print(f"Total: {len(counties)} counties")

    finally:
        db.close()


def test_county_adapter(county_name: str):
    """Test a specific county adapter"""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./title_search.db")
    sync_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    try:
        county = db.query(CountyConfig).filter(
            CountyConfig.county_name.ilike(county_name)
        ).first()

        if not county:
            print(f"County '{county_name}' not found")
            return

        print(f"\nTesting adapter for {county.county_name} County:")
        print(f"  Recorder URL: {county.recorder_url}")
        print(f"  Adapter: {county.scraping_adapter}")
        print(f"  Rate limit: {county.requests_per_minute} req/min")

        # Import and test adapter
        from app.scraping.adapters import get_adapter_for_county

        config = {
            "county_name": county.county_name,
            "recorder_url": county.recorder_url,
            "requests_per_minute": county.requests_per_minute,
            "delay_between_requests_ms": county.delay_between_requests_ms,
        }

        adapter = get_adapter_for_county(county.county_name, config)
        if adapter:
            print(f"  Adapter class: {adapter.__class__.__name__}")
        else:
            print("  No adapter available")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="County seed data management")
    parser.add_argument("command", choices=["seed", "list", "test"],
                        help="Command to run: seed, list, or test")
    parser.add_argument("--county", type=str, help="County name for test command")

    args = parser.parse_args()

    if args.command == "seed":
        seed_counties()
    elif args.command == "list":
        list_counties()
    elif args.command == "test":
        if not args.county:
            print("Please specify a county with --county")
        else:
            test_county_adapter(args.county)
