"""Unit tests for infrastructure __init__ module imports."""


class TestInfrastructureImports:
    """Test that infrastructure modules can be imported successfully."""

    def test_resilience_module_imports(self):
        """Resilience module exports expected classes."""
        from src.infrastructure.resilience import (
            CircuitBreaker,
            CircuitBreakerOpenError,
            CircuitBreakerStats,
            CircuitState,
        )

        assert CircuitBreaker is not None
        assert CircuitBreakerOpenError is not None
        assert CircuitBreakerStats is not None
        assert CircuitState is not None

    def test_services_module_imports(self):
        """Services module exports expected classes."""
        from src.infrastructure.services import EmailService, get_email_service

        assert EmailService is not None
        assert get_email_service is not None

    def test_messaging_module_imports(self):
        """Messaging module can be imported."""
        from src.infrastructure import messaging

        assert messaging is not None
        assert hasattr(messaging, "__all__")

    def test_plugins_module_imports(self):
        """Plugins module can be imported."""
        from src.infrastructure import plugins

        assert plugins is not None

    def test_cache_module_imports(self):
        """Cache module exports expected classes."""
        from src.infrastructure.cache import RedisCache

        assert RedisCache is not None


class TestAppModuleImports:
    """Test that app modules can be imported successfully."""

    def test_tasks_module_imports(self):
        """Tasks module exports expected classes."""
        from src.app.tasks import SendWelcomeEmailWorkflow, send_welcome_email_activity

        assert SendWelcomeEmailWorkflow is not None
        assert send_welcome_email_activity is not None

    def test_commands_module_all_exports(self):
        """Commands module __all__ contains all command classes."""
        from src.app import commands

        assert "CreateUserCommand" in commands.__all__
        assert "UpdateUserCommand" in commands.__all__
        assert "DeleteUserCommand" in commands.__all__
        assert "RestoreUserCommand" in commands.__all__

    def test_queries_module_all_exports(self):
        """Queries module __all__ contains all query classes."""
        from src.app import queries

        assert "UserQueryModel" in queries.__all__
        assert "UserListQuery" in queries.__all__
        assert "UserDetailQuery" in queries.__all__
        assert "UserSearchQuery" in queries.__all__
        assert "UserStatsQuery" in queries.__all__

    def test_usecases_module_imports(self):
        """Usecases module can be imported."""
        from src.app import usecases

        assert usecases is not None
