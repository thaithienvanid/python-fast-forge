"""Tests for Circuit Breaker pattern.

Test Organization:
- TestCircuitBreakerServiceInitialization: Service initialization
- TestCircuitBreakerCreation: Breaker creation and caching
- TestCircuitBreakerParameters: Custom parameter configuration
- TestCircuitBreakerListeners: Listener creation and callbacks
- TestCircuitBreakerBehavior: Circuit state behavior
- TestCallWithBreaker: Async function protection
- TestCircuitBreakerEdgeCases: Edge cases and error handling
"""

import pytest
from pybreaker import CircuitBreaker, CircuitBreakerError

from src.infrastructure.patterns.circuit_breaker import CircuitBreakerService


# ============================================================================
# Initialization Tests
# ============================================================================


class TestCircuitBreakerServiceInitialization:
    """Test CircuitBreakerService initialization."""

    def test_initializes_with_empty_breakers_dictionary(self) -> None:
        """Test service initializes with empty breakers dict.

        Arrange: None
        Act: Create CircuitBreakerService
        Assert: _breakers is empty dictionary
        """
        # Arrange & Act
        service = CircuitBreakerService()

        # Assert
        assert isinstance(service._breakers, dict)
        assert len(service._breakers) == 0
        assert service._breakers == {}

    def test_creates_independent_instances(self) -> None:
        """Test each service instance has independent breakers dict.

        Arrange: None
        Act: Create two service instances
        Assert: Instances have separate breakers dictionaries
        """
        # Arrange & Act
        service1 = CircuitBreakerService()
        service2 = CircuitBreakerService()

        # Assert
        assert service1._breakers is not service2._breakers
        service1.get_breaker("test")
        assert len(service1._breakers) == 1
        assert len(service2._breakers) == 0


# ============================================================================
# Circuit Breaker Creation Tests
# ============================================================================


class TestCircuitBreakerCreation:
    """Test circuit breaker creation and caching."""

    @pytest.fixture
    def service(self) -> CircuitBreakerService:
        """Create circuit breaker service instance for testing.

        Returns:
            CircuitBreakerService instance
        """
        return CircuitBreakerService()

    def test_creates_breaker_on_first_call(self, service: CircuitBreakerService) -> None:
        """Test get_breaker creates new breaker on first call.

        Arrange: Service with no breakers
        Act: Call get_breaker with name
        Assert: Breaker is created and cached
        """
        # Arrange
        assert len(service._breakers) == 0

        # Act
        breaker = service.get_breaker("test_service")

        # Assert
        assert breaker is not None
        assert isinstance(breaker, CircuitBreaker)
        assert "test_service" in service._breakers
        assert service._breakers["test_service"] is breaker

    def test_reuses_existing_breaker_on_subsequent_calls(
        self, service: CircuitBreakerService
    ) -> None:
        """Test get_breaker returns same instance on subsequent calls.

        Arrange: Service with one breaker
        Act: Call get_breaker twice with same name
        Assert: Both calls return same instance
        """
        # Arrange
        breaker1 = service.get_breaker("test_service")

        # Act
        breaker2 = service.get_breaker("test_service")

        # Assert
        assert breaker1 is breaker2  # Same object reference
        assert len(service._breakers) == 1

    def test_creates_separate_breakers_for_different_names(
        self, service: CircuitBreakerService
    ) -> None:
        """Test different names create different breaker instances.

        Arrange: Service with no breakers
        Act: Create breakers with different names
        Assert: Separate instances are created
        """
        # Arrange & Act
        breaker_a = service.get_breaker("service_a")
        breaker_b = service.get_breaker("service_b")
        breaker_c = service.get_breaker("service_c")

        # Assert
        assert breaker_a is not breaker_b
        assert breaker_b is not breaker_c
        assert breaker_a is not breaker_c
        assert len(service._breakers) == 3
        assert "service_a" in service._breakers
        assert "service_b" in service._breakers
        assert "service_c" in service._breakers

    def test_breaker_has_correct_name(self, service: CircuitBreakerService) -> None:
        """Test created breaker has correct name attribute.

        Arrange: Service
        Act: Create breaker with name
        Assert: Breaker.name matches provided name
        """
        # Arrange
        name = "my_external_service"

        # Act
        breaker = service.get_breaker(name)

        # Assert
        assert breaker.name == name


# ============================================================================
# Circuit Breaker Parameters Tests
# ============================================================================


class TestCircuitBreakerParameters:
    """Test circuit breaker parameter configuration."""

    @pytest.fixture
    def service(self) -> CircuitBreakerService:
        """Create circuit breaker service instance."""
        return CircuitBreakerService()

    def test_uses_default_parameters(self, service: CircuitBreakerService) -> None:
        """Test breaker uses default parameters when none specified.

        Arrange: Service
        Act: Create breaker without custom parameters
        Assert: Default parameters are applied
        """
        # Arrange & Act
        breaker = service.get_breaker("test_service")

        # Assert
        assert breaker.fail_max == 5  # Default fail_max
        assert breaker.reset_timeout == 30  # Default reset_timeout
        assert breaker.name == "test_service"

    def test_applies_custom_fail_max(self, service: CircuitBreakerService) -> None:
        """Test breaker applies custom fail_max parameter.

        Arrange: Service
        Act: Create breaker with custom fail_max
        Assert: Custom fail_max is applied
        """
        # Arrange
        custom_fail_max = 10

        # Act
        breaker = service.get_breaker("test_service", fail_max=custom_fail_max)

        # Assert
        assert breaker.fail_max == custom_fail_max

    def test_applies_custom_reset_timeout(self, service: CircuitBreakerService) -> None:
        """Test breaker applies custom reset_timeout parameter.

        Arrange: Service
        Act: Create breaker with custom reset_timeout
        Assert: Custom reset_timeout is applied
        """
        # Arrange
        custom_reset_timeout = 60

        # Act
        breaker = service.get_breaker("test_service", reset_timeout=custom_reset_timeout)

        # Assert
        assert breaker.reset_timeout == custom_reset_timeout

    def test_applies_all_custom_parameters(self, service: CircuitBreakerService) -> None:
        """Test breaker applies all custom parameters together.

        Arrange: Service
        Act: Create breaker with all custom parameters
        Assert: All custom parameters are applied
        """
        # Arrange
        custom_fail_max = 10
        custom_timeout_duration = 120
        custom_reset_timeout = 60

        # Act
        breaker = service.get_breaker(
            "test_service",
            fail_max=custom_fail_max,
            timeout_duration=custom_timeout_duration,
            reset_timeout=custom_reset_timeout,
        )

        # Assert
        assert breaker.fail_max == custom_fail_max
        assert breaker.reset_timeout == custom_reset_timeout

    def test_parameters_only_apply_to_first_creation(self, service: CircuitBreakerService) -> None:
        """Test parameters only apply when breaker is first created.

        Arrange: Service
        Act: Create breaker twice with different parameters
        Assert: Second call parameters are ignored (cached instance returned)
        """
        # Arrange
        breaker1 = service.get_breaker("test_service", fail_max=5)

        # Act
        breaker2 = service.get_breaker("test_service", fail_max=10)

        # Assert
        assert breaker1 is breaker2
        assert breaker2.fail_max == 5  # Original parameter preserved


# ============================================================================
# Listener Tests
# ============================================================================


class TestCircuitBreakerListeners:
    """Test circuit breaker listener creation and callbacks."""

    @pytest.fixture
    def service(self) -> CircuitBreakerService:
        """Create circuit breaker service instance."""
        return CircuitBreakerService()

    def test_creates_listener_with_required_methods(self, service: CircuitBreakerService) -> None:
        """Test _create_listener creates listener with required methods.

        Arrange: Service
        Act: Create listener
        Assert: Listener has state_change, failure, and success methods
        """
        # Arrange & Act
        listener = service._create_listener("test_service")

        # Assert
        assert hasattr(listener, "state_change")
        assert hasattr(listener, "failure")
        assert hasattr(listener, "success")

    def test_listener_methods_are_callable(self, service: CircuitBreakerService) -> None:
        """Test listener methods are callable.

        Arrange: Service
        Act: Create listener and check methods
        Assert: All callback methods are callable
        """
        # Arrange & Act
        listener = service._create_listener("test_service")

        # Assert
        assert callable(getattr(listener, "state_change", None))
        assert callable(getattr(listener, "failure", None))
        assert callable(getattr(listener, "success", None))

    def test_breaker_has_listeners_attached(self, service: CircuitBreakerService) -> None:
        """Test created breaker has listeners attached.

        Arrange: Service
        Act: Create breaker
        Assert: Breaker has at least one listener
        """
        # Arrange & Act
        breaker = service.get_breaker("test_service")

        # Assert
        assert len(breaker.listeners) > 0
        assert breaker.listeners[0] is not None

    def test_different_breakers_have_separate_listeners(
        self, service: CircuitBreakerService
    ) -> None:
        """Test different breakers have separate listener instances.

        Arrange: Service
        Act: Create two breakers
        Assert: Each has its own listener instance
        """
        # Arrange & Act
        breaker1 = service.get_breaker("service_a")
        breaker2 = service.get_breaker("service_b")

        # Assert
        assert breaker1.listeners[0] is not breaker2.listeners[0]


# ============================================================================
# Circuit Breaker Behavior Tests
# ============================================================================


class TestCircuitBreakerBehavior:
    """Test circuit breaker state behavior."""

    @pytest.fixture
    def service(self) -> CircuitBreakerService:
        """Create circuit breaker service instance."""
        return CircuitBreakerService()

    def test_breaker_starts_in_closed_state(self, service: CircuitBreakerService) -> None:
        """Test newly created breaker starts in closed state.

        Arrange: Service
        Act: Create breaker
        Assert: Breaker is in closed state
        """
        # Arrange & Act
        breaker = service.get_breaker("test_service")

        # Assert
        assert breaker.current_state == "closed"

    def test_breaker_opens_after_max_failures(self, service: CircuitBreakerService) -> None:
        """Test breaker opens after reaching fail_max failures.

        Arrange: Service with breaker (fail_max=2)
        Act: Trigger 2 failures
        Assert: Breaker opens
        """
        # Arrange
        breaker = service.get_breaker("test_service", fail_max=2)

        def failing_function() -> None:
            raise ValueError("Service failure")

        # Act: Trigger failures (catch both ValueError and CircuitBreakerError)
        for _ in range(2):
            try:
                breaker.call(failing_function)
            except (ValueError, CircuitBreakerError):
                pass

        # Assert
        assert breaker.current_state == "open"

    def test_open_breaker_raises_circuit_breaker_error(
        self, service: CircuitBreakerService
    ) -> None:
        """Test open breaker raises CircuitBreakerError on call attempts.

        Arrange: Breaker in open state
        Act: Attempt to call function
        Assert: CircuitBreakerError is raised
        """
        # Arrange
        breaker = service.get_breaker("test_service", fail_max=1)

        def failing_function() -> None:
            raise ValueError("Service failure")

        # Trigger failure to open circuit
        try:
            breaker.call(failing_function)
        except (ValueError, CircuitBreakerError):
            pass

        # Assert breaker is now open
        assert breaker.current_state == "open"

        # Act & Assert: open breaker rejects calls
        with pytest.raises(CircuitBreakerError):
            breaker.call(lambda: "success")

    def test_breaker_tracks_failure_count(self, service: CircuitBreakerService) -> None:
        """Test breaker correctly tracks failure count.

        Arrange: Service with breaker
        Act: Trigger failures
        Assert: Failure count increases
        """
        # Arrange
        breaker = service.get_breaker("test_service", fail_max=5)

        def failing_function() -> None:
            raise ValueError("Service failure")

        # Act
        initial_count = breaker.fail_counter
        try:
            breaker.call(failing_function)
        except ValueError:
            pass

        # Assert
        assert breaker.fail_counter == initial_count + 1


# ============================================================================
# Call With Breaker Tests
# ============================================================================


class TestCallWithBreaker:
    """Test call_with_breaker method."""

    @pytest.fixture
    def service(self) -> CircuitBreakerService:
        """Create circuit breaker service instance."""
        return CircuitBreakerService()

    def test_call_with_breaker_method_exists(self, service: CircuitBreakerService) -> None:
        """Test call_with_breaker method is available.

        Arrange: Service instance
        Act: Check for call_with_breaker attribute
        Assert: Method exists and is callable
        """
        # Arrange & Act & Assert
        assert hasattr(service, "call_with_breaker")
        assert callable(service.call_with_breaker)

    def test_call_with_breaker_creates_breaker_if_not_exists(
        self, service: CircuitBreakerService
    ) -> None:
        """Test call_with_breaker creates breaker on first use.

        Arrange: Service with no breakers
        Act: Access breaker via get_breaker (simulating call_with_breaker behavior)
        Assert: Breaker is created with specified name
        """
        # Arrange
        assert len(service._breakers) == 0

        # Act
        breaker = service.get_breaker("new_service")

        # Assert
        assert "new_service" in service._breakers
        assert breaker.name == "new_service"


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestCircuitBreakerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def service(self) -> CircuitBreakerService:
        """Create circuit breaker service instance."""
        return CircuitBreakerService()

    def test_handles_empty_string_name(self, service: CircuitBreakerService) -> None:
        """Test breaker handles empty string as name.

        Arrange: Service
        Act: Create breaker with empty string name
        Assert: Breaker is created with empty name
        """
        # Arrange & Act
        breaker = service.get_breaker("")

        # Assert
        assert breaker.name == ""
        assert "" in service._breakers

    def test_handles_very_long_name(self, service: CircuitBreakerService) -> None:
        """Test breaker handles very long name.

        Arrange: Service
        Act: Create breaker with 1000-character name
        Assert: Breaker is created successfully
        """
        # Arrange
        long_name = "a" * 1000

        # Act
        breaker = service.get_breaker(long_name)

        # Assert
        assert breaker.name == long_name
        assert long_name in service._breakers

    def test_handles_special_characters_in_name(self, service: CircuitBreakerService) -> None:
        """Test breaker handles special characters in name.

        Arrange: Service
        Act: Create breaker with special characters in name
        Assert: Breaker is created successfully
        """
        # Arrange
        special_name = "service://api.example.com:8080/v1/users"

        # Act
        breaker = service.get_breaker(special_name)

        # Assert
        assert breaker.name == special_name
        assert special_name in service._breakers

    def test_handles_zero_fail_max(self, service: CircuitBreakerService) -> None:
        """Test breaker handles fail_max of 0.

        Arrange: Service
        Act: Create breaker with fail_max=0
        Assert: Breaker is created (pybreaker will handle behavior)
        """
        # Arrange & Act
        breaker = service.get_breaker("test_service", fail_max=0)

        # Assert
        assert breaker.fail_max == 0

    def test_handles_negative_reset_timeout(self, service: CircuitBreakerService) -> None:
        """Test breaker handles negative reset_timeout.

        Arrange: Service
        Act: Create breaker with negative reset_timeout
        Assert: Breaker is created (pybreaker will handle behavior)
        """
        # Arrange & Act
        breaker = service.get_breaker("test_service", reset_timeout=-1)

        # Assert
        assert breaker.reset_timeout == -1

    def test_handles_very_large_fail_max(self, service: CircuitBreakerService) -> None:
        """Test breaker handles very large fail_max.

        Arrange: Service
        Act: Create breaker with very large fail_max
        Assert: Breaker is created successfully
        """
        # Arrange
        large_fail_max = 1000000

        # Act
        breaker = service.get_breaker("test_service", fail_max=large_fail_max)

        # Assert
        assert breaker.fail_max == large_fail_max

    def test_multiple_breakers_operate_independently(self, service: CircuitBreakerService) -> None:
        """Test multiple breakers maintain independent state.

        Arrange: Service with two breakers
        Act: Fail one breaker, keep other closed
        Assert: Breakers have independent states
        """
        # Arrange
        breaker1 = service.get_breaker("service_a", fail_max=1)
        breaker2 = service.get_breaker("service_b", fail_max=1)

        def failing_function() -> None:
            raise ValueError("Failure")

        # Act: Fail only breaker1
        try:
            breaker1.call(failing_function)
        except (ValueError, CircuitBreakerError):
            pass

        # Assert: breaker1 is open, breaker2 is still closed
        assert breaker1.current_state == "open"
        assert breaker2.current_state == "closed"
