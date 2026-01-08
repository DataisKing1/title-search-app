"""Report generation Celery tasks"""
from tasks.celery_app import celery_app
from datetime import datetime
import logging
import os
import json

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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_title_report(self, search_id: int):
    """
    Generate comprehensive title report for a search.

    Creates:
    - Schedule A: Property and vesting information
    - Schedule B-1: Requirements (liens to satisfy)
    - Schedule B-2: Exceptions (easements, restrictions)
    - Chain of title narrative
    - Risk assessment summary
    - PDF document
    """
    from app.models.search import TitleSearch, SearchStatus
    from app.models.report import TitleReport, ReportStatus
    from app.models.document import Document
    from app.models.encumbrance import Encumbrance, EncumbranceStatus
    from app.models.chain_of_title import ChainOfTitleEntry

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        if not search:
            return {"success": False, "error": "Search not found"}

        logger.info(f"Generating title report for search {search_id}")

        # Check if report already exists
        existing_report = db.query(TitleReport).filter(
            TitleReport.search_id == search_id
        ).first()

        if existing_report:
            report = existing_report
            report.status = ReportStatus.DRAFT
        else:
            # Generate report number
            import uuid
            report_number = f"TR-{datetime.utcnow().strftime('%Y')}-{uuid.uuid4().hex[:8].upper()}"
            report = TitleReport(
                search_id=search_id,
                report_number=report_number,
                status=ReportStatus.DRAFT
            )
            db.add(report)

        db.commit()

        # Build Schedule A - Property Information
        schedule_a = _build_schedule_a(db, search)

        # Build Schedule B-1 - Requirements
        schedule_b1 = _build_schedule_b1(db, search_id)

        # Build Schedule B-2 - Exceptions
        schedule_b2 = _build_schedule_b2(db, search_id)

        # Build chain of title narrative
        chain_narrative = _build_chain_narrative(db, search_id)

        # Calculate risk score
        risk_result = _calculate_risk_score(db, search_id)

        # Update report
        report.schedule_a = schedule_a
        report.schedule_b1 = schedule_b1
        report.schedule_b2 = schedule_b2
        report.chain_of_title_narrative = chain_narrative
        report.risk_score = risk_result["score"]
        report.risk_assessment_summary = risk_result["summary"]
        report.status = ReportStatus.REVIEW
        report.effective_date = datetime.utcnow()

        # Generate PDF
        pdf_path = _generate_pdf_report(report, search)
        if pdf_path:
            report.pdf_path = pdf_path

        db.commit()

        logger.info(f"Title report generated for search {search_id}")

        return {
            "success": True,
            "search_id": search_id,
            "report_id": report.id,
            "risk_score": report.risk_score,
            "pdf_path": pdf_path
        }

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"success": False, "error": str(e)}

    finally:
        db.close()


def _build_schedule_a(db, search) -> dict:
    """Build Schedule A - Property and vesting information"""
    property_data = search.property

    schedule_a = {
        "effective_date": datetime.utcnow().strftime("%B %d, %Y"),
        "property": {
            "street_address": property_data.street_address if property_data else "",
            "city": property_data.city if property_data else "",
            "county": property_data.county if property_data else search.county,
            "state": property_data.state if property_data else "Colorado",
            "zip_code": property_data.zip_code if property_data else "",
            "parcel_number": property_data.parcel_number if property_data else search.parcel_number,
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
    from app.models.chain_of_title import ChainOfTitleEntry
    latest_entry = db.query(ChainOfTitleEntry).filter(
        ChainOfTitleEntry.search_id == search.id
    ).order_by(ChainOfTitleEntry.sequence_number.desc()).first()

    if latest_entry:
        schedule_a["vesting"]["current_owner"] = ", ".join(latest_entry.grantee_names) if latest_entry.grantee_names else ""
        schedule_a["vesting"]["vesting_type"] = latest_entry.transaction_type or ""
        schedule_a["vesting"]["vesting_instrument"] = latest_entry.recording_reference or ""
        schedule_a["vesting"]["vesting_date"] = latest_entry.transaction_date.strftime("%B %d, %Y") if latest_entry.transaction_date else ""

    return schedule_a


def _build_schedule_b1(db, search_id: int) -> list:
    """Build Schedule B-1 - Requirements to be satisfied"""
    from app.models.encumbrance import Encumbrance, EncumbranceStatus, EncumbranceType

    requirements = []

    # Get active liens that need to be satisfied
    active_liens = db.query(Encumbrance).filter(
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
    ).all()

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
            "action_required": _get_required_action(lien.encumbrance_type)
        }
        requirements.append(requirement)

    return requirements


def _build_schedule_b2(db, search_id: int) -> list:
    """Build Schedule B-2 - Exceptions from coverage"""
    from app.models.encumbrance import Encumbrance, EncumbranceStatus, EncumbranceType

    exceptions = []

    # Get easements, restrictions, and other exceptions
    exception_types = [
        EncumbranceType.EASEMENT,
        EncumbranceType.RESTRICTION,
        EncumbranceType.COVENANT,
    ]

    encumbrances = db.query(Encumbrance).filter(
        Encumbrance.search_id == search_id,
        Encumbrance.encumbrance_type.in_(exception_types)
    ).all()

    for i, enc in enumerate(encumbrances, 1):
        exception = {
            "number": i,
            "type": enc.encumbrance_type.value.replace("_", " ").title(),
            "description": enc.description or "",
            "instrument_number": enc.recording_reference or "",
            "recording_date": enc.recorded_date.strftime("%m/%d/%Y") if enc.recorded_date else "",
            "book_page": "",
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
            "book_page": "",
            "affects": "Entire Property"
        },
        {
            "number": len(exceptions) + 2,
            "type": "Standard Exception",
            "description": "Easements or claims of easements not shown by the public records.",
            "instrument_number": "",
            "recording_date": "",
            "book_page": "",
            "affects": "Entire Property"
        },
        {
            "number": len(exceptions) + 3,
            "type": "Standard Exception",
            "description": "Any encroachment, encumbrance, violation, variation, or adverse circumstance that would be disclosed by an accurate survey.",
            "instrument_number": "",
            "recording_date": "",
            "book_page": "",
            "affects": "Entire Property"
        },
        {
            "number": len(exceptions) + 4,
            "type": "Standard Exception",
            "description": "Any lien for real estate taxes or assessments not yet due and payable.",
            "instrument_number": "",
            "recording_date": "",
            "book_page": "",
            "affects": "Entire Property"
        }
    ]

    exceptions.extend(standard_exceptions)

    return exceptions


def _build_chain_narrative(db, search_id: int) -> str:
    """Build chain of title narrative"""
    from app.models.chain_of_title import ChainOfTitleEntry

    entries = db.query(ChainOfTitleEntry).filter(
        ChainOfTitleEntry.search_id == search_id
    ).order_by(ChainOfTitleEntry.sequence_number).all()

    if not entries:
        return "No chain of title entries found for this property."

    narrative_parts = [
        "CHAIN OF TITLE",
        "=" * 50,
        ""
    ]

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

        if entry.consideration:
            narrative_parts.append(f"   Consideration: {entry.consideration}")

        if entry.description:
            narrative_parts.append(f"   Notes: {entry.description}")

        narrative_parts.append("")

    return "\n".join(narrative_parts)


def _calculate_risk_score(db, search_id: int) -> dict:
    """Calculate overall risk score for the title"""
    from app.models.encumbrance import Encumbrance, EncumbranceStatus, EncumbranceType
    from app.models.document import Document
    from app.models.chain_of_title import ChainOfTitleEntry

    score = 0
    risk_factors = []

    # Check for active liens
    active_liens = db.query(Encumbrance).filter(
        Encumbrance.search_id == search_id,
        Encumbrance.status == EncumbranceStatus.ACTIVE
    ).all()

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
    chain_entries = db.query(ChainOfTitleEntry).filter(
        ChainOfTitleEntry.search_id == search_id
    ).count()

    if chain_entries < 2:
        score += 30
        risk_factors.append("Incomplete chain of title - fewer than 2 transfers found")
    elif chain_entries < 5:
        score += 10
        risk_factors.append("Limited chain of title history")

    # Check for documents needing review
    docs_needing_review = db.query(Document).filter(
        Document.search_id == search_id,
        Document.needs_review == True
    ).count()

    if docs_needing_review > 0:
        score += 5 * docs_needing_review
        risk_factors.append(f"{docs_needing_review} document(s) require manual review")

    # Check for gaps in chain
    entries = db.query(ChainOfTitleEntry).filter(
        ChainOfTitleEntry.search_id == search_id
    ).order_by(ChainOfTitleEntry.sequence_number).all()

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


def _get_required_action(encumbrance_type) -> str:
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


def _generate_pdf_report(report, search) -> str:
    """Generate PDF version of the report"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

        storage_path = os.getenv("STORAGE_PATH", "./storage")
        reports_dir = os.path.join(storage_path, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        filename = f"title_report_{search.reference_number}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join(reports_dir, filename)

        doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='TitleHeader',
                                  parent=styles['Heading1'],
                                  fontSize=18,
                                  spaceAfter=30,
                                  alignment=1))
        styles.add(ParagraphStyle(name='SectionHeader',
                                  parent=styles['Heading2'],
                                  fontSize=14,
                                  spaceBefore=20,
                                  spaceAfter=10))

        story = []

        # Title
        story.append(Paragraph("TITLE COMMITMENT", styles['TitleHeader']))
        story.append(Spacer(1, 12))

        # Reference info
        ref_data = [
            ["Reference Number:", search.reference_number],
            ["Effective Date:", report.schedule_a.get("effective_date", "")],
            ["County:", report.schedule_a.get("property", {}).get("county", "")],
        ]
        ref_table = Table(ref_data, colWidths=[2*inch, 4*inch])
        ref_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(ref_table)
        story.append(Spacer(1, 20))

        # Schedule A
        story.append(Paragraph("SCHEDULE A - PROPERTY AND VESTING", styles['SectionHeader']))
        property_info = report.schedule_a.get("property", {})
        vesting_info = report.schedule_a.get("vesting", {})

        prop_data = [
            ["Property Address:", property_info.get("street_address", "")],
            ["City, State, Zip:", f"{property_info.get('city', '')}, {property_info.get('state', '')} {property_info.get('zip_code', '')}"],
            ["Parcel Number:", property_info.get("parcel_number", "")],
            ["Legal Description:", property_info.get("legal_description", "")],
            ["Current Owner:", vesting_info.get("current_owner", "")],
            ["Vesting Instrument:", vesting_info.get("vesting_instrument", "")],
            ["Vesting Date:", vesting_info.get("vesting_date", "")],
        ]
        prop_table = Table(prop_data, colWidths=[2*inch, 4*inch])
        prop_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(prop_table)
        story.append(Spacer(1, 20))

        # Schedule B-1
        story.append(Paragraph("SCHEDULE B-1 - REQUIREMENTS", styles['SectionHeader']))
        if report.schedule_b1:
            for req in report.schedule_b1:
                story.append(Paragraph(
                    f"<b>{req.get('number')}. {req.get('type')}</b><br/>"
                    f"Holder: {req.get('holder')}<br/>"
                    f"Amount: {req.get('amount')}<br/>"
                    f"Instrument: {req.get('instrument_number')}<br/>"
                    f"Action Required: {req.get('action_required')}",
                    styles['Normal']
                ))
                story.append(Spacer(1, 10))
        else:
            story.append(Paragraph("No requirements identified.", styles['Normal']))

        story.append(PageBreak())

        # Schedule B-2
        story.append(Paragraph("SCHEDULE B-2 - EXCEPTIONS", styles['SectionHeader']))
        if report.schedule_b2:
            for exc in report.schedule_b2:
                story.append(Paragraph(
                    f"<b>{exc.get('number')}.</b> {exc.get('description')}",
                    styles['Normal']
                ))
                if exc.get('instrument_number'):
                    story.append(Paragraph(
                        f"<i>Instrument: {exc.get('instrument_number')} - {exc.get('recording_date')}</i>",
                        styles['Normal']
                    ))
                story.append(Spacer(1, 8))

        story.append(PageBreak())

        # Chain of Title
        story.append(Paragraph("CHAIN OF TITLE", styles['SectionHeader']))
        if report.chain_of_title_narrative:
            for line in report.chain_of_title_narrative.split('\n'):
                if line.strip():
                    story.append(Paragraph(line, styles['Normal']))
            story.append(Spacer(1, 10))

        # Risk Assessment
        story.append(Paragraph("RISK ASSESSMENT", styles['SectionHeader']))
        risk_color = colors.green if report.risk_score < 30 else (colors.orange if report.risk_score < 60 else colors.red)
        story.append(Paragraph(f"<b>Risk Score: {report.risk_score}/100</b>", styles['Normal']))
        story.append(Spacer(1, 10))
        if report.risk_assessment_summary:
            story.append(Paragraph(report.risk_assessment_summary.replace('\n', '<br/>'), styles['Normal']))

        # Build PDF
        doc.build(story)

        logger.info(f"PDF generated: {pdf_path}")
        return pdf_path

    except ImportError:
        logger.warning("ReportLab not installed, skipping PDF generation")
        return None
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return None


@celery_app.task
def regenerate_report(report_id: int):
    """Regenerate an existing report"""
    from app.models.report import TitleReport

    db = get_db_session()

    try:
        report = db.query(TitleReport).filter(TitleReport.id == report_id).first()
        if not report:
            return {"success": False, "error": "Report not found"}

        return generate_title_report(report.search_id)

    except Exception as e:
        logger.error(f"Report regeneration failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


@celery_app.task
def export_report_json(report_id: int) -> dict:
    """Export report as JSON"""
    from app.models.report import TitleReport

    db = get_db_session()

    try:
        report = db.query(TitleReport).filter(TitleReport.id == report_id).first()
        if not report:
            return {"success": False, "error": "Report not found"}

        storage_path = os.getenv("STORAGE_PATH", "./storage")
        exports_dir = os.path.join(storage_path, "exports")
        os.makedirs(exports_dir, exist_ok=True)

        filename = f"report_{report_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        json_path = os.path.join(exports_dir, filename)

        export_data = {
            "report_id": report.id,
            "search_id": report.search_id,
            "report_number": report.report_number,
            "effective_date": report.effective_date.isoformat() if report.effective_date else None,
            "status": report.status.value if report.status else None,
            "schedule_a": report.schedule_a,
            "schedule_b1": report.schedule_b1,
            "schedule_b2": report.schedule_b2,
            "chain_of_title_narrative": report.chain_of_title_narrative,
            "risk_score": report.risk_score,
            "risk_assessment_summary": report.risk_assessment_summary,
        }

        with open(json_path, "w") as f:
            json.dump(export_data, f, indent=2)

        return {
            "success": True,
            "report_id": report_id,
            "export_path": json_path
        }

    except Exception as e:
        logger.error(f"JSON export failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()
