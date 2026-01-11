"""Chain of Title Break Analysis Module"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.search import TitleSearch
from app.models.chain_of_title import ChainOfTitleEntry
from app.models.user import User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/searches", tags=["Chain Analysis"])


class ChainBreak(BaseModel):
    """Represents a break or gap in the chain of title"""
    break_type: str  # "missing_link", "unknown_grantor", "time_gap"
    severity: str  # "critical", "warning", "info"
    description: str
    from_entry: Optional[int] = None
    to_entry: Optional[int] = None
    from_party: Optional[str] = None
    to_party: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    recommendation: str


class OwnershipPeriod(BaseModel):
    """A period of ownership in the chain"""
    name: str
    acquired_date: Optional[str] = None
    sold_date: Optional[str] = None
    acquired_from: Optional[str] = None
    sold_to: Optional[str] = None


class ChainAnalysisResponse(BaseModel):
    """Complete chain of title analysis"""
    search_id: int
    is_clear: bool  # True if no critical breaks
    total_breaks: int
    critical_breaks: int
    warning_breaks: int
    breaks: List[ChainBreak]
    ownership_summary: List[OwnershipPeriod]
    analysis_notes: List[str]


def normalize_name(name: str) -> str:
    """Normalize a name for comparison (remove suffixes, standardize format)"""
    if not name:
        return ""
    name = name.upper().strip()
    # Remove common suffixes
    for suffix in [" TRST", " TRUST", " TRUSTEE", " NA", " N.A.", " LLC", " INC", " CORP", " CO"]:
        name = name.replace(suffix, "")
    # Remove extra whitespace
    return " ".join(name.split())


def names_match(name1: str, name2: str) -> bool:
    """Check if two names refer to the same entity"""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    # Check if one contains the other (for partial matches)
    if len(n1) > 3 and len(n2) > 3:
        if n1 in n2 or n2 in n1:
            return True
    # Check for common variations (US BANK vs U S BANK)
    if n1.replace(" ", "") == n2.replace(" ", ""):
        return True
    return False


@router.get("/{search_id}/chain-analysis", response_model=ChainAnalysisResponse)
async def analyze_chain_of_title(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze the chain of title for breaks, gaps, and issues.

    Returns detailed analysis including:
    - Critical breaks (missing links in ownership)
    - Unknown grantors (people conveying who never acquired)
    - Time gaps (unusually long periods between transfers)
    - Ownership summary timeline
    """
    # Verify search exists
    search_result = await db.execute(
        select(TitleSearch).where(TitleSearch.id == search_id)
    )
    if not search_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search not found"
        )

    # Get chain of title entries ordered by sequence
    result = await db.execute(
        select(ChainOfTitleEntry)
        .where(ChainOfTitleEntry.search_id == search_id)
        .order_by(ChainOfTitleEntry.sequence_number)
    )
    entries = result.scalars().all()

    breaks: List[ChainBreak] = []
    ownership_summary: List[OwnershipPeriod] = []
    analysis_notes: List[str] = []

    # Types of transactions that transfer ownership (not mortgages/liens)
    ownership_transfers = [
        "warranty deed", "trustee's deed", "grant deed",
        "quitclaim deed", "reo sale"
    ]

    # Exclude these - they are mortgages/liens, not ownership transfers
    excluded_types = [
        "deed of trust", "mortgage", "lien", "assignment", "release",
        "satisfaction", "subordination", "notice", "refinance"
    ]

    # Filter to only ownership transfers for chain analysis
    deed_entries = []
    for entry in entries:
        tx_type = (entry.transaction_type or "").lower()
        # Skip excluded types
        if any(excl in tx_type for excl in excluded_types):
            continue
        if any(t in tx_type for t in ownership_transfers):
            deed_entries.append(entry)

    if not deed_entries:
        return ChainAnalysisResponse(
            search_id=search_id,
            is_clear=True,
            total_breaks=0,
            critical_breaks=0,
            warning_breaks=0,
            breaks=[],
            ownership_summary=[],
            analysis_notes=["No ownership transfer documents found in chain."]
        )

    # Track current owner through the chain
    current_owner: Optional[str] = None
    owners_seen: List[OwnershipPeriod] = []

    for i, entry in enumerate(deed_entries):
        grantors = entry.grantor_names or []
        grantees = entry.grantee_names or []
        tx_type = entry.transaction_type or "Unknown"
        tx_date = entry.transaction_date

        # For first deed, establish initial owner
        if i == 0:
            if grantors:
                # Add the first grantor as the original owner
                owners_seen.append(OwnershipPeriod(
                    name=grantors[0],
                    acquired_date=None,
                    sold_date=tx_date.isoformat() if tx_date else None,
                    acquired_from="Unknown (prior to search period)",
                    sold_to=grantees[0] if grantees else "Unknown"
                ))
            if grantees:
                current_owner = grantees[0]
                owners_seen.append(OwnershipPeriod(
                    name=grantees[0],
                    acquired_date=tx_date.isoformat() if tx_date else None,
                    sold_date=None,
                    acquired_from=grantors[0] if grantors else "Unknown",
                    sold_to=None
                ))
        else:
            # Check if the grantor matches the previous grantee (current owner)
            grantor_matches = False
            if grantors and current_owner:
                for grantor in grantors:
                    if names_match(grantor, current_owner):
                        grantor_matches = True
                        break

            # Check special cases (PUBLIC TRUSTEE, bank foreclosure)
            is_foreclosure = "trustee" in tx_type.lower() or "foreclosure" in tx_type.lower()
            is_bank_sale = any("bank" in (g or "").lower() for g in grantors)

            if not grantor_matches and not is_foreclosure and not is_bank_sale:
                # This is a potential break in the chain!
                prev_entry = deed_entries[i - 1]

                breaks.append(ChainBreak(
                    break_type="missing_link",
                    severity="critical",
                    description=f"Chain break: '{grantors[0] if grantors else 'Unknown'}' is conveying property, but the last recorded owner was '{current_owner}'",
                    from_entry=prev_entry.sequence_number,
                    to_entry=entry.sequence_number,
                    from_party=current_owner,
                    to_party=grantors[0] if grantors else None,
                    from_date=prev_entry.transaction_date,
                    to_date=tx_date,
                    recommendation=f"Search for a deed transferring from '{current_owner}' to '{grantors[0] if grantors else 'the grantor'}'. A missing document is likely."
                ))

            # Update ownership tracking
            if grantees:
                # Update previous owner's sold info
                for owner in owners_seen:
                    if names_match(owner.name, current_owner or "") and owner.sold_date is None:
                        owner.sold_date = tx_date.isoformat() if tx_date else None
                        owner.sold_to = grantees[0]
                        break

                # Add new owner
                current_owner = grantees[0]
                owners_seen.append(OwnershipPeriod(
                    name=grantees[0],
                    acquired_date=tx_date.isoformat() if tx_date else None,
                    sold_date=None,
                    acquired_from=grantors[0] if grantors else "Unknown",
                    sold_to=None
                ))

    # Check for time gaps between deeds (more than 5 years)
    for i in range(1, len(deed_entries)):
        prev_entry = deed_entries[i - 1]
        curr_entry = deed_entries[i]

        if prev_entry.transaction_date and curr_entry.transaction_date:
            days_gap = (curr_entry.transaction_date - prev_entry.transaction_date).days
            if days_gap > 365 * 5:  # More than 5 years
                years_gap = days_gap / 365
                breaks.append(ChainBreak(
                    break_type="time_gap",
                    severity="warning",
                    description=f"Large time gap of {years_gap:.1f} years between recorded ownership transfers",
                    from_entry=prev_entry.sequence_number,
                    to_entry=curr_entry.sequence_number,
                    from_date=prev_entry.transaction_date,
                    to_date=curr_entry.transaction_date,
                    recommendation="Review for any unrecorded transfers, probate proceedings, or other conveyances during this period."
                ))

    # Check for grantors who never appeared as grantees
    all_grantees = set()
    for entry in deed_entries:
        for grantee in (entry.grantee_names or []):
            all_grantees.add(normalize_name(grantee))

    for i, entry in enumerate(deed_entries):
        if i == 0:
            continue  # Skip first entry
        for grantor in (entry.grantor_names or []):
            norm_grantor = normalize_name(grantor)
            # Skip special entities
            if any(x in norm_grantor for x in ["TRUSTEE", "PUBLIC", "BANK"]):
                continue
            found = any(names_match(norm_grantor, grantee) for grantee in all_grantees)
            if not found:
                breaks.append(ChainBreak(
                    break_type="unknown_grantor",
                    severity="critical",
                    description=f"'{grantor}' is conveying property but never appears as a grantee in the recorded chain",
                    from_entry=entry.sequence_number,
                    to_entry=entry.sequence_number,
                    from_party=grantor,
                    from_date=entry.transaction_date,
                    recommendation=f"Search for the deed by which '{grantor}' acquired the property. This is a critical chain break."
                ))

    # Generate analysis notes
    if not breaks:
        analysis_notes.append("✓ Chain of title appears complete with no breaks detected.")
    else:
        critical_count = sum(1 for b in breaks if b.severity == "critical")
        warning_count = sum(1 for b in breaks if b.severity == "warning")
        if critical_count > 0:
            analysis_notes.append(f"⚠️ ATTENTION: {critical_count} critical chain break(s) detected that require immediate attention.")
        if warning_count > 0:
            analysis_notes.append(f"ℹ️ {warning_count} warning(s) found that should be reviewed.")
        analysis_notes.append("Review all breaks and obtain missing documents before closing.")

    if deed_entries:
        start_date = deed_entries[0].transaction_date.strftime('%m/%d/%Y') if deed_entries[0].transaction_date else 'Unknown'
        end_date = deed_entries[-1].transaction_date.strftime('%m/%d/%Y') if deed_entries[-1].transaction_date else 'Unknown'
        analysis_notes.append(f"Chain analyzed from {start_date} to {end_date}.")
        analysis_notes.append(f"Total ownership transfers analyzed: {len(deed_entries)}")

    critical_breaks = sum(1 for b in breaks if b.severity == "critical")
    warning_breaks = sum(1 for b in breaks if b.severity == "warning")

    return ChainAnalysisResponse(
        search_id=search_id,
        is_clear=critical_breaks == 0,
        total_breaks=len(breaks),
        critical_breaks=critical_breaks,
        warning_breaks=warning_breaks,
        breaks=breaks,
        ownership_summary=owners_seen,
        analysis_notes=analysis_notes
    )
