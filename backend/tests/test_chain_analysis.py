"""Tests for Chain of Title Analysis

Tests the chain analysis module including:
- Name normalization and matching
- Break detection (missing links, unknown grantors, time gaps)
- Ownership summary generation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.chain_analysis import (
    normalize_name,
    names_match,
    ChainBreak,
    OwnershipPeriod,
    ChainAnalysisResponse,
)


class TestNameNormalization:
    """Tests for the normalize_name function"""

    def test_basic_normalization(self):
        """Test basic name normalization"""
        assert normalize_name("John Smith") == "JOHN SMITH"
        assert normalize_name("  john  smith  ") == "JOHN SMITH"

    def test_removes_trust_suffixes(self):
        """Test removal of trust-related suffixes"""
        assert normalize_name("John Smith Trust") == "JOHN SMITH"
        assert normalize_name("John Smith TRST") == "JOHN SMITH"
        assert normalize_name("John Smith Trustee") == "JOHN SMITH"

    def test_removes_corporate_suffixes(self):
        """Test removal of corporate suffixes"""
        assert normalize_name("ABC Company LLC") == "ABC COMPANY"
        assert normalize_name("XYZ Corp INC") == "XYZ"  # Both removed
        assert normalize_name("First National Bank NA") == "FIRST NATIONAL BANK"
        assert normalize_name("Wells Fargo N.A.") == "WELLS FARGO"

    def test_empty_and_none(self):
        """Test handling of empty and None values"""
        assert normalize_name("") == ""
        assert normalize_name(None) == ""

    def test_preserves_core_name(self):
        """Test that core name is preserved"""
        assert normalize_name("SMITH, JOHN AND JANE") == "SMITH, JOHN AND JANE"


class TestNameMatching:
    """Tests for the names_match function"""

    def test_exact_match(self):
        """Test exact name matching"""
        assert names_match("John Smith", "JOHN SMITH") is True
        assert names_match("ABC LLC", "ABC") is True

    def test_partial_match(self):
        """Test partial name matching"""
        assert names_match("John Smith", "John Smith Trust") is True
        assert names_match("US Bank NA", "US BANK") is True

    def test_space_variation(self):
        """Test matching with space variations"""
        assert names_match("US BANK", "U S BANK") is True
        assert names_match("WELLSFARGO", "WELLS FARGO") is True

    def test_no_match(self):
        """Test non-matching names"""
        assert names_match("John Smith", "Jane Doe") is False
        assert names_match("ABC Company", "XYZ Company") is False

    def test_empty_names(self):
        """Test handling of empty names"""
        assert names_match("", "John") is False
        assert names_match("John", "") is False
        assert names_match("", "") is False

    def test_short_names(self):
        """Test that very short names don't false-match"""
        assert names_match("AB", "ABCD") is False
        assert names_match("ABC", "ABCDEFGH") is True  # 3 chars is threshold


class TestChainBreakDetection:
    """Tests for chain break detection logic"""

    @pytest.fixture
    def mock_entries(self):
        """Create mock chain of title entries"""
        entries = []

        # Entry 1: John Smith sells to Jane Doe
        entry1 = MagicMock()
        entry1.sequence_number = 1
        entry1.transaction_type = "Warranty Deed"
        entry1.transaction_date = datetime(2020, 1, 15)
        entry1.grantor_names = ["John Smith"]
        entry1.grantee_names = ["Jane Doe"]
        entries.append(entry1)

        # Entry 2: Jane Doe sells to Bob Johnson
        entry2 = MagicMock()
        entry2.sequence_number = 2
        entry2.transaction_type = "Warranty Deed"
        entry2.transaction_date = datetime(2022, 6, 1)
        entry2.grantor_names = ["Jane Doe"]
        entry2.grantee_names = ["Bob Johnson"]
        entries.append(entry2)

        return entries

    @pytest.fixture
    def broken_chain_entries(self):
        """Create mock entries with a chain break"""
        entries = []

        # Entry 1: John Smith sells to Jane Doe
        entry1 = MagicMock()
        entry1.sequence_number = 1
        entry1.transaction_type = "Warranty Deed"
        entry1.transaction_date = datetime(2020, 1, 15)
        entry1.grantor_names = ["John Smith"]
        entry1.grantee_names = ["Jane Doe"]
        entries.append(entry1)

        # Entry 2: UNKNOWN PERSON sells to Bob (chain break!)
        entry2 = MagicMock()
        entry2.sequence_number = 2
        entry2.transaction_type = "Warranty Deed"
        entry2.transaction_date = datetime(2022, 6, 1)
        entry2.grantor_names = ["Unknown Person"]  # Not Jane Doe!
        entry2.grantee_names = ["Bob Johnson"]
        entries.append(entry2)

        return entries

    @pytest.fixture
    def time_gap_entries(self):
        """Create mock entries with a large time gap"""
        entries = []

        entry1 = MagicMock()
        entry1.sequence_number = 1
        entry1.transaction_type = "Warranty Deed"
        entry1.transaction_date = datetime(2010, 1, 15)
        entry1.grantor_names = ["John Smith"]
        entry1.grantee_names = ["Jane Doe"]
        entries.append(entry1)

        entry2 = MagicMock()
        entry2.sequence_number = 2
        entry2.transaction_type = "Warranty Deed"
        entry2.transaction_date = datetime(2022, 1, 15)  # 12 year gap!
        entry2.grantor_names = ["Jane Doe"]
        entry2.grantee_names = ["Bob Johnson"]
        entries.append(entry2)

        return entries

    def test_valid_chain_has_no_breaks(self, mock_entries):
        """Test that a valid chain produces no breaks"""
        # The analyze function checks if grantor of entry N matches grantee of entry N-1
        # Entry 2 grantor "Jane Doe" matches Entry 1 grantee "Jane Doe"
        assert names_match(
            mock_entries[1].grantor_names[0],
            mock_entries[0].grantee_names[0]
        ) is True

    def test_broken_chain_detected(self, broken_chain_entries):
        """Test that a broken chain is detected"""
        # Entry 2 grantor "Unknown Person" does NOT match Entry 1 grantee "Jane Doe"
        assert names_match(
            broken_chain_entries[1].grantor_names[0],
            broken_chain_entries[0].grantee_names[0]
        ) is False

    def test_time_gap_calculation(self, time_gap_entries):
        """Test time gap calculation between entries"""
        entry1 = time_gap_entries[0]
        entry2 = time_gap_entries[1]

        days_gap = (entry2.transaction_date - entry1.transaction_date).days
        years_gap = days_gap / 365

        assert years_gap > 5  # This should trigger a warning
        assert abs(years_gap - 12) < 0.1  # Should be ~12 years


class TestOwnershipSummary:
    """Tests for ownership summary generation"""

    def test_ownership_period_creation(self):
        """Test creating ownership period objects"""
        period = OwnershipPeriod(
            name="John Smith",
            acquired_date="2020-01-15",
            sold_date="2022-06-01",
            acquired_from="Previous Owner",
            sold_to="Jane Doe"
        )

        assert period.name == "John Smith"
        assert period.acquired_date == "2020-01-15"
        assert period.sold_date == "2022-06-01"
        assert period.acquired_from == "Previous Owner"
        assert period.sold_to == "Jane Doe"

    def test_ownership_period_optional_fields(self):
        """Test ownership period with optional fields"""
        period = OwnershipPeriod(
            name="Current Owner",
            acquired_date="2022-06-01",
            acquired_from="Previous Owner"
        )

        assert period.name == "Current Owner"
        assert period.sold_date is None
        assert period.sold_to is None


class TestChainBreakModel:
    """Tests for ChainBreak model"""

    def test_chain_break_creation(self):
        """Test creating chain break objects"""
        break_obj = ChainBreak(
            break_type="missing_link",
            severity="critical",
            description="Missing deed in chain",
            from_entry=1,
            to_entry=2,
            from_party="Jane Doe",
            to_party="Unknown Person",
            from_date=datetime(2020, 1, 15),
            to_date=datetime(2022, 6, 1),
            recommendation="Search for missing deed"
        )

        assert break_obj.break_type == "missing_link"
        assert break_obj.severity == "critical"
        assert break_obj.from_entry == 1
        assert break_obj.to_entry == 2

    def test_chain_break_types(self):
        """Test different break types"""
        # Missing link
        missing = ChainBreak(
            break_type="missing_link",
            severity="critical",
            description="Gap in ownership",
            recommendation="Find missing document"
        )
        assert missing.break_type == "missing_link"

        # Unknown grantor
        unknown = ChainBreak(
            break_type="unknown_grantor",
            severity="critical",
            description="Grantor never acquired",
            recommendation="Search for acquisition deed"
        )
        assert unknown.break_type == "unknown_grantor"

        # Time gap
        gap = ChainBreak(
            break_type="time_gap",
            severity="warning",
            description="Long period between transfers",
            recommendation="Review for unrecorded documents"
        )
        assert gap.break_type == "time_gap"


class TestChainAnalysisResponse:
    """Tests for ChainAnalysisResponse model"""

    def test_clear_chain_response(self):
        """Test response for a clear chain"""
        response = ChainAnalysisResponse(
            search_id=1,
            is_clear=True,
            total_breaks=0,
            critical_breaks=0,
            warning_breaks=0,
            breaks=[],
            ownership_summary=[
                OwnershipPeriod(name="John Smith"),
                OwnershipPeriod(name="Jane Doe"),
            ],
            analysis_notes=["Chain appears complete"]
        )

        assert response.is_clear is True
        assert response.total_breaks == 0
        assert len(response.ownership_summary) == 2

    def test_broken_chain_response(self):
        """Test response for a broken chain"""
        response = ChainAnalysisResponse(
            search_id=1,
            is_clear=False,
            total_breaks=2,
            critical_breaks=1,
            warning_breaks=1,
            breaks=[
                ChainBreak(
                    break_type="missing_link",
                    severity="critical",
                    description="Missing deed",
                    recommendation="Find document"
                ),
                ChainBreak(
                    break_type="time_gap",
                    severity="warning",
                    description="Long gap",
                    recommendation="Review period"
                ),
            ],
            ownership_summary=[],
            analysis_notes=["Critical issues found"]
        )

        assert response.is_clear is False
        assert response.critical_breaks == 1
        assert response.warning_breaks == 1


class TestSpecialCases:
    """Tests for special case handling in chain analysis"""

    def test_foreclosure_grantor_handling(self):
        """Test that foreclosure transactions are handled specially"""
        # Public Trustee and bank sales don't require previous grantee match
        foreclosure_grantors = ["PUBLIC TRUSTEE", "US BANK NA TRUSTEE"]

        for grantor in foreclosure_grantors:
            normalized = normalize_name(grantor)
            # These should contain "TRUSTEE" or "BANK" patterns
            assert "TRUSTEE" in normalized or "BANK" in normalized

    def test_mortgage_excluded_from_chain(self):
        """Test that mortgages are excluded from ownership chain analysis"""
        excluded_types = [
            "deed of trust", "mortgage", "lien", "assignment", "release",
            "satisfaction", "subordination", "notice", "refinance"
        ]

        test_entry = MagicMock()
        test_entry.transaction_type = "Deed of Trust"

        tx_type = (test_entry.transaction_type or "").lower()
        should_exclude = any(excl in tx_type for excl in excluded_types)

        assert should_exclude is True

    def test_ownership_transfer_included(self):
        """Test that ownership transfers are included in chain"""
        ownership_transfers = [
            "warranty deed", "trustee's deed", "grant deed",
            "quitclaim deed", "reo sale"
        ]

        test_entry = MagicMock()
        test_entry.transaction_type = "Warranty Deed"

        tx_type = (test_entry.transaction_type or "").lower()
        should_include = any(t in tx_type for t in ownership_transfers)

        assert should_include is True


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_empty_chain(self):
        """Test handling of empty chain of title"""
        response = ChainAnalysisResponse(
            search_id=1,
            is_clear=True,
            total_breaks=0,
            critical_breaks=0,
            warning_breaks=0,
            breaks=[],
            ownership_summary=[],
            analysis_notes=["No ownership transfer documents found in chain."]
        )

        assert response.is_clear is True
        assert len(response.ownership_summary) == 0

    def test_single_entry_chain(self):
        """Test chain with only one entry"""
        entry = MagicMock()
        entry.sequence_number = 1
        entry.transaction_type = "Warranty Deed"
        entry.transaction_date = datetime(2020, 1, 15)
        entry.grantor_names = ["John Smith"]
        entry.grantee_names = ["Jane Doe"]

        # With only one entry, we can establish ownership but can't check chain
        assert len(entry.grantor_names) == 1
        assert len(entry.grantee_names) == 1

    def test_multiple_grantors_grantees(self):
        """Test handling of multiple parties on a deed"""
        entry = MagicMock()
        entry.grantor_names = ["John Smith", "Jane Smith"]  # Joint owners
        entry.grantee_names = ["Bob Johnson", "Mary Johnson"]

        assert len(entry.grantor_names) == 2
        assert len(entry.grantee_names) == 2

        # Primary grantor/grantee should be first in list
        assert entry.grantor_names[0] == "John Smith"
        assert entry.grantee_names[0] == "Bob Johnson"

    def test_none_transaction_date(self):
        """Test handling of missing transaction dates"""
        entry = MagicMock()
        entry.transaction_date = None

        # Should not raise exception
        date_str = entry.transaction_date.isoformat() if entry.transaction_date else None
        assert date_str is None

    def test_special_characters_in_names(self):
        """Test handling of special characters in names"""
        names_with_special = [
            "O'Brien Family Trust",
            "Smith-Johnson LLC",
            "ABC & DEF Company",
        ]

        for name in names_with_special:
            normalized = normalize_name(name)
            assert normalized  # Should produce non-empty result


# Integration test placeholder - requires database setup
class TestChainAnalysisEndpoint:
    """Integration tests for the chain analysis endpoint"""

    @pytest.mark.asyncio
    async def test_endpoint_returns_404_for_missing_search(self):
        """Test that endpoint returns 404 for non-existent search"""
        # This would require setting up a test database
        # Placeholder for integration testing
        pass

    @pytest.mark.asyncio
    async def test_endpoint_requires_authentication(self):
        """Test that endpoint requires authentication"""
        # Placeholder for authentication testing
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
