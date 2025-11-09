"""Hypothesis strategies for property-based testing.

Property-based testing finds edge cases by generating hundreds of test cases
automatically. This is more thorough than example-based testing.

Install hypothesis:
    pip install hypothesis

Usage:
    from hypothesis import given
    from tests.strategies import user_strategy

    @given(user=user_strategy())
    def test_user_property(user):
        # Test runs with 100+ generated users
        assert user.email is not None
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from hypothesis import strategies as st
from uuid_extension import uuid7

from src.domain.models.user import User


# ============================================================================
# Basic Strategies
# ============================================================================


@st.composite
def uuid7_strategy(draw: st.DrawFn) -> UUID:
    """Generate valid UUIDv7 instances.

    UUIDv7 is time-ordered, so we can generate realistic IDs.

    Args:
        draw: Hypothesis draw function

    Returns:
        Valid UUIDv7 instance

    Example:
        >>> from hypothesis import given
        >>> @given(user_id=uuid7_strategy())
        ... def test_with_uuid(user_id):
        ...     assert isinstance(user_id, UUID)
    """
    return uuid7()


@st.composite
def email_strategy(draw: st.DrawFn) -> str:
    """Generate valid email addresses.

    Args:
        draw: Hypothesis draw function

    Returns:
        Valid email address string

    Example:
        >>> from hypothesis import given
        >>> @given(email=email_strategy())
        ... def test_with_email(email):
        ...     assert "@" in email
    """
    # Use hypothesis built-in email strategy
    return draw(st.emails())


@st.composite
def username_strategy(draw: st.DrawFn, min_size: int = 3, max_size: int = 50) -> str:
    """Generate valid usernames.

    Usernames must:
    - Be 3-50 characters
    - Contain only ASCII letters, numbers, underscores, hyphens
    - Match pattern: ^[a-zA-Z0-9_-]+$

    Args:
        draw: Hypothesis draw function
        min_size: Minimum username length
        max_size: Maximum username length

    Returns:
        Valid username string

    Example:
        >>> from hypothesis import given
        >>> @given(username=username_strategy())
        ... def test_with_username(username):
        ...     assert 3 <= len(username) <= 50
    """
    # Valid characters: ASCII letters, digits, underscore, hyphen
    # Use explicit string to ensure we only get characters matching ^[a-zA-Z0-9_-]+$
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"

    # Generate username
    username = draw(
        st.text(
            alphabet=alphabet,
            min_size=min_size,
            max_size=max_size,
        )
    )

    return username


@st.composite
def datetime_strategy(
    draw: st.DrawFn,
    min_value: datetime | None = None,
    max_value: datetime | None = None,
) -> datetime:
    """Generate datetime instances with timezone.

    Args:
        draw: Hypothesis draw function
        min_value: Minimum datetime (default: 2020-01-01)
        max_value: Maximum datetime (default: now + 1 year)

    Returns:
        Datetime with UTC timezone

    Example:
        >>> from hypothesis import given
        >>> @given(timestamp=datetime_strategy())
        ... def test_with_datetime(timestamp):
        ...     assert timestamp.tzinfo is not None
    """
    now = datetime.now(UTC)

    if min_value is None:
        min_value = datetime(2020, 1, 1)
    if max_value is None:
        max_value = (now + timedelta(days=365)).replace(tzinfo=None)

    # Ensure min_value and max_value are naive (no timezone)
    # Hypothesis will apply the timezone from timezones parameter
    if min_value.tzinfo is not None:
        min_value = min_value.replace(tzinfo=None)
    if max_value.tzinfo is not None:
        max_value = max_value.replace(tzinfo=None)

    # Use timezones parameter to force timezone-aware datetimes
    # min/max values must be naive when using timezones parameter
    dt = draw(
        st.datetimes(
            min_value=min_value,
            max_value=max_value,
            timezones=st.just(UTC),  # Force UTC timezone
        )
    )

    return dt


# ============================================================================
# Domain Model Strategies
# ============================================================================


@st.composite
def user_strategy(
    draw: st.DrawFn,
    *,
    is_active: bool | None = None,
    is_deleted: bool = False,
) -> User:
    """Generate valid User instances.

    This strategy generates realistic User objects with all required fields.

    Args:
        draw: Hypothesis draw function
        is_active: Force active status (None = random)
        is_deleted: Generate deleted users

    Returns:
        Valid User instance

    Example:
        >>> from hypothesis import given
        >>> @given(user=user_strategy())
        ... def test_user_invariants(user):
        ...     # Test runs with 100+ different users
        ...     assert user.email is not None
        ...     assert "@" in user.email
        ...     assert len(user.username) >= 3

        >>> @given(user=user_strategy(is_active=True))
        ... def test_active_users(user):
        ...     assert user.is_active is True

        >>> @given(user=user_strategy(is_deleted=True))
        ... def test_deleted_users(user):
        ...     assert user.is_deleted is True
    """
    now = datetime.now(UTC)

    # Generate created_at first
    created_at = draw(datetime_strategy(max_value=now))

    # Generate updated_at >= created_at (respects invariant)
    updated_at = draw(datetime_strategy(min_value=created_at, max_value=now))

    # Generate deleted_at >= updated_at if deleted (realistic deletion timeline)
    deleted_at = None
    if is_deleted:
        deleted_at = draw(datetime_strategy(min_value=updated_at, max_value=now))

    user = User(
        id=draw(uuid7_strategy()),
        email=draw(email_strategy()),
        username=draw(username_strategy()),
        full_name=draw(
            st.one_of(
                st.none(),
                st.text(min_size=1, max_size=100),
            )
        ),
        is_active=is_active if is_active is not None else draw(st.booleans()),
        tenant_id=draw(uuid7_strategy()),
        created_at=created_at,
        updated_at=updated_at,
        deleted_at=deleted_at,
    )

    return user


@st.composite
def user_list_strategy(
    draw: st.DrawFn,
    min_size: int = 0,
    max_size: int = 10,
    **kwargs: st.SearchStrategy,
) -> list[User]:
    """Generate lists of User instances.

    Args:
        draw: Hypothesis draw function
        min_size: Minimum list size
        max_size: Maximum list size
        **kwargs: Passed to user_strategy

    Returns:
        List of User instances

    Example:
        >>> from hypothesis import given
        >>> @given(users=user_list_strategy(min_size=1, max_size=5))
        ... def test_user_batch_operations(users):
        ...     assert 1 <= len(users) <= 5
        ...     assert all(isinstance(u, User) for u in users)
    """
    return draw(
        st.lists(
            user_strategy(**kwargs),
            min_size=min_size,
            max_size=max_size,
        )
    )


# ============================================================================
# API Request Strategies
# ============================================================================


@st.composite
def create_user_request_strategy(draw: st.DrawFn) -> dict:
    """Generate valid user creation requests.

    Returns:
        Dictionary with user creation data

    Example:
        >>> from hypothesis import given
        >>> @given(request_data=create_user_request_strategy())
        ... def test_create_user_endpoint(client, request_data):
        ...     response = client.post("/api/v1/users", json=request_data)
        ...     # Test with 100+ different requests
    """
    return {
        "email": draw(email_strategy()),
        "username": draw(username_strategy()),
        "full_name": draw(
            st.one_of(
                st.none(),
                st.text(min_size=1, max_size=100),
            )
        ),
    }


# ============================================================================
# Pagination Strategies
# ============================================================================


@st.composite
def pagination_params_strategy(draw: st.DrawFn) -> dict:
    """Generate valid pagination parameters.

    Returns:
        Dictionary with skip and limit

    Example:
        >>> from hypothesis import given
        >>> @given(params=pagination_params_strategy())
        ... def test_pagination(params):
        ...     assert 0 <= params["skip"] <= 10000
        ...     assert 1 <= params["limit"] <= 100
    """
    return {
        "skip": draw(st.integers(min_value=0, max_value=10000)),
        "limit": draw(st.integers(min_value=1, max_value=100)),
    }


# ============================================================================
# Pagination Strategies
# ============================================================================


@st.composite
def cursor_strategy(draw: st.DrawFn, with_sort_value: bool = True) -> dict:
    """Generate cursor data for pagination testing.

    Args:
        draw: Hypothesis draw function
        with_sort_value: Include sort_value in cursor

    Returns:
        Dictionary with cursor data (value and optionally sort_value)

    Example:
        >>> from hypothesis import given
        >>> @given(cursor_data=cursor_strategy())
        ... def test_cursor_encoding(cursor_data):
        ...     # Test runs with 100+ different cursors
        ...     assert "value" in cursor_data

    Note:
        Text sizes are limited to account for:
        - MAX_DECODED_SIZE = 768 bytes in pagination.py
        - Unicode characters can be up to 4 bytes each
        - JSON overhead (~35 bytes for structure: {"value":"", "sort_value":""})
        - With two fields: (768 - 35) / 2 / 4 = ~90 chars per field max
        - Using 80 chars to be safe and allow for both fields with 4-byte chars
    """
    # Value can be string or UUID
    value = draw(
        st.one_of(
            st.text(min_size=1, max_size=80),
            uuid7_strategy().map(str),
        )
    )

    cursor_data = {"value": value}

    if with_sort_value:
        # Sort value can be string, int, float, or datetime
        sort_value = draw(
            st.one_of(
                st.text(min_size=1, max_size=80),
                st.integers(min_value=0, max_value=10**10),
                st.floats(min_value=0.0, max_value=10**10, allow_nan=False, allow_infinity=False),
                datetime_strategy().map(lambda dt: dt.isoformat()),
            )
        )
        cursor_data["sort_value"] = sort_value

    return cursor_data


@st.composite
def pagination_limit_strategy(draw: st.DrawFn) -> int:
    """Generate valid pagination limits (1-100).

    Args:
        draw: Hypothesis draw function

    Returns:
        Valid pagination limit

    Example:
        >>> from hypothesis import given
        >>> @given(limit=pagination_limit_strategy())
        ... def test_pagination_limit(limit):
        ...     assert 1 <= limit <= 100
    """
    return draw(st.integers(min_value=1, max_value=100))


# ============================================================================
# Exception Strategies
# ============================================================================


@st.composite
def error_message_strategy(draw: st.DrawFn) -> str:
    """Generate realistic error messages for exception testing.

    Args:
        draw: Hypothesis draw function

    Returns:
        Error message string

    Example:
        >>> from hypothesis import given
        >>> @given(message=error_message_strategy())
        ... def test_exception_with_message(message):
        ...     exception = DomainException(message)
        ...     assert exception.message == message
    """
    # Generate realistic error message patterns
    patterns = [
        st.just("Entity not found"),
        st.just("Validation failed"),
        st.just("Business rule violated"),
        st.text(
            min_size=10,
            max_size=200,
            alphabet=st.characters(
                whitelist_categories=(
                    "L",
                    "N",
                    "P",
                    "Z",
                ),  # Letters, numbers, punctuation, separators
            ),
        ),
    ]
    return draw(st.one_of(*patterns))


@st.composite
def error_details_strategy(draw: st.DrawFn) -> dict[str, any] | list[any] | None:
    """Generate error details for exception testing.

    Args:
        draw: Hypothesis draw function

    Returns:
        Error details (dict, list, or None)

    Example:
        >>> from hypothesis import given
        >>> @given(details=error_details_strategy())
        ... def test_exception_with_details(details):
        ...     exception = DomainException("Error", details=details)
        ...     assert exception.details == details
    """
    return draw(
        st.one_of(
            st.none(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.one_of(st.text(), st.integers(), st.booleans()),
                max_size=5,
            ),
            st.lists(st.text(min_size=1, max_size=50), max_size=5),
        )
    )


# ============================================================================
# Configuration Strategies
# ============================================================================


@st.composite
def cors_origin_strategy(draw: st.DrawFn, require_https: bool = False) -> str:
    """Generate valid CORS origin URLs.

    Args:
        draw: Hypothesis draw function
        require_https: Require HTTPS protocol

    Returns:
        Valid CORS origin URL

    Example:
        >>> from hypothesis import given
        >>> @given(origin=cors_origin_strategy())
        ... def test_cors_validation(origin):
        ...     assert origin.startswith("http://") or origin.startswith("https://")
    """
    protocol = "https" if require_https else draw(st.sampled_from(["http", "https"]))

    # Generate domain (localhost or example domains)
    domain = draw(
        st.one_of(
            st.just("localhost"),
            st.just("127.0.0.1"),
            st.sampled_from(["example.com", "test.com", "app.example.org"]),
        )
    )

    # Optionally add port
    has_port = draw(st.booleans())
    port = f":{draw(st.integers(min_value=3000, max_value=9999))}" if has_port else ""

    return f"{protocol}://{domain}{port}"


@st.composite
def environment_name_strategy(draw: st.DrawFn) -> str:
    """Generate environment names (development, staging, production, etc.).

    Args:
        draw: Hypothesis draw function

    Returns:
        Environment name string

    Example:
        >>> from hypothesis import given
        >>> @given(env=environment_name_strategy())
        ... def test_environment_settings(env):
        ...     assert env in ["development", "staging", "production", "testing", "local"]
    """
    return draw(
        st.sampled_from(
            [
                "development",
                "staging",
                "production",
                "testing",
                "local",
            ]
        )
    )


@st.composite
def api_key_strategy(draw: st.DrawFn, secure: bool = True) -> str:
    """Generate API keys for testing.

    Args:
        draw: Hypothesis draw function
        secure: Generate secure key (True) or insecure dev key (False)

    Returns:
        API key string

    Example:
        >>> from hypothesis import given
        >>> @given(key=api_key_strategy(secure=True))
        ... def test_secure_api_key(key):
        ...     assert len(key) >= 32
    """
    if secure:
        # Generate secure-looking API key (32-64 chars of hex)
        length = draw(st.integers(min_value=32, max_value=64))
        return draw(
            st.text(
                alphabet="0123456789abcdef",
                min_size=length,
                max_size=length,
            )
        )
    # Generate insecure dev key
    return draw(
        st.sampled_from(
            [
                "dev-api-key-UNSAFE",
                "dev-email-api-key-UNSAFE",
                "test-key",
                "development-key",
            ]
        )
    )


# ============================================================================
# Schema Validation Strategies
# ============================================================================


@st.composite
def full_name_with_control_chars_strategy(draw: st.DrawFn) -> str:
    """Generate full names with control characters for sanitization testing.

    Args:
        draw: Hypothesis draw function

    Returns:
        String with control characters (ASCII < 32)

    Example:
        >>> from hypothesis import given
        >>> @given(name=full_name_with_control_chars_strategy())
        ... def test_control_char_sanitization(name):
        ...     # Test that control chars are stripped
        ...     assert any(ord(c) < 32 for c in name)
    """
    # Generate text with control characters mixed in
    normal_text = draw(
        st.text(
            min_size=5,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("L", "Zs"),  # Letters and spaces
            ),
        )
    )

    # Insert control characters (ASCII 0-31)
    control_chars = "".join(chr(i) for i in range(32))

    # Mix control chars into the text
    parts = list(normal_text)
    num_control_chars = draw(st.integers(min_value=1, max_value=5))

    for _ in range(num_control_chars):
        if parts:
            position = draw(st.integers(min_value=0, max_value=len(parts)))
            control_char = draw(st.sampled_from(control_chars))
            parts.insert(position, control_char)

    return "".join(parts)


@st.composite
def invalid_username_strategy(draw: st.DrawFn) -> str:
    """Generate invalid usernames for validation testing.

    Args:
        draw: Hypothesis draw function

    Returns:
        Invalid username string

    Example:
        >>> from hypothesis import given
        >>> @given(username=invalid_username_strategy())
        ... def test_username_validation(username):
        ...     # Should raise ValidationError
        ...     with pytest.raises(ValidationError):
        ...         UserCreate(email="test@example.com", username=username)
    """
    return draw(
        st.one_of(
            # Too short (< 3 chars)
            st.text(
                min_size=0, max_size=2, alphabet=st.characters(whitelist_categories=("L", "Nd"))
            ),
            # Contains invalid characters
            st.text(min_size=3, max_size=20, alphabet="!@#$%^&*()+=[]{}|;:,.<>?/\\"),
            # Contains spaces
            st.from_regex(r"[a-zA-Z0-9_-]+ [a-zA-Z0-9_-]+", fullmatch=True),
            # Contains unicode characters outside allowed range
            st.text(min_size=3, max_size=20, alphabet="日本語中文한국어"),
        )
    )


@st.composite
def invalid_email_strategy(draw: st.DrawFn) -> str:
    """Generate invalid email addresses for validation testing.

    Args:
        draw: Hypothesis draw function

    Returns:
        Invalid email string

    Example:
        >>> from hypothesis import given
        >>> @given(email=invalid_email_strategy())
        ... def test_email_validation(email):
        ...     # Should raise ValidationError
        ...     with pytest.raises(ValidationError):
        ...         UserCreate(email=email, username="testuser")
    """
    return draw(
        st.one_of(
            # No @ symbol
            st.text(
                min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "Nd"))
            ),
            # Multiple @ symbols
            st.from_regex(r"[a-z]+@[a-z]+@[a-z]+\.[a-z]+", fullmatch=True),
            # Missing domain
            st.from_regex(r"[a-z]+@", fullmatch=True),
            # Missing local part
            st.from_regex(r"@[a-z]+\.[a-z]+", fullmatch=True),
            # Invalid characters
            st.just("test user@example.com"),  # Space
            st.just("test..user@example.com"),  # Double dot
        )
    )


# ============================================================================
# Configuration
# ============================================================================


# Configure Hypothesis settings for faster tests during development
# In CI, use default settings for thorough testing
#
# from hypothesis import settings, Phase  # noqa: ERA001
# settings.register_profile("dev", max_examples=10, phases=[Phase.generate])  # noqa: ERA001
# settings.register_profile("ci", max_examples=100)  # noqa: ERA001
