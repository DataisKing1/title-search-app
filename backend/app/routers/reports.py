"""Reports router"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models.report import TitleReport, ReportStatus
from app.models.search import TitleSearch
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportResponse(BaseModel):
    """Report response model"""
    id: int
    search_id: int
    report_number: str
    report_type: str
    status: ReportStatus
    effective_date: Optional[datetime]
    expiration_date: Optional[datetime]
    risk_score: Optional[int]
    risk_assessment_summary: Optional[str]
    pdf_generated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportDetailResponse(ReportResponse):
    """Detailed report response with schedules"""
    schedule_a: Optional[Dict[str, Any]]
    schedule_b1: Optional[List[Dict[str, Any]]]
    schedule_b2: Optional[List[Dict[str, Any]]]
    chain_of_title_narrative: Optional[str]
    ai_recommendations: Optional[List[Dict[str, Any]]]


@router.get("", response_model=List[ReportResponse])
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all reports"""
    result = await db.execute(
        select(TitleReport).order_by(TitleReport.created_at.desc())
    )
    reports = result.scalars().all()

    return [ReportResponse.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed report information"""
    result = await db.execute(
        select(TitleReport).where(TitleReport.id == report_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    return ReportDetailResponse.model_validate(report)


@router.get("/{report_id}/download")
async def download_report_pdf(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download report PDF"""
    result = await db.execute(
        select(TitleReport).where(TitleReport.id == report_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    if not report.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not yet generated"
        )

    return FileResponse(
        path=report.pdf_path,
        filename=f"title_report_{report.report_number}.pdf",
        media_type="application/pdf"
    )


@router.get("/{report_id}/export/json")
async def export_report_json(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export report as JSON"""
    result = await db.execute(
        select(TitleReport).where(TitleReport.id == report_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    # Return JSON directly
    return {
        "report_number": report.report_number,
        "effective_date": report.effective_date.isoformat() if report.effective_date else None,
        "schedule_a": report.schedule_a,
        "schedule_b1": report.schedule_b1,
        "schedule_b2": report.schedule_b2,
        "chain_of_title_narrative": report.chain_of_title_narrative,
        "risk_score": report.risk_score,
        "risk_assessment": report.risk_assessment_summary
    }


@router.post("/{report_id}/approve")
async def approve_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Approve a report for issuance"""
    result = await db.execute(
        select(TitleReport).where(TitleReport.id == report_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    if report.status == ReportStatus.ISSUED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report already issued"
        )

    report.status = ReportStatus.APPROVED
    report.approved_by = current_user.id
    report.approved_at = datetime.utcnow()
    await db.commit()

    return {"message": "Report approved successfully"}
