"""Tests for Document Classification Service

Tests the pattern-based document classifier including:
- Document type detection from text content
- Raw type code mapping
- Filename-based classification
- Confidence scoring
"""

import pytest
from app.services.document_classifier import (
    DocumentClassifier,
    classify_document,
    classify_from_raw_type,
)
from app.models.document import DocumentType


class TestDocumentClassifier:
    """Tests for the DocumentClassifier class"""

    @pytest.fixture
    def classifier(self):
        """Create a classifier instance"""
        return DocumentClassifier()


class TestDeedClassification:
    """Tests for deed document classification"""

    def test_warranty_deed(self):
        """Test classification of warranty deed"""
        text = """
        WARRANTY DEED

        This Warranty Deed made this 15th day of January, 2024, between
        JOHN SMITH AND JANE SMITH, husband and wife, as Grantor, and
        BOB JOHNSON, a single person, as Grantee.

        The Grantor, for and in consideration of TEN DOLLARS ($10.00) and other
        good and valuable consideration, does hereby grant, bargain, sell and convey
        unto the Grantee, his heirs and assigns forever, the following described
        real property situated in the County of Denver, State of Colorado.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.DEED
        assert confidence > 0.5

    def test_quitclaim_deed(self):
        """Test classification of quitclaim deed"""
        text = """
        QUITCLAIM DEED

        The Grantor, ABC LLC, hereby remises, releases and quit claims to
        XYZ Corporation, the Grantee, all right, title and interest in the
        following described real property.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.DEED
        assert confidence > 0.4

    def test_special_warranty_deed(self):
        """Test classification of special warranty deed"""
        text = """
        SPECIAL WARRANTY DEED

        This Special Warranty Deed is made by First National Bank, a national
        banking association, as Grantor, to Jane Doe, as Grantee.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.DEED


class TestMortgageClassification:
    """Tests for mortgage/deed of trust classification"""

    def test_mortgage(self):
        """Test classification of mortgage document"""
        text = """
        MORTGAGE

        THIS MORTGAGE is made this 1st day of January, 2024, between
        JOHN DOE, hereinafter called Mortgagor, and FIRST NATIONAL BANK,
        hereinafter called Mortgagee.

        The Mortgagor hereby mortgages to the Mortgagee the following property
        to secure the payment of the promissory note in the principal sum of
        TWO HUNDRED FIFTY THOUSAND DOLLARS ($250,000.00).
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.MORTGAGE
        assert confidence > 0.4

    def test_deed_of_trust(self):
        """Test classification of deed of trust"""
        text = """
        DEED OF TRUST

        THIS DEED OF TRUST is made this 15th day of March, 2024, by and between
        JOHN SMITH (Trustor), PUBLIC TRUSTEE OF DENVER COUNTY (Trustee), and
        WELLS FARGO BANK, N.A. (Beneficiary).

        Trustor hereby grants, bargains and sells to the Trustee in trust with
        power of sale the following described real property to secure payment
        of the indebtedness evidenced by a promissory note.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.DEED_OF_TRUST
        assert confidence > 0.5


class TestLienClassification:
    """Tests for lien document classification"""

    def test_mechanics_lien(self):
        """Test classification of mechanic's lien"""
        text = """
        STATEMENT OF MECHANIC'S LIEN

        Notice is hereby given that ABC Construction Company, the lien claimant,
        claims a mechanic's lien upon the real property described below for labor
        and materials furnished in the improvement of said property.

        Amount of Lien: $45,000.00
        Property Owner: John Smith
        Property Address: 123 Main Street, Denver, CO 80202
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.LIEN
        assert confidence > 0.5

    def test_tax_lien(self):
        """Test classification of federal tax lien"""
        text = """
        NOTICE OF FEDERAL TAX LIEN

        As provided by section 6321, 6322, and 6323 of the Internal Revenue Code,
        notice is given that taxes including interest and penalties have been
        assessed against the following-named taxpayer. Demand for payment of this
        liability has been made, but it remains unpaid.

        This is an IRS lien filing against JOHN DOE for unpaid taxes.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.LIEN


class TestReleaseClassification:
    """Tests for release/satisfaction classification"""

    def test_release_of_lien(self):
        """Test classification of release of lien"""
        text = """
        RELEASE OF MECHANIC'S LIEN

        ABC Construction Company hereby releases and discharges the mechanic's lien
        recorded on January 15, 2024, as Reception No. 2024012345, as the amount
        claimed has been paid in full and satisfied.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.RELEASE
        assert confidence > 0.4

    def test_satisfaction_of_mortgage(self):
        """Test classification of satisfaction of mortgage"""
        text = """
        SATISFACTION OF MORTGAGE

        First National Bank hereby certifies that the mortgage recorded in
        Book 1234, Page 567 has been fully paid and satisfied. The mortgagee
        hereby releases and discharges said mortgage.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type in [DocumentType.RELEASE, DocumentType.SATISFACTION]


class TestEasementClassification:
    """Tests for easement classification"""

    def test_utility_easement(self):
        """Test classification of utility easement"""
        text = """
        GRANT OF UTILITY EASEMENT

        This Grant of Easement is made by John Smith, owner of the servient estate,
        to Xcel Energy, for the purpose of installing, maintaining, and operating
        electric transmission lines across the following described property.

        The easement shall be perpetual and shall run with the land.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.EASEMENT
        assert confidence > 0.4

    def test_access_easement(self):
        """Test classification of access easement"""
        text = """
        ACCESS EASEMENT AGREEMENT

        This Access Easement grants to the owner of the dominant estate the right
        of ingress and egress across the servient tenement for purposes of
        accessing the public roadway.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.EASEMENT


class TestLisPendensClassification:
    """Tests for lis pendens classification"""

    def test_lis_pendens(self):
        """Test classification of lis pendens"""
        text = """
        NOTICE OF LIS PENDENS

        Notice is hereby given that an action has been commenced and is now pending
        in the District Court of Denver County, Colorado, Case No. 2024CV12345,
        in which John Doe is plaintiff and Jane Doe is defendant.

        This is a foreclosure action affecting the real property described herein.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.LIS_PENDENS
        assert confidence > 0.4


class TestAssignmentClassification:
    """Tests for assignment classification"""

    def test_assignment_of_mortgage(self):
        """Test classification of assignment of mortgage"""
        text = """
        CORPORATE ASSIGNMENT OF DEED OF TRUST

        First National Bank, as Assignor, hereby assigns, transfers and conveys
        to Second National Bank, as Assignee, all right, title and interest in
        the Deed of Trust recorded as Reception No. 2023123456.
        """
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.ASSIGNMENT


class TestRawTypeMapping:
    """Tests for raw document type code mapping"""

    def test_deed_codes(self):
        """Test mapping of deed type codes"""
        assert classify_from_raw_type("WD") == DocumentType.DEED
        assert classify_from_raw_type("QCD") == DocumentType.DEED
        assert classify_from_raw_type("SWD") == DocumentType.DEED
        assert classify_from_raw_type("DEED") == DocumentType.DEED

    def test_mortgage_codes(self):
        """Test mapping of mortgage type codes"""
        assert classify_from_raw_type("MORT") == DocumentType.MORTGAGE
        assert classify_from_raw_type("MTG") == DocumentType.MORTGAGE
        assert classify_from_raw_type("DOT") == DocumentType.DEED_OF_TRUST
        assert classify_from_raw_type("DTD") == DocumentType.DEED_OF_TRUST

    def test_lien_codes(self):
        """Test mapping of lien type codes"""
        assert classify_from_raw_type("LIEN") == DocumentType.LIEN
        assert classify_from_raw_type("ML") == DocumentType.LIEN
        assert classify_from_raw_type("FTL") == DocumentType.LIEN

    def test_release_codes(self):
        """Test mapping of release type codes"""
        assert classify_from_raw_type("REL") == DocumentType.RELEASE
        assert classify_from_raw_type("RELDOT") == DocumentType.RELEASE
        assert classify_from_raw_type("SAT") == DocumentType.SATISFACTION

    def test_unknown_code(self):
        """Test handling of unknown type codes"""
        assert classify_from_raw_type("UNKNOWN123") == DocumentType.OTHER
        assert classify_from_raw_type("") == DocumentType.OTHER


class TestFilenameClassification:
    """Tests for filename-based classification hints"""

    def test_deed_filename(self):
        """Test classification boost from deed filename"""
        text = "This document conveys property from grantor to grantee."
        doc_type, confidence, details = classify_document(
            text, filename="warranty_deed_12345.pdf"
        )
        # Should get a boost from filename
        assert "boosted_by" in details

    def test_mortgage_filename(self):
        """Test classification boost from mortgage filename"""
        text = "This document secures a loan on property."
        doc_type, confidence, details = classify_document(
            text, filename="mortgage_document.pdf"
        )
        assert "filename" in str(details.get("boosted_by", []))


class TestConfidenceScoring:
    """Tests for confidence score calculation"""

    def test_high_confidence(self):
        """Test that clear documents get high confidence"""
        text = """
        WARRANTY DEED
        WARRANTY DEED
        This WARRANTY DEED is made by the Grantor who does hereby grant,
        bargain, sell and convey to the Grantee the following property.
        """
        doc_type, confidence, details = classify_document(text)

        assert confidence > 0.5  # High confidence for multiple matches

    def test_low_confidence(self):
        """Test that ambiguous text gets lower confidence"""
        text = "This is a document about property."
        doc_type, confidence, details = classify_document(text)

        # Should either be OTHER or low confidence
        if doc_type != DocumentType.OTHER:
            assert confidence < 0.3

    def test_insufficient_text(self):
        """Test handling of insufficient text"""
        text = "Short text"
        doc_type, confidence, details = classify_document(text)

        assert doc_type == DocumentType.OTHER or confidence < 0.2


class TestEdgeCases:
    """Tests for edge cases"""

    def test_empty_text(self):
        """Test handling of empty text"""
        doc_type, confidence, details = classify_document("")

        assert doc_type == DocumentType.OTHER
        assert confidence == 0.0

    def test_none_values(self):
        """Test handling of None values"""
        doc_type, confidence, details = classify_document(
            "Sample document text",
            filename=None,
            raw_doc_type=None
        )

        # Should not raise exception
        assert doc_type is not None

    def test_mixed_content(self):
        """Test document with content from multiple types"""
        text = """
        This WARRANTY DEED also references a MORTGAGE and LIEN on the property.
        The DEED OF TRUST is hereby released and satisfied.
        """
        doc_type, confidence, details = classify_document(text)

        # Should classify as the dominant type
        assert doc_type in [
            DocumentType.DEED,
            DocumentType.MORTGAGE,
            DocumentType.DEED_OF_TRUST,
            DocumentType.RELEASE
        ]


class TestRawTypeBoost:
    """Tests for raw type code boosting"""

    def test_raw_type_boosts_confidence(self):
        """Test that raw type code boosts the correct classification"""
        text = "This document conveys property."

        # Without raw type
        type1, conf1, _ = classify_document(text)

        # With raw type
        type2, conf2, details = classify_document(text, raw_doc_type="WD")

        # Deed should be boosted
        if type2 == DocumentType.DEED:
            assert "boosted_by" in details
            assert any("raw_type" in str(b) for b in details.get("boosted_by", []))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
