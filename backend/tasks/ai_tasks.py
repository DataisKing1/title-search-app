"""AI analysis tasks"""
from tasks.celery_app import celery_app
from datetime import datetime
import logging
import os
import json

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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def analyze_document(self, document_id: int):
    """
    Analyze a document with OCR and AI.

    Steps:
    1. Extract text via OCR if needed
    2. Send to AI for analysis
    3. Store extracted data
    """
    from app.models.document import Document

    db = get_db_session()

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"success": False, "error": "Document not found"}

        logger.info(f"Analyzing document {document_id}: {document.instrument_number}")

        # Step 1: OCR if we have a file but no text
        if document.file_path and not document.ocr_text:
            ocr_result = _perform_ocr(document.file_path)
            if ocr_result:
                document.ocr_text = ocr_result.get("text", "")
                document.ocr_confidence = ocr_result.get("confidence", 0)
                db.commit()

        # Step 2: AI Analysis if we have text
        if document.ocr_text or document.ai_extracted_data:
            text_to_analyze = document.ocr_text or ""

            ai_result = _analyze_with_ai(
                text=text_to_analyze,
                document_type=document.document_type.value,
                instrument_number=document.instrument_number
            )

            if ai_result.get("success"):
                document.ai_extracted_data = ai_result.get("extracted_data", {})
                document.ai_summary = ai_result.get("summary", "")
                document.ai_analysis_at = datetime.utcnow()

                # Update document fields from AI extraction
                extracted = ai_result.get("extracted_data", {})
                if extracted.get("grantor") and not document.grantor:
                    document.grantor = extracted["grantor"]
                if extracted.get("grantee") and not document.grantee:
                    document.grantee = extracted["grantee"]
                if extracted.get("consideration") and not document.consideration:
                    document.consideration = extracted["consideration"]

                db.commit()

        logger.info(f"Document {document_id} analysis complete")

        return {
            "success": True,
            "document_id": document_id,
            "has_ocr": bool(document.ocr_text),
            "has_ai_analysis": bool(document.ai_extracted_data)
        }

    except Exception as e:
        logger.error(f"Document analysis failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"success": False, "error": str(e)}

    finally:
        db.close()


def _perform_ocr(file_path: str) -> dict:
    """Perform OCR on a document file"""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from PIL import Image

        logger.info(f"Performing OCR on {file_path}")

        # Check file type
        if file_path.lower().endswith('.pdf'):
            # Convert PDF to images
            try:
                images = convert_from_path(file_path, dpi=settings.OCR_DPI)
            except Exception as e:
                logger.warning(f"PDF conversion failed: {e}")
                return {"text": "", "confidence": 0}
        else:
            # Assume it's an image
            images = [Image.open(file_path)]

        all_text = []
        total_confidence = 0

        for i, image in enumerate(images):
            # Get OCR data
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT
            )

            # Extract text and confidence
            page_text = []
            page_confidence = []

            for j, text in enumerate(data["text"]):
                if text.strip():
                    page_text.append(text)
                    conf = data["conf"][j]
                    if conf > 0:
                        page_confidence.append(conf)

            all_text.append(" ".join(page_text))
            if page_confidence:
                total_confidence += sum(page_confidence) / len(page_confidence)

        combined_text = "\n\n".join(all_text)
        avg_confidence = int(total_confidence / len(images)) if images else 0

        logger.info(f"OCR complete: {len(combined_text)} chars, {avg_confidence}% confidence")

        return {
            "text": combined_text,
            "confidence": avg_confidence,
            "pages": len(images)
        }

    except ImportError as e:
        logger.warning(f"OCR dependencies not available: {e}")
        return {"text": "", "confidence": 0}
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return {"text": "", "confidence": 0}


def _analyze_with_ai(text: str, document_type: str, instrument_number: str) -> dict:
    """Analyze document text with AI"""

    # Get AI provider configuration
    provider = settings.DEFAULT_AI_PROVIDER
    model = settings.DEFAULT_AI_MODEL

    # Build prompt
    system_prompt = f"""You are an expert title examiner analyzing a {document_type} document.
Extract all relevant information for title insurance purposes.

Return your analysis as JSON with the following structure:
{{
    "document_type": "the type of document",
    "summary": "brief summary of the document",
    "grantor": ["list of grantor names"],
    "grantee": ["list of grantee names"],
    "consideration": "sale price or loan amount if applicable",
    "recording_date": "date if found",
    "legal_description": "property legal description if found",
    "encumbrances": ["list of any liens, easements, or restrictions"],
    "potential_issues": ["list of any title concerns or defects"],
    "key_terms": ["important terms or conditions"]
}}
"""

    try:
        if provider == "openai":
            return _analyze_with_openai(text, system_prompt, model)
        elif provider == "anthropic":
            return _analyze_with_anthropic(text, system_prompt, model)
        else:
            logger.warning(f"Unknown AI provider: {provider}")
            return {"success": False, "error": f"Unknown provider: {provider}"}

    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {"success": False, "error": str(e)}


def _analyze_with_openai(text: str, system_prompt: str, model: str) -> dict:
    """Analyze with OpenAI"""
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not configured")
            return {"success": False, "error": "OpenAI not configured"}

        client = OpenAI(api_key=api_key)

        # Truncate text to configured limit
        text_limit = settings.AI_TEXT_TRUNCATION_LIMIT
        truncated_text = text[:text_limit]

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this document:\n\n{truncated_text}"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        extracted_data = json.loads(content)

        return {
            "success": True,
            "extracted_data": extracted_data,
            "summary": extracted_data.get("summary", ""),
            "provider": "openai",
            "model": model
        }

    except ImportError:
        logger.warning("OpenAI package not installed")
        return {"success": False, "error": "OpenAI not installed"}
    except Exception as e:
        logger.error(f"OpenAI analysis failed: {e}")
        return {"success": False, "error": str(e)}


def _analyze_with_anthropic(text: str, system_prompt: str, model: str) -> dict:
    """Analyze with Anthropic Claude"""
    try:
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("Anthropic API key not configured")
            return {"success": False, "error": "Anthropic not configured"}

        client = Anthropic(api_key=api_key)

        # Truncate text to configured limit
        text_limit = settings.AI_TEXT_TRUNCATION_LIMIT
        truncated_text = text[:text_limit]

        response = client.messages.create(
            model=model or "claude-3-opus-20240229",
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Analyze this document and return JSON:\n\n{truncated_text}"}
            ]
        )

        content = response.content[0].text

        # Try to parse JSON from response
        try:
            # Find JSON in response
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                extracted_data = json.loads(json_match.group())
            else:
                extracted_data = {"summary": content}
        except json.JSONDecodeError:
            extracted_data = {"summary": content}

        return {
            "success": True,
            "extracted_data": extracted_data,
            "summary": extracted_data.get("summary", ""),
            "provider": "anthropic",
            "model": model
        }

    except ImportError:
        logger.warning("Anthropic package not installed")
        return {"success": False, "error": "Anthropic not installed"}
    except Exception as e:
        logger.error(f"Anthropic analysis failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task
def generate_risk_assessment(search_id: int):
    """Generate risk assessment for a search"""
    from app.models.search import TitleSearch
    from app.models.encumbrance import Encumbrance, EncumbranceStatus

    db = get_db_session()

    try:
        search = db.query(TitleSearch).filter(TitleSearch.id == search_id).first()
        if not search:
            return {"success": False, "error": "Search not found"}

        # Calculate risk score
        risk_score = 0
        risk_factors = []

        # Check encumbrances
        active_encumbrances = db.query(Encumbrance).filter(
            Encumbrance.search_id == search_id,
            Encumbrance.status == EncumbranceStatus.ACTIVE
        ).all()

        for enc in active_encumbrances:
            if enc.encumbrance_type.value in ["judgment_lien", "tax_lien", "irs_lien"]:
                risk_score += 20
                risk_factors.append(f"Active {enc.encumbrance_type.value}: {enc.description}")
            elif enc.encumbrance_type.value in ["mechanics_lien", "lis_pendens"]:
                risk_score += 15
                risk_factors.append(f"Active {enc.encumbrance_type.value}")
            elif enc.encumbrance_type.value in ["mortgage", "deed_of_trust"]:
                risk_score += 5
                risk_factors.append(f"Open loan: {enc.holder_name}")

        # Check chain of title
        chain_entries = len(search.chain_of_title) if search.chain_of_title else 0
        if chain_entries < 2:
            risk_score += 20
            risk_factors.append("Incomplete chain of title")

        # Check documents needing review
        docs_needing_review = [d for d in search.documents if d.needs_review]
        if docs_needing_review:
            risk_score += 10 * len(docs_needing_review)
            risk_factors.append(f"{len(docs_needing_review)} documents need manual review")

        # Cap at 100
        risk_score = min(risk_score, 100)

        # Determine risk level
        if risk_score < 20:
            risk_level = "low"
        elif risk_score < 50:
            risk_level = "medium"
        elif risk_score < 75:
            risk_level = "high"
        else:
            risk_level = "critical"

        return {
            "success": True,
            "search_id": search_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors
        }

    except Exception as e:
        logger.error(f"Risk assessment failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()
