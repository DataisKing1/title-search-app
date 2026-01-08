"""Unit tests for file upload validation"""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

# Import after loading all modules
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers.documents import validate_upload_file, detect_mime_type
from app.config import settings


class TestFileUploadValidation:
    """Tests for file upload validation functions"""

    def test_validate_upload_file_rejects_large_files(self):
        """Test that files larger than max size are rejected"""
        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"

        # File larger than max size
        file_size = settings.max_upload_size_bytes + 1

        with pytest.raises(HTTPException) as exc_info:
            validate_upload_file(mock_file, file_size)

        assert exc_info.value.status_code == 413
        assert "too large" in exc_info.value.detail.lower()

    def test_validate_upload_file_accepts_valid_file(self):
        """Test that valid files pass validation"""
        mock_file = MagicMock()
        mock_file.filename = "document.pdf"
        mock_file.content_type = "application/pdf"

        # Valid file size (1MB)
        file_size = 1024 * 1024

        # Should not raise any exception
        validate_upload_file(mock_file, file_size)

    def test_validate_upload_file_rejects_invalid_extension(self):
        """Test that files with invalid extensions are rejected"""
        mock_file = MagicMock()
        mock_file.filename = "malware.exe"
        mock_file.content_type = None  # No content type

        with pytest.raises(HTTPException) as exc_info:
            validate_upload_file(mock_file, 1024)

        assert exc_info.value.status_code == 415
        assert "not allowed" in exc_info.value.detail.lower()

    def test_validate_upload_file_rejects_invalid_mimetype(self):
        """Test that files with invalid MIME types are rejected"""
        mock_file = MagicMock()
        mock_file.filename = "file"  # No extension
        mock_file.content_type = "text/html"  # Invalid MIME type

        with pytest.raises(HTTPException) as exc_info:
            validate_upload_file(mock_file, 1024)

        assert exc_info.value.status_code == 415

    def test_validate_upload_file_accepts_png(self):
        """Test that PNG files are accepted"""
        mock_file = MagicMock()
        mock_file.filename = "image.png"
        mock_file.content_type = "image/png"

        # Should not raise any exception
        validate_upload_file(mock_file, 1024 * 100)

    def test_validate_upload_file_accepts_jpg(self):
        """Test that JPG files are accepted"""
        mock_file = MagicMock()
        mock_file.filename = "photo.jpg"
        mock_file.content_type = "image/jpeg"

        # Should not raise any exception
        validate_upload_file(mock_file, 1024 * 100)


class TestDetectMimeType:
    """Tests for MIME type detection"""

    def test_detect_mime_type_pdf(self):
        """Test MIME type detection for PDF"""
        result = detect_mime_type(".pdf", None)
        assert result == "application/pdf"

    def test_detect_mime_type_png(self):
        """Test MIME type detection for PNG"""
        result = detect_mime_type(".png", None)
        assert result == "image/png"

    def test_detect_mime_type_jpg(self):
        """Test MIME type detection for JPG"""
        result = detect_mime_type(".jpg", None)
        assert result == "image/jpeg"

    def test_detect_mime_type_jpeg(self):
        """Test MIME type detection for JPEG"""
        result = detect_mime_type(".jpeg", None)
        assert result == "image/jpeg"

    def test_detect_mime_type_tiff(self):
        """Test MIME type detection for TIFF"""
        result = detect_mime_type(".tiff", None)
        assert result == "image/tiff"

    def test_detect_mime_type_tif(self):
        """Test MIME type detection for TIF"""
        result = detect_mime_type(".tif", None)
        assert result == "image/tiff"

    def test_detect_mime_type_fallback_to_content_type(self):
        """Test MIME type falls back to provided content type"""
        # Unknown extension but valid content type
        result = detect_mime_type(".unknown", "application/pdf")
        assert result == "application/pdf"

    def test_detect_mime_type_returns_octet_stream_for_unknown(self):
        """Test MIME type returns octet-stream for completely unknown types"""
        result = detect_mime_type(".xyz", "weird/unknown-type")
        assert result == "application/octet-stream"

    def test_detect_mime_type_case_insensitive(self):
        """Test MIME type detection is case insensitive"""
        result = detect_mime_type(".PDF", None)
        assert result == "application/pdf"

        result = detect_mime_type(".PNG", None)
        assert result == "image/png"
