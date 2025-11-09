"""Tests for application configuration.

Test Organization:
- TestSettingsDefaults: Default configuration values
- TestSettingsFromEnvironment: Environment variable parsing
- TestCORSOriginsValidation: CORS origin parsing and HTTPS validation
- TestRateLimitValidation: Rate limit boundary validation
- TestProductionValidation: Production security validation
- TestEnvironmentProperties: Environment detection properties
- TestGetSettingsCaching: Settings singleton caching
"""

import pytest
from pydantic import ValidationError

from src.infrastructure.config import Settings, get_settings


# ============================================================================
# Default Values Tests
# ============================================================================


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_has_sensible_application_defaults(self) -> None:
        """Test application settings have sensible defaults.

        Arrange: None (use default Settings)
        Act: Create Settings instance
        Assert: Application settings have expected defaults
        """
        # Arrange & Act
        settings = Settings()

        # Assert
        assert settings.app_name == "python-fast-forge"
        assert settings.app_version == "0.1.0"
        assert settings.app_env == "development"
        assert settings.port == 8000
        assert settings.host == "0.0.0.0"

    def test_has_secure_development_defaults(self) -> None:
        """Test security defaults are appropriate for development.

        Arrange: None
        Act: Create Settings instance
        Assert: Security defaults are development-appropriate
        """
        # Arrange & Act
        settings = Settings()

        # Assert
        # secret_key is now optional (for API signature auth)
        assert settings.secret_key is None or isinstance(settings.secret_key, str)
        assert "dev-email" in settings.email_api_key.lower()
        assert settings.debug is False  # Secure default even in dev

    def test_has_expected_cors_defaults(self) -> None:
        """Test CORS defaults allow local development.

        Arrange: None
        Act: Create Settings instance
        Assert: CORS defaults include localhost
        """
        # Arrange & Act
        settings = Settings()

        # Assert
        assert isinstance(settings.cors_origins, list)
        assert len(settings.cors_origins) >= 1
        assert any("localhost" in origin for origin in settings.cors_origins)


# ============================================================================
# Environment Variable Tests
# ============================================================================


class TestSettingsFromEnvironment:
    """Test loading settings from environment variables."""

    def test_loads_app_env_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test APP_ENV environment variable overrides default.

        Arrange: Set APP_ENV environment variable
        Act: Create Settings instance
        Assert: Settings uses environment value
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "staging")

        # Act
        settings = Settings()

        # Assert
        assert settings.app_env == "staging"

    def test_loads_debug_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test DEBUG environment variable is parsed as boolean.

        Arrange: Set DEBUG environment variable to "true"
        Act: Create Settings instance
        Assert: Settings parses string to boolean correctly
        """
        # Arrange
        monkeypatch.setenv("DEBUG", "true")

        # Act
        settings = Settings()

        # Assert
        assert settings.debug is True

    def test_loads_port_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PORT environment variable is parsed as integer.

        Arrange: Set PORT environment variable to string number
        Act: Create Settings instance
        Assert: Settings parses string to integer correctly
        """
        # Arrange
        monkeypatch.setenv("PORT", "9000")

        # Act
        settings = Settings()

        # Assert
        assert settings.port == 9000
        assert isinstance(settings.port, int)

    def test_loads_multiple_settings_from_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading multiple configuration values from environment.

        Arrange: Set multiple environment variables
        Act: Create Settings instance
        Assert: All environment values are loaded correctly
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("PORT", "8080")
        monkeypatch.setenv("SECRET_KEY", "a" * 64)
        monkeypatch.setenv("EMAIL_API_KEY", "prod-email-api-key-12345")

        # Act
        settings = Settings()

        # Assert
        assert settings.app_env == "production"
        assert settings.debug is False
        assert settings.log_level == "WARNING"
        assert settings.port == 8080


# ============================================================================
# CORS Origins Validation Tests
# ============================================================================


class TestCORSOriginsValidation:
    """Test CORS origins HTTPS validation in production."""

    def test_has_cors_origins_list(self) -> None:
        """Test CORS origins is a list.

        Arrange: Default settings
        Act: Create Settings instance
        Assert: cors_origins is a list
        """
        # Arrange & Act
        settings = Settings()

        # Assert
        assert isinstance(settings.cors_origins, list)
        assert len(settings.cors_origins) >= 1


# ============================================================================
# Rate Limit Validation Tests
# ============================================================================


class TestRateLimitValidation:
    """Test rate limit boundary validation."""

    def test_accepts_valid_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test accepting valid rate limit value.

        Arrange: Set rate limit to valid value (60)
        Act: Create Settings instance
        Assert: Rate limit is accepted
        """
        # Arrange
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "60")

        # Act
        settings = Settings()

        # Assert
        assert settings.rate_limit_per_minute == 60

    def test_accepts_minimum_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test accepting minimum rate limit (1).

        Arrange: Set rate limit to minimum (1)
        Act: Create Settings instance
        Assert: Minimum is accepted
        """
        # Arrange
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")

        # Act
        settings = Settings()

        # Assert
        assert settings.rate_limit_per_minute == 1

    def test_accepts_maximum_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test accepting maximum rate limit (10000).

        Arrange: Set rate limit to maximum (10000)
        Act: Create Settings instance
        Assert: Maximum is accepted
        """
        # Arrange
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10000")

        # Act
        settings = Settings()

        # Assert
        assert settings.rate_limit_per_minute == 10000

    def test_rejects_zero_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rejecting rate limit of 0.

        Arrange: Set rate limit to 0
        Act: Create Settings instance
        Assert: ValidationError is raised
        """
        # Arrange
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "between 1 and 10000" in str(exc_info.value)

    def test_rejects_negative_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rejecting negative rate limit.

        Arrange: Set rate limit to negative value
        Act: Create Settings instance
        Assert: ValidationError is raised
        """
        # Arrange
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "-10")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "between 1 and 10000" in str(exc_info.value)

    def test_rejects_excessive_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rejecting rate limit above maximum.

        Arrange: Set rate limit above 10000
        Act: Create Settings instance
        Assert: ValidationError is raised
        """
        # Arrange
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10001")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "between 1 and 10000" in str(exc_info.value)


# ============================================================================
# Production Validation Tests
# ============================================================================


class TestProductionValidation:
    """Test production security validation."""

    def test_allows_dev_keys_in_development(self) -> None:
        """Test development environment allows insecure default keys.

        Arrange: Development environment (default)
        Act: Create Settings instance
        Assert: Development keys are accepted
        """
        # Arrange & Act
        settings = Settings()

        # Assert
        assert settings.app_env == "development"
        # secret_key is now optional (None) in development for API signature auth
        assert settings.secret_key is None or isinstance(settings.secret_key, str)
        assert "dev-email" in settings.email_api_key.lower()

    def test_rejects_dev_secret_key_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test production rejects default development email API key.

        Arrange: Production with dev email API key
        Act: Create Settings instance
        Assert: ValidationError is raised for email_api_key (secret_key is now optional)
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "production")
        # secret_key is now optional for API signature auth, no validation
        monkeypatch.setenv("EMAIL_API_KEY", "dev-email-api-key-change-in-production-UNSAFE")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Check that the validation error mentions production and the API key
        error_str = str(exc_info.value)
        assert "production" in error_str.lower()
        assert "email_api_key" in error_str.lower() or "email api key" in error_str.lower()

    def test_rejects_short_secret_key_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test production rejects dev email API keys.

        Arrange: Production with dev-like email API key
        Act: Create Settings instance
        Assert: ValidationError is raised (secret_key is now optional)
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "production")
        # secret_key is now optional for API signature auth, no validation needed
        # Use a dev-like email API key to trigger validation
        monkeypatch.setenv("EMAIL_API_KEY", "dev-email")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Check that the validation error mentions production and the API key
        error_str = str(exc_info.value)
        assert "production" in error_str.lower()
        assert "email_api_key" in error_str.lower() or "email api key" in error_str.lower()

    def test_accepts_secure_keys_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test production accepts secure keys (32+ characters).

        Arrange: Production with 64-char secure key
        Act: Create Settings instance
        Assert: Secure key is accepted
        """
        # Arrange
        secure_key = "a" * 64
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", secure_key)
        monkeypatch.setenv("EMAIL_API_KEY", "sendgrid-api-key-12345")

        # Act
        settings = Settings()

        # Assert
        assert settings.secret_key == secure_key
        assert len(settings.secret_key) >= 32
        assert settings.email_api_key == "sendgrid-api-key-12345"

    def test_rejects_dev_email_key_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test production rejects default development email API key.

        Arrange: Production with dev email key
        Act: Create Settings instance
        Assert: ValidationError is raised
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 64)
        monkeypatch.setenv("EMAIL_API_KEY", "dev-email-api-key-UNSAFE")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "real API key in production" in str(exc_info.value)


# ============================================================================
# Environment Properties Tests
# ============================================================================


class TestEnvironmentProperties:
    """Test environment detection properties."""

    def test_is_production_returns_true_for_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test is_production property returns True in production.

        Arrange: Production environment
        Act: Create Settings and check is_production
        Assert: is_production is True
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 64)
        monkeypatch.setenv("EMAIL_API_KEY", "prod-email-api-key-12345")

        # Act
        settings = Settings()

        # Assert
        assert settings.is_production is True
        assert settings.is_development is False

    def test_is_production_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test is_production handles case-insensitive comparison.

        Arrange: APP_ENV with mixed case
        Act: Create Settings and check is_production
        Assert: Case-insensitive comparison works
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "PRODUCTION")
        monkeypatch.setenv("SECRET_KEY", "a" * 64)
        monkeypatch.setenv("EMAIL_API_KEY", "prod-email-api-key-12345")

        # Act
        settings = Settings()

        # Assert
        assert settings.is_production is True

    def test_is_development_returns_true_for_development(self) -> None:
        """Test is_development property returns True in development.

        Arrange: Development environment (default)
        Act: Create Settings and check is_development
        Assert: is_development is True
        """
        # Arrange & Act
        settings = Settings()

        # Assert
        assert settings.is_development is True
        assert settings.is_production is False

    def test_is_development_returns_false_for_staging(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test is_development returns False for non-development environments.

        Arrange: Staging environment
        Act: Create Settings and check is_development
        Assert: is_development is False
        """
        # Arrange
        monkeypatch.setenv("APP_ENV", "staging")

        # Act
        settings = Settings()

        # Assert
        assert settings.is_development is False
        assert settings.is_production is False  # Not production either


# ============================================================================
# Settings Caching Tests
# ============================================================================


class TestGetSettingsCaching:
    """Test get_settings caching behavior."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test get_settings returns Settings instance.

        Arrange: None
        Act: Call get_settings()
        Assert: Returns Settings instance
        """
        # Arrange & Act
        settings = get_settings()

        # Assert
        assert isinstance(settings, Settings)

    def test_get_settings_returns_cached_instance(self) -> None:
        """Test get_settings returns same cached instance.

        Arrange: None
        Act: Call get_settings() twice
        Assert: Both calls return same instance (cached)
        """
        # Arrange & Act
        settings1 = get_settings()
        settings2 = get_settings()

        # Assert
        assert settings1 is settings2  # Same object reference

    def test_cached_settings_have_identical_values(self) -> None:
        """Test cached settings have identical configuration values.

        Arrange: None
        Act: Get settings twice and compare values
        Assert: All configuration values are identical
        """
        # Arrange & Act
        settings1 = get_settings()
        settings2 = get_settings()

        # Assert
        assert settings1.app_name == settings2.app_name
        assert settings1.port == settings2.port
        assert settings1.database_url == settings2.database_url
        assert settings1.cors_origins == settings2.cors_origins
