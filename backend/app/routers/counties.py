"""Counties configuration router"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models.county import CountyConfig
from app.models.user import User
from app.routers.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/counties", tags=["Counties"])


class CountyResponse(BaseModel):
    """County configuration response"""
    id: int
    county_name: str
    state: str
    fips_code: Optional[str]
    recorder_url: Optional[str]
    scraping_enabled: bool
    scraping_adapter: Optional[str]
    is_healthy: bool
    last_successful_scrape: Optional[datetime]
    consecutive_failures: int

    class Config:
        from_attributes = True


class CountyDetailResponse(CountyResponse):
    """Detailed county response"""
    court_records_url: Optional[str]
    assessor_url: Optional[str]
    requests_per_minute: int
    delay_between_requests_ms: int
    requires_auth: bool
    fallback_api_enabled: bool
    fallback_api_provider: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class CountyUpdateRequest(BaseModel):
    """Request to update county configuration"""
    recorder_url: Optional[str] = None
    court_records_url: Optional[str] = None
    scraping_enabled: Optional[bool] = None
    scraping_adapter: Optional[str] = None
    scraping_config: Optional[Dict[str, Any]] = None
    requests_per_minute: Optional[int] = None
    delay_between_requests_ms: Optional[int] = None
    fallback_api_enabled: Optional[bool] = None
    fallback_api_provider: Optional[str] = None
    notes: Optional[str] = None


class CountyHealthResponse(BaseModel):
    """County health status"""
    county_name: str
    is_healthy: bool
    scraping_enabled: bool
    last_successful_scrape: Optional[datetime]
    last_failed_scrape: Optional[datetime]
    consecutive_failures: int
    fallback_available: bool


@router.get("", response_model=List[CountyResponse])
async def list_counties(
    state: str = "CO",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all county configurations"""
    result = await db.execute(
        select(CountyConfig)
        .where(CountyConfig.state == state)
        .order_by(CountyConfig.county_name)
    )
    counties = result.scalars().all()

    return [CountyResponse.model_validate(c) for c in counties]


@router.get("/{county_name}", response_model=CountyDetailResponse)
async def get_county(
    county_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed county configuration"""
    result = await db.execute(
        select(CountyConfig).where(CountyConfig.county_name.ilike(county_name))
    )
    county = result.scalar_one_or_none()

    if not county:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="County not found"
        )

    return CountyDetailResponse.model_validate(county)


@router.put("/{county_name}", response_model=CountyDetailResponse)
async def update_county(
    county_name: str,
    request: CountyUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update county configuration (admin only)"""
    result = await db.execute(
        select(CountyConfig).where(CountyConfig.county_name.ilike(county_name))
    )
    county = result.scalar_one_or_none()

    if not county:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="County not found"
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(county, field, value)

    await db.commit()
    await db.refresh(county)

    return CountyDetailResponse.model_validate(county)


@router.get("/{county_name}/health", response_model=CountyHealthResponse)
async def get_county_health(
    county_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get county health status"""
    result = await db.execute(
        select(CountyConfig).where(CountyConfig.county_name.ilike(county_name))
    )
    county = result.scalar_one_or_none()

    if not county:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="County not found"
        )

    return CountyHealthResponse(
        county_name=county.county_name,
        is_healthy=county.is_healthy,
        scraping_enabled=county.scraping_enabled,
        last_successful_scrape=county.last_successful_scrape,
        last_failed_scrape=county.last_failed_scrape,
        consecutive_failures=county.consecutive_failures,
        fallback_available=county.fallback_api_enabled and county.fallback_api_provider is not None
    )


@router.post("/{county_name}/test")
async def test_county_scraping(
    county_name: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Test county scraping adapter (admin only)"""
    result = await db.execute(
        select(CountyConfig).where(CountyConfig.county_name.ilike(county_name))
    )
    county = result.scalar_one_or_none()

    if not county:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="County not found"
        )

    if not county.scraping_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scraping is disabled for this county"
        )

    # TODO: Run actual test scrape
    return {
        "county": county.county_name,
        "adapter": county.scraping_adapter,
        "message": "Test scrape functionality not yet implemented"
    }
