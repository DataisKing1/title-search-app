"""Unit tests for application configuration"""
import pytest
import os
from unittest.mock import patch


class TestConfig:
    """Tests for Settings configuration class"""

    def test_default_settings(self):
        """Test that default settings are properly loaded"""
        # Clear lru_cache to ensure fresh settings
        from app.config import get_settings
        get_settings.cache_clear()

        from app.config import settings

        assert settings.APP_NAME == "Title Search Application"
        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is False
        assert settings.BROWSER_POOL_SIZE == 5
        assert settings.SCRAPING_MAX_RETRIES == 3

    def test_secret_key_not_random(self):
        """Test that SECRET_KEY is persistent (not random) in development"""
        from app.config import get_settings
        get_settings.cache_clear()

        from app.config import settings, _DEV_SECRET_KEY

        # In development, should use the persistent dev key
        assert settings.SECRET_KEY == _DEV_SECRET_KEY

    def test_allowed_origins_list(self):
        """Test that ALLOWED_ORIGINS is properly parsed"""
        from app.config import settings

        origins = settings.allowed_origins_list
        assert isinstance(origins, list)
        assert "http://localhost:5173" in origins
        assert "http://localhost:3000" in origins

    def test_max_upload_size_bytes(self):
        """Test that max upload size is calculated correctly"""
        from app.config import settings

        # Default is 50MB
        assert settings.max_upload_size_bytes == 50 * 1024 * 1024

    def test_allowed_extensions_list(self):
        """Test that file extensions are properly parsed"""
        from app.config import settings

        extensions = settings.allowed_extensions_list
        assert isinstance(extensions, list)
        assert ".pdf" in extensions
        assert ".png" in extensions
        assert ".jpg" in extensions

    def test_allowed_mimetypes_list(self):
        """Test that MIME types are properly parsed"""
        from app.config import settings

        mimetypes = settings.allowed_mimetypes_list
        assert isinstance(mimetypes, list)
        assert "application/pdf" in mimetypes
        assert "image/png" in mimetypes

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SECRET_KEY": "a" * 32})
    def test_production_secret_key_validation(self):
        """Test that production requires proper SECRET_KEY"""
        from app.config import get_settings, Settings

        get_settings.cache_clear()

        # This should work with a 32+ char key
        settings = Settings(ENVIRONMENT="production", SECRET_KEY="a" * 32)
        assert len(settings.SECRET_KEY) >= 32

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_production_rejects_dev_key(self):
        """Test that production rejects the development key"""
        from app.config import get_settings, Settings, _DEV_SECRET_KEY

        get_settings.cache_clear()

        # This should raise an error
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            Settings(ENVIRONMENT="production", SECRET_KEY=_DEV_SECRET_KEY)

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_production_rejects_short_key(self):
        """Test that production rejects short SECRET_KEY"""
        from app.config import get_settings, Settings

        get_settings.cache_clear()

        # Short key should be rejected
        with pytest.raises(ValueError, match="at least 32 characters"):
            Settings(ENVIRONMENT="production", SECRET_KEY="short")


class TestScrapingConfig:
    """Tests for scraping-related configuration"""

    def test_scraping_defaults(self):
        """Test scraping configuration defaults"""
        from app.config import settings

        assert settings.SCRAPING_MAX_RETRIES == 3
        assert settings.SCRAPING_RETRY_DELAY_SECONDS == 120
        assert settings.SCRAPING_RATE_LIMIT_DELAY_SECONDS == 60
        assert settings.SCRAPING_DEFAULT_SEARCH_YEARS == 40

    def test_browser_pool_defaults(self):
        """Test browser pool configuration defaults"""
        from app.config import settings

        assert settings.BROWSER_HEADLESS is True
        assert settings.BROWSER_POOL_SIZE == 5
        assert settings.BROWSER_TIMEOUT == 30000
        assert settings.BROWSER_MAX_REQUESTS_PER_INSTANCE == 100


class TestAIConfig:
    """Tests for AI-related configuration"""

    def test_ai_defaults(self):
        """Test AI configuration defaults"""
        from app.config import settings

        assert settings.DEFAULT_AI_PROVIDER == "openai"
        assert settings.DEFAULT_AI_MODEL == "gpt-4-turbo-preview"
        assert settings.OCR_DPI == 300
        assert settings.AI_TEXT_TRUNCATION_LIMIT == 15000
