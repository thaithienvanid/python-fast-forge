"""Unit tests for cursor-based pagination."""

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, ValidationError
from uuid_extension import uuid7

from src.domain.pagination import (
    Cursor,
    CursorPage,
    CursorPaginationParams,
    create_cursor_page,
)
from tests.strategies import (
    cursor_strategy,
    pagination_limit_strategy,
    uuid7_strategy,
)


# ============================================================================
# Test Models
# ============================================================================


class PaginationItem(BaseModel):
    """Sample item for pagination tests."""

    id: UUID
    name: str
    created_at: datetime


# ============================================================================
# Cursor Encoding Tests
# ============================================================================


class TestCursorEncoding:
    """Test Cursor encoding with various data types."""

    def test_encode_with_uuid_value(self) -> None:
        """Test encoding cursor with UUID value."""
        # Arrange
        item_id = uuid7()
        cursor = Cursor(value=item_id)

        # Act
        encoded = cursor.encode()

        # Assert
        assert isinstance(encoded, str)
        decoded_bytes = base64.urlsafe_b64decode(encoded.encode())
        data = json.loads(decoded_bytes.decode())
        assert data["value"] == str(item_id)
        assert "sort_value" not in data

    def test_encode_with_string_value(self) -> None:
        """Test encoding cursor with string value."""
        # Arrange
        cursor = Cursor(value="user-123")

        # Act
        encoded = cursor.encode()

        # Assert
        decoded_bytes = base64.urlsafe_b64decode(encoded.encode())
        data = json.loads(decoded_bytes.decode())
        assert data["value"] == "user-123"

    def test_encode_with_integer_value(self) -> None:
        """Test encoding cursor with integer value (converted to string)."""
        # Arrange
        cursor = Cursor(value=12345)

        # Act
        encoded = cursor.encode()

        # Assert
        decoded_bytes = base64.urlsafe_b64decode(encoded.encode())
        data = json.loads(decoded_bytes.decode())
        assert data["value"] == "12345"  # Converted to string

    @pytest.mark.parametrize(
        ("sort_value", "expected_type"),
        [
            ("2025-01-01T00:00:00Z", str),
            (1234567890, int),
            (123.456, float),
        ],
    )
    def test_encode_with_various_sort_values(self, sort_value, expected_type) -> None:
        """Test encoding with different sort value types."""
        # Arrange
        cursor = Cursor(value=uuid7(), sort_value=sort_value)

        # Act
        encoded = cursor.encode()

        # Assert
        decoded_bytes = base64.urlsafe_b64decode(encoded.encode())
        data = json.loads(decoded_bytes.decode())
        assert "sort_value" in data
        assert isinstance(data["sort_value"], expected_type)
        assert data["sort_value"] == sort_value

    def test_encode_with_datetime_sort_value(self) -> None:
        """Test encoding with datetime sort value (converted to ISO string)."""
        # Arrange
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        cursor = Cursor(value="id-123", sort_value=dt)

        # Act
        encoded = cursor.encode()

        # Assert
        decoded_bytes = base64.urlsafe_b64decode(encoded.encode())
        data = json.loads(decoded_bytes.decode())
        assert isinstance(data["sort_value"], str)
        assert "2025-01-01" in data["sort_value"]

    def test_encode_is_deterministic(self) -> None:
        """Test that encoding the same cursor produces identical results."""
        # Arrange
        cursor1 = Cursor(value="id-123", sort_value=456)
        cursor2 = Cursor(value="id-123", sort_value=456)

        # Act
        encoded1 = cursor1.encode()
        encoded2 = cursor2.encode()

        # Assert
        assert encoded1 == encoded2


# ============================================================================
# Cursor Decoding Tests
# ============================================================================


class TestCursorDecoding:
    """Test Cursor decoding and error handling."""

    def test_decode_simple_cursor(self) -> None:
        """Test decoding cursor without sort value."""
        # Arrange
        data = {"value": "user-123"}
        json_str = json.dumps(data, sort_keys=True)
        encoded = base64.urlsafe_b64encode(json_str.encode()).decode()

        # Act
        cursor = Cursor.decode(encoded)

        # Assert
        assert cursor.value == "user-123"
        assert cursor.sort_value is None

    def test_decode_cursor_with_sort_value(self) -> None:
        """Test decoding cursor with sort value."""
        # Arrange
        data = {"value": "user-456", "sort_value": "2025-01-01T00:00:00Z"}
        json_str = json.dumps(data, sort_keys=True)
        encoded = base64.urlsafe_b64encode(json_str.encode()).decode()

        # Act
        cursor = Cursor.decode(encoded)

        # Assert
        assert cursor.value == "user-456"
        assert cursor.sort_value == "2025-01-01T00:00:00Z"

    def test_decode_rejects_invalid_base64(self) -> None:
        """Test that invalid base64 raises ValueError."""
        # Arrange
        invalid_cursor = "not-valid-base64!!!"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid cursor"):
            Cursor.decode(invalid_cursor)

    def test_decode_rejects_invalid_json(self) -> None:
        """Test that invalid JSON raises ValueError."""
        # Arrange
        invalid_json = base64.urlsafe_b64encode(b"not json").decode()

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid cursor"):
            Cursor.decode(invalid_json)

    def test_decode_rejects_missing_value_field(self) -> None:
        """Test that cursor missing 'value' field raises ValueError."""
        # Arrange
        data = {"sort_value": "123"}  # Missing 'value' field
        json_str = json.dumps(data)
        encoded = base64.urlsafe_b64encode(json_str.encode()).decode()

        # Act & Assert
        with pytest.raises(
            ValueError,
            match="(Invalid cursor|Cursor missing required 'value' field|Failed to decode cursor)",
        ):
            Cursor.decode(encoded)

    def test_encode_decode_roundtrip(self) -> None:
        """Test that encoding and decoding produces same cursor."""
        # Arrange
        original = Cursor(value=str(uuid7()), sort_value=1234567890)

        # Act
        encoded = original.encode()
        decoded = Cursor.decode(encoded)

        # Assert
        assert decoded.value == original.value
        assert decoded.sort_value == original.sort_value

    def test_encode_decode_roundtrip_no_sort(self) -> None:
        """Test roundtrip without sort value."""
        # Arrange
        original = Cursor(value="test-id-123")

        # Act
        encoded = original.encode()
        decoded = Cursor.decode(encoded)

        # Assert
        assert decoded.value == original.value
        assert decoded.sort_value is None


# ============================================================================
# CursorPage Tests
# ============================================================================


class TestCursorPage:
    """Test CursorPage creation and serialization."""

    def test_page_creation_with_next(self) -> None:
        """Test creating CursorPage with next page indicator."""
        # Arrange
        items = [
            PaginationItem(id=uuid7(), name=f"Item {i}", created_at=datetime.now(UTC))
            for i in range(3)
        ]

        # Act
        page = CursorPage(
            items=items,
            has_next=True,
            next_cursor="abc123",
        )

        # Assert
        assert len(page.items) == 3
        assert page.has_next is True
        assert page.next_cursor == "abc123"

    def test_page_creation_without_next(self) -> None:
        """Test creating CursorPage without next page."""
        # Arrange
        items = [PaginationItem(id=uuid7(), name="Item 1", created_at=datetime.now(UTC))]

        # Act
        page = CursorPage(
            items=items,
            has_next=False,
            next_cursor=None,
        )

        # Assert
        assert len(page.items) == 1
        assert page.has_next is False
        assert page.next_cursor is None

    def test_page_creation_with_empty_results(self) -> None:
        """Test creating CursorPage with no items."""
        # Arrange & Act
        page = CursorPage[PaginationItem](
            items=[],
            has_next=False,
            next_cursor=None,
        )

        # Assert
        assert len(page.items) == 0
        assert page.has_next is False
        assert page.next_cursor is None

    def test_page_to_dict_serialization(self) -> None:
        """Test CursorPage serialization to dictionary."""
        # Arrange
        items = [
            PaginationItem(id=uuid7(), name="Item 1", created_at=datetime(2025, 1, 1, tzinfo=UTC)),
            PaginationItem(id=uuid7(), name="Item 2", created_at=datetime(2025, 1, 2, tzinfo=UTC)),
        ]
        page = CursorPage(
            items=items,
            has_next=True,
            next_cursor="next_cursor_value",
        )

        # Act
        result = page.to_dict()

        # Assert
        assert "items" in result
        assert len(result["items"]) == 2
        assert result["has_next"] is True
        assert result["next_cursor"] == "next_cursor_value"
        # Check items are serialized as dicts
        assert isinstance(result["items"][0], dict)
        assert result["items"][0]["name"] == "Item 1"

    def test_page_to_dict_with_non_pydantic_items(self) -> None:
        """Test serialization with non-Pydantic items (plain dicts)."""
        # Arrange
        items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        page = CursorPage(
            items=items,
            has_next=False,
            next_cursor=None,
        )

        # Act
        result = page.to_dict()

        # Assert
        assert result["items"] == items
        assert result["has_next"] is False


# ============================================================================
# CursorPaginationParams Tests
# ============================================================================


class TestCursorPaginationParams:
    """Test pagination parameter validation and cursor retrieval."""

    def test_params_use_default_values(self) -> None:
        """Test that CursorPaginationParams uses correct defaults."""
        # Arrange & Act
        params = CursorPaginationParams()

        # Assert
        assert params.cursor is None
        assert params.limit == 50

    def test_params_accept_custom_values(self) -> None:
        """Test creating params with custom values."""
        # Arrange & Act
        params = CursorPaginationParams(cursor="abc123", limit=25)

        # Assert
        assert params.cursor == "abc123"
        assert params.limit == 25

    @pytest.mark.parametrize(
        ("invalid_limit", "error_pattern"),
        [
            (0, "greater_than_equal"),
            (-1, "greater_than_equal"),
            (101, "less_than_equal"),
            (1000, "less_than_equal"),
        ],
    )
    def test_params_reject_invalid_limits(self, invalid_limit, error_pattern) -> None:
        """Test that limits outside 1-100 range are rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            CursorPaginationParams(limit=invalid_limit)

        errors = exc_info.value.errors()
        assert any(error_pattern in str(error) for error in errors)

    def test_get_cursor_returns_none_when_not_provided(self) -> None:
        """Test get_cursor returns None when no cursor in params."""
        # Arrange
        params = CursorPaginationParams()

        # Act
        cursor = params.get_cursor()

        # Assert
        assert cursor is None

    def test_get_cursor_decodes_valid_cursor(self) -> None:
        """Test get_cursor successfully decodes valid cursor string."""
        # Arrange
        original_cursor = Cursor(value="user-123", sort_value=456)
        encoded = original_cursor.encode()
        params = CursorPaginationParams(cursor=encoded)

        # Act
        decoded_cursor = params.get_cursor()

        # Assert
        assert decoded_cursor is not None
        assert decoded_cursor.value == "user-123"
        assert decoded_cursor.sort_value == 456

    def test_get_cursor_raises_error_for_invalid_cursor(self) -> None:
        """Test get_cursor raises ValueError for malformed cursor."""
        # Arrange
        params = CursorPaginationParams(cursor="invalid-cursor")

        # Act & Assert
        with pytest.raises(ValueError, match="(Invalid cursor|Failed to decode cursor)"):
            params.get_cursor()


# ============================================================================
# create_cursor_page Helper Tests
# ============================================================================


class TestCreateCursorPage:
    """Test create_cursor_page helper function."""

    def test_create_page_without_next_when_items_less_than_limit(self) -> None:
        """Test page creation when items < limit (no next page)."""
        # Arrange
        items = [
            PaginationItem(id=uuid7(), name="Item 1", created_at=datetime(2025, 1, 1, tzinfo=UTC)),
            PaginationItem(id=uuid7(), name="Item 2", created_at=datetime(2025, 1, 2, tzinfo=UTC)),
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=10,
            cursor_fn=lambda item: Cursor(value=item.id, sort_value=item.created_at),
        )

        # Assert
        assert len(page.items) == 2
        assert page.has_next is False
        assert page.next_cursor is None

    def test_create_page_with_next_when_items_exceed_limit(self) -> None:
        """Test page creation when items > limit (has next page)."""
        # Arrange - standard pattern: fetch limit + 1 to check for next page
        items = [
            PaginationItem(
                id=uuid7(), name=f"Item {i}", created_at=datetime(2025, 1, i + 1, tzinfo=UTC)
            )
            for i in range(11)
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=10,
            cursor_fn=lambda item: Cursor(value=item.id, sort_value=item.created_at),
        )

        # Assert
        assert len(page.items) == 10  # Only limit items returned
        assert page.has_next is True
        assert page.next_cursor is not None
        # Verify cursor is from last item in page
        decoded_cursor = Cursor.decode(page.next_cursor)
        assert str(decoded_cursor.value) == str(page.items[-1].id)

    def test_create_page_when_items_exactly_equal_limit(self) -> None:
        """Test page creation when items exactly equals limit."""
        # Arrange
        items = [
            PaginationItem(
                id=uuid7(), name=f"Item {i}", created_at=datetime(2025, 1, i + 1, tzinfo=UTC)
            )
            for i in range(10)
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=10,
            cursor_fn=lambda item: Cursor(value=item.id, sort_value=item.created_at),
        )

        # Assert
        assert len(page.items) == 10
        assert page.has_next is False
        assert page.next_cursor is None

    def test_create_page_with_empty_items(self) -> None:
        """Test page creation with no items."""
        # Arrange & Act
        page = create_cursor_page(
            items=[],
            limit=10,
            cursor_fn=lambda item: Cursor(value=item.id),
        )

        # Assert
        assert len(page.items) == 0
        assert page.has_next is False
        assert page.next_cursor is None

    def test_create_page_cursor_fn_uses_last_item(self) -> None:
        """Test that cursor_fn is called with the last item in page."""
        # Arrange
        test_id = uuid7()
        test_time = datetime(2025, 1, 15, tzinfo=UTC)
        items = [
            PaginationItem(id=uuid7(), name="Item 1", created_at=datetime(2025, 1, 1, tzinfo=UTC)),
            PaginationItem(id=test_id, name="Item 2", created_at=test_time),
            PaginationItem(id=uuid7(), name="Item 3", created_at=datetime(2025, 1, 3, tzinfo=UTC)),
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=2,
            cursor_fn=lambda item: Cursor(value=item.id, sort_value=item.created_at.isoformat()),
        )

        # Assert
        assert page.has_next is True
        assert page.next_cursor is not None
        # Cursor should be from second item (last in returned page)
        decoded = Cursor.decode(page.next_cursor)
        assert str(decoded.value) == str(test_id)
        assert decoded.sort_value == test_time.isoformat()

    def test_create_page_with_simple_cursor_no_sort_value(self) -> None:
        """Test creating page with cursor containing only ID (no sort value)."""
        # Arrange
        items = [
            PaginationItem(id=uuid7(), name=f"Item {i}", created_at=datetime.now(UTC))
            for i in range(6)
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=5,
            cursor_fn=lambda item: Cursor(value=item.id),  # No sort value
        )

        # Assert
        assert len(page.items) == 5
        assert page.has_next is True
        decoded = Cursor.decode(page.next_cursor)
        assert str(decoded.value) == str(page.items[-1].id)
        assert decoded.sort_value is None


# ============================================================================
# Integration Workflow Tests
# ============================================================================


class TestPaginationWorkflow:
    """Test complete pagination workflows across multiple pages."""

    def test_complete_pagination_workflow_three_pages(self) -> None:
        """Test realistic pagination workflow across multiple pages."""
        # Arrange - simulate 25 total items
        all_items = [
            PaginationItem(
                id=uuid7(), name=f"Item {i}", created_at=datetime(2025, 1, i + 1, tzinfo=UTC)
            )
            for i in range(25)
        ]

        # Act - Page 1: Get first 10 items (fetch 11 to check for next)
        page1_items = all_items[:11]
        page1 = create_cursor_page(
            items=page1_items,
            limit=10,
            cursor_fn=lambda item: Cursor(value=item.id, sort_value=item.created_at),
        )

        # Assert - Page 1
        assert len(page1.items) == 10
        assert page1.has_next is True
        assert page1.next_cursor is not None
        cursor_for_page2 = Cursor.decode(page1.next_cursor)
        assert cursor_for_page2.value == str(page1.items[-1].id)

        # Act - Page 2: Get next 10 items
        page2_items = all_items[10:21]
        page2 = create_cursor_page(
            items=page2_items,
            limit=10,
            cursor_fn=lambda item: Cursor(value=item.id, sort_value=item.created_at),
        )

        # Assert - Page 2
        assert len(page2.items) == 10
        assert page2.has_next is True

        # Act - Page 3: Get remaining items
        page3_items = all_items[20:25]  # Only 5 left
        page3 = create_cursor_page(
            items=page3_items,
            limit=10,
            cursor_fn=lambda item: Cursor(value=item.id, sort_value=item.created_at),
        )

        # Assert - Page 3 (final page)
        assert len(page3.items) == 5
        assert page3.has_next is False
        assert page3.next_cursor is None


# ============================================================================
# Property-Based Tests
# ============================================================================


class TestPaginationPropertyBased:
    """Property-based tests using Hypothesis to find edge cases."""

    @given(cursor_data=cursor_strategy())
    def test_cursor_encode_decode_always_roundtrips(self, cursor_data) -> None:
        """Property: Encoding then decoding produces original cursor.

        This test runs 100+ times with different cursor data.
        """
        # Arrange
        cursor = Cursor(value=cursor_data["value"], sort_value=cursor_data.get("sort_value"))

        # Act
        encoded = cursor.encode()
        decoded = Cursor.decode(encoded)

        # Assert
        assert str(decoded.value) == str(cursor.value)
        if cursor.sort_value is not None:
            assert decoded.sort_value == cursor.sort_value

    @given(limit=pagination_limit_strategy())
    def test_pagination_limit_always_valid(self, limit) -> None:
        """Property: Valid limits (1-100) always create valid params."""
        # Arrange & Act
        params = CursorPaginationParams(limit=limit)

        # Assert
        assert 1 <= params.limit <= 100
        assert params.limit == limit

    @given(
        num_items=st.integers(min_value=0, max_value=200),
        limit=pagination_limit_strategy(),
    )
    def test_create_cursor_page_has_next_logic(self, num_items, limit) -> None:
        """Property: has_next is True iff items > limit."""
        # Arrange
        items = [
            PaginationItem(id=uuid7(), name=f"Item {i}", created_at=datetime.now(UTC))
            for i in range(num_items)
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=limit,
            cursor_fn=lambda item: Cursor(value=item.id),
        )

        # Assert - Core pagination invariants
        if num_items > limit:
            assert page.has_next is True
            assert page.next_cursor is not None
            assert len(page.items) == limit
        else:
            assert page.has_next is False
            assert page.next_cursor is None
            assert len(page.items) == num_items

    @given(
        value=st.one_of(st.text(min_size=1, max_size=100), uuid7_strategy().map(str)),
    )
    def test_cursor_encode_produces_valid_base64(self, value) -> None:
        """Property: Encoded cursors are always valid base64."""
        # Arrange
        cursor = Cursor(value=value)

        # Act
        encoded = cursor.encode()

        # Assert
        # Should decode without error
        decoded_bytes = base64.urlsafe_b64decode(encoded.encode())
        assert decoded_bytes is not None
        # Should be valid JSON
        data = json.loads(decoded_bytes.decode())
        assert "value" in data


# ============================================================================
# Edge Cases
# ============================================================================


class TestPaginationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_cursor_with_very_long_string_value(self) -> None:
        """Test cursor with maximum length string value.

        Note: Limited to 300 chars to stay within MAX_DECODED_SIZE (768 bytes).
        With JSON overhead and potential Unicode multi-byte chars, this ensures
        the encoded cursor stays under the limit.
        """
        # Arrange - Use 300 chars (safe for Unicode up to 2 bytes per char)
        long_value = "a" * 300
        cursor = Cursor(value=long_value)

        # Act
        encoded = cursor.encode()
        decoded = Cursor.decode(encoded)

        # Assert
        assert decoded.value == long_value

    def test_cursor_with_unicode_values(self) -> None:
        """Test cursor with Unicode characters."""
        # Arrange
        unicode_value = "用户-123-🎉"
        cursor = Cursor(value=unicode_value)

        # Act
        encoded = cursor.encode()
        decoded = Cursor.decode(encoded)

        # Assert
        assert decoded.value == unicode_value

    def test_pagination_with_limit_one(self) -> None:
        """Test pagination with minimum limit (1 item per page)."""
        # Arrange
        items = [
            PaginationItem(id=uuid7(), name="Item 1", created_at=datetime.now(UTC)),
            PaginationItem(id=uuid7(), name="Item 2", created_at=datetime.now(UTC)),
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=1,
            cursor_fn=lambda item: Cursor(value=item.id),
        )

        # Assert
        assert len(page.items) == 1
        assert page.has_next is True

    def test_pagination_with_limit_one_hundred(self) -> None:
        """Test pagination with maximum limit (100 items per page)."""
        # Arrange
        items = [
            PaginationItem(id=uuid7(), name=f"Item {i}", created_at=datetime.now(UTC))
            for i in range(101)
        ]

        # Act
        page = create_cursor_page(
            items=items,
            limit=100,
            cursor_fn=lambda item: Cursor(value=item.id),
        )

        # Assert
        assert len(page.items) == 100
        assert page.has_next is True

    @pytest.mark.parametrize("limit", [1, 10, 50, 100])
    def test_pagination_params_valid_boundary_limits(self, limit) -> None:
        """Test pagination params accept all valid boundary values."""
        # Arrange & Act
        params = CursorPaginationParams(limit=limit)

        # Assert
        assert params.limit == limit
