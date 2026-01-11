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


class GenerateReportRequest(BaseModel):
    """Request to generate a report"""
    search_id: int


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    request: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a title report for a completed search.

    This is a synchronous endpoint for development/testing.
    In production, use Celery task for async generation.
    """
    from app.models.document import Document
    from app.models.encumbrance import Encumbrance, EncumbranceStatus, EncumbranceType
    from app.models.chain_of_title import ChainOfTitleEntry
    import uuid

    # Verify search exists and is completed
    search_result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == request.search_id)
    )
    search = search_result.scalar_one_or_none()

    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Check if report already exists
    existing_result = await db.execute(
        select(TitleReport).where(TitleReport.search_id == request.search_id)
    )
    existing_report = existing_result.scalar_one_or_none()

    if existing_report:
        # Return existing report
        return ReportResponse.model_validate(existing_report)

    # Generate report number
    report_number = f"TR-{datetime.utcnow().strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"

    # Build Schedule A
    schedule_a = await _build_schedule_a_async(db, search)

    # Build Schedule B-1 (requirements/liens)
    schedule_b1 = await _build_schedule_b1_async(db, request.search_id)

    # Build Schedule B-2 (exceptions)
    schedule_b2 = await _build_schedule_b2_async(db, request.search_id)

    # Build chain narrative
    chain_narrative = await _build_chain_narrative_async(db, request.search_id)

    # Calculate risk score
    risk_result = await _calculate_risk_score_async(db, request.search_id)

    # Create report
    report = TitleReport(
        search_id=request.search_id,
        report_number=report_number,
        status=ReportStatus.REVIEW,
        schedule_a=schedule_a,
        schedule_b1=schedule_b1,
        schedule_b2=schedule_b2,
        chain_of_title_narrative=chain_narrative,
        risk_score=risk_result["score"],
        risk_assessment_summary=risk_result["summary"],
        effective_date=datetime.utcnow()
    )

    db.add(report)
    await db.commit()
    await db.refresh(report)

    return ReportResponse.model_validate(report)


async def _build_schedule_a_async(db: AsyncSession, search) -> dict:
    """Build Schedule A - Property and vesting information"""
    from app.models.chain_of_title import ChainOfTitleEntry

    property_data = search.property

    schedule_a = {
        "effective_date": datetime.utcnow().strftime("%B %d, %Y"),
        "property": {
            "street_address": property_data.street_address if property_data else "",
            "city": property_data.city if property_data else "",
            "county": property_data.county if property_data else "",
            "state": property_data.state if property_data else "Colorado",
            "zip_code": property_data.zip_code if property_data else "",
            "parcel_number": property_data.parcel_number if property_data else "",
            "legal_description": property_data.legal_description if property_data else ""
        },
        "vesting": {
            "current_owner": "",
            "vesting_type": "",
            "vesting_instrument": "",
            "vesting_date": ""
        }
    }

    # Get current vesting from chain of title
    result = await db.execute(
        select(ChainOfTitleEntry)
        .where(ChainOfTitleEntry.search_id == search.id)
        .order_by(ChainOfTitleEntry.sequence_number.desc())
        .limit(1)
    )
    latest_entry = result.scalar_one_or_none()

    if latest_entry:
        schedule_a["vesting"]["current_owner"] = ", ".join(latest_entry.grantee_names) if latest_entry.grantee_names else ""
        schedule_a["vesting"]["vesting_type"] = latest_entry.transaction_type or ""
        schedule_a["vesting"]["vesting_instrument"] = latest_entry.recording_reference or ""
        schedule_a["vesting"]["vesting_date"] = latest_entry.transaction_date.strftime("%B %d, %Y") if latest_entry.transaction_date else ""

    return schedule_a


async def _build_schedule_b1_async(db: AsyncSession, search_id: int) -> list:
    """Build Schedule B-1 - Requirements to be satisfied"""
    from app.models.encumbrance import Encumbrance, EncumbranceStatus, EncumbranceType

    requirements = []

    # Get active liens that need to be satisfied
    result = await db.execute(
        select(Encumbrance).where(
            Encumbrance.search_id == search_id,
            Encumbrance.status == EncumbranceStatus.ACTIVE,
            Encumbrance.encumbrance_type.in_([
                EncumbranceType.MORTGAGE,
                EncumbranceType.DEED_OF_TRUST,
                EncumbranceType.JUDGMENT_LIEN,
                EncumbranceType.TAX_LIEN,
                EncumbranceType.IRS_LIEN,
                EncumbranceType.MECHANICS_LIEN,
                EncumbranceType.HOA_LIEN
            ])
        )
    )
    active_liens = result.scalars().all()

    for i, lien in enumerate(active_liens, 1):
        amount = lien.current_amount or lien.original_amount
        requirement = {
            "number": i,
            "type": lien.encumbrance_type.value.replace("_", " ").title(),
            "holder": lien.holder_name or "Unknown",
            "amount": f"${amount:,.2f}" if amount else "Amount Unknown",
            "instrument_number": lien.recording_reference or "",
            "recording_date": lien.recorded_date.strftime("%m/%d/%Y") if lien.recorded_date else "",
            "description": lien.description or "",
            "action_required": _get_required_action_sync(lien.encumbrance_type)
        }
        requirements.append(requirement)

    return requirements


async def _build_schedule_b2_async(db: AsyncSession, search_id: int) -> list:
    """Build Schedule B-2 - Exceptions from coverage"""
    from app.models.encumbrance import Encumbrance, EncumbranceType

    exceptions = []

    # Get easements, restrictions, and other exceptions
    result = await db.execute(
        select(Encumbrance).where(
            Encumbrance.search_id == search_id,
            Encumbrance.encumbrance_type.in_([
                EncumbranceType.EASEMENT,
                EncumbranceType.RESTRICTION,
                EncumbranceType.COVENANT,
            ])
        )
    )
    encumbrances = result.scalars().all()

    for i, enc in enumerate(encumbrances, 1):
        exception = {
            "number": i,
            "type": enc.encumbrance_type.value.replace("_", " ").title(),
            "description": enc.description or "",
            "instrument_number": enc.recording_reference or "",
            "recording_date": enc.recorded_date.strftime("%m/%d/%Y") if enc.recorded_date else "",
            "affects": "Entire Property"
        }
        exceptions.append(exception)

    # Add standard exceptions
    standard_exceptions = [
        {
            "number": len(exceptions) + 1,
            "type": "Standard Exception",
            "description": "Rights or claims of parties in possession not shown by the public records.",
            "instrument_number": "",
            "recording_date": "",
            "affects": "Entire Property"
        },
        {
            "number": len(exceptions) + 2,
            "type": "Standard Exception",
            "description": "Easements or claims of easements not shown by the public records.",
            "instrument_number": "",
            "recording_date": "",
            "affects": "Entire Property"
        },
        {
            "number": len(exceptions) + 3,
            "type": "Standard Exception",
            "description": "Any encroachment, encumbrance, violation, variation, or adverse circumstance that would be disclosed by an accurate survey.",
            "instrument_number": "",
            "recording_date": "",
            "affects": "Entire Property"
        },
        {
            "number": len(exceptions) + 4,
            "type": "Standard Exception",
            "description": "Any lien for real estate taxes or assessments not yet due and payable.",
            "instrument_number": "",
            "recording_date": "",
            "affects": "Entire Property"
        }
    ]

    exceptions.extend(standard_exceptions)
    return exceptions


async def _build_chain_narrative_async(db: AsyncSession, search_id: int) -> str:
    """Build chain of title narrative"""
    from app.models.chain_of_title import ChainOfTitleEntry

    result = await db.execute(
        select(ChainOfTitleEntry)
        .where(ChainOfTitleEntry.search_id == search_id)
        .order_by(ChainOfTitleEntry.sequence_number)
    )
    entries = result.scalars().all()

    if not entries:
        return "No chain of title entries found for this property."

    narrative_parts = []

    for entry in entries:
        grantor = ", ".join(entry.grantor_names) if entry.grantor_names else "Unknown Grantor"
        grantee = ", ".join(entry.grantee_names) if entry.grantee_names else "Unknown Grantee"
        date_str = entry.transaction_date.strftime("%B %d, %Y") if entry.transaction_date else "Unknown Date"
        trans_type = entry.transaction_type.replace("_", " ").title() if entry.transaction_type else "Unknown Transaction"

        narrative_parts.append(f"{entry.sequence_number}. {trans_type}")
        narrative_parts.append(f"   From: {grantor}")
        narrative_parts.append(f"   To: {grantee}")
        narrative_parts.append(f"   Date: {date_str}")
        narrative_parts.append(f"   Instrument: {entry.recording_reference or 'N/A'}")

        if entry.description:
            narrative_parts.append(f"   Notes: {entry.description}")

        narrative_parts.append("")

    return "\n".join(narrative_parts)


async def _calculate_risk_score_async(db: AsyncSession, search_id: int) -> dict:
    """Calculate overall risk score for the title"""
    from app.models.encumbrance import Encumbrance, EncumbranceStatus, EncumbranceType
    from app.models.document import Document
    from app.models.chain_of_title import ChainOfTitleEntry

    score = 0
    risk_factors = []

    # Check for active liens
    result = await db.execute(
        select(Encumbrance).where(
            Encumbrance.search_id == search_id,
            Encumbrance.status == EncumbranceStatus.ACTIVE
        )
    )
    active_liens = result.scalars().all()

    for lien in active_liens:
        if lien.encumbrance_type in [EncumbranceType.JUDGMENT_LIEN, EncumbranceType.TAX_LIEN, EncumbranceType.IRS_LIEN]:
            score += 25
            risk_factors.append(f"High-risk lien: {lien.encumbrance_type.value}")
        elif lien.encumbrance_type in [EncumbranceType.MECHANICS_LIEN, EncumbranceType.LIS_PENDENS]:
            score += 20
            risk_factors.append(f"Active {lien.encumbrance_type.value}")
        elif lien.encumbrance_type in [EncumbranceType.MORTGAGE, EncumbranceType.DEED_OF_TRUST]:
            score += 5
            risk_factors.append(f"Open loan: {lien.holder_name or 'Unknown lender'}")

    # Check chain of title completeness
    chain_count_result = await db.execute(
        select(ChainOfTitleEntry).where(ChainOfTitleEntry.search_id == search_id)
    )
    chain_entries = len(chain_count_result.scalars().all())

    if chain_entries < 2:
        score += 30
        risk_factors.append("Incomplete chain of title - fewer than 2 transfers found")
    elif chain_entries < 5:
        score += 10
        risk_factors.append("Limited chain of title history")

    # Check for chain gaps
    entries_result = await db.execute(
        select(ChainOfTitleEntry)
        .where(ChainOfTitleEntry.search_id == search_id)
        .order_by(ChainOfTitleEntry.sequence_number)
    )
    entries = entries_result.scalars().all()

    for i in range(1, len(entries)):
        prev_grantee = set(entries[i-1].grantee_names or [])
        curr_grantor = set(entries[i].grantor_names or [])
        if prev_grantee and curr_grantor and not prev_grantee.intersection(curr_grantor):
            score += 15
            risk_factors.append(f"Potential gap in chain between entries {i} and {i+1}")

    # Cap score at 100
    score = min(score, 100)

    # Determine risk level
    if score < 20:
        risk_level = "LOW"
        summary = "Title appears clear with minimal issues."
    elif score < 40:
        risk_level = "MODERATE"
        summary = "Some issues identified that may require attention before closing."
    elif score < 60:
        risk_level = "ELEVATED"
        summary = "Multiple issues identified. Recommend thorough review before proceeding."
    elif score < 80:
        risk_level = "HIGH"
        summary = "Significant title issues present. May affect insurability."
    else:
        risk_level = "CRITICAL"
        summary = "Critical title defects identified. Title may be uninsurable."

    return {
        "score": score,
        "level": risk_level,
        "factors": risk_factors,
        "summary": f"{risk_level} RISK ({score}/100): {summary}\n\nRisk Factors:\n" + "\n".join(f"- {f}" for f in risk_factors) if risk_factors else f"{risk_level} RISK ({score}/100): {summary}"
    }


def _get_required_action_sync(encumbrance_type) -> str:
    """Get required action for encumbrance type"""
    from app.models.encumbrance import EncumbranceType

    actions = {
        EncumbranceType.MORTGAGE: "Obtain payoff statement and record satisfaction",
        EncumbranceType.DEED_OF_TRUST: "Obtain payoff statement and record reconveyance",
        EncumbranceType.JUDGMENT_LIEN: "Pay judgment and obtain release",
        EncumbranceType.TAX_LIEN: "Pay delinquent taxes and obtain release",
        EncumbranceType.IRS_LIEN: "Contact IRS for payoff and release",
        EncumbranceType.MECHANICS_LIEN: "Obtain release or bond over lien",
        EncumbranceType.HOA_LIEN: "Pay HOA dues and obtain release",
    }

    return actions.get(encumbrance_type, "Resolve and obtain release")


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
