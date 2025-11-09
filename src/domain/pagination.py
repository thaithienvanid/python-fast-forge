"""Cursor-based pagination for unlimited data loads."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# Security constants for cursor validation
MAX_CURSOR_LENGTH = 1024  # Prevent DoS via extremely large cursors
MAX_DECODED_SIZE = 768  # Prevent memory exhaustion from decoded data
ALLOWED_FIELDS = {"value", "sort_value"}  # Whitelist for injection prevention


@dataclass
class Cursor:
    """Cursor for pagination.

    Encodes the position in a dataset using a composite key (typically timestamp + id).
    """

    value: str | UUID | int
    """Primary cursor value (usually ID)"""

    sort_value: Any | None = None
    """Secondary sort value (e.g., created_at timestamp)"""

    def encode(self) -> str:
        """Encode cursor to base64 string.

        Returns:
            Base64-encoded cursor string
        """
        data: dict[str, str | int | float | bool] = {"value": str(self.value)}
        if self.sort_value is not None:
            # Handle different types
            if isinstance(self.sort_value, (str, int, float, bool)):
                data["sort_value"] = self.sort_value
            else:
                data["sort_value"] = str(self.sort_value)

        json_str = json.dumps(data, sort_keys=True)
        return base64.urlsafe_b64encode(json_str.encode()).decode()

    @classmethod
    def decode(cls, encoded: str) -> Cursor:
        """Decode cursor from base64 string with validation.

        Args:
            encoded: Base64-encoded cursor string

        Returns:
            Cursor object

        Raises:
            ValueError: If cursor is invalid or malicious

        Security:
            - Validates cursor length to prevent DoS
            - Validates base64 format
            - Whitelists allowed fields to prevent injection
            - Limits decoded size to prevent memory exhaustion
        """
        if len(encoded) > MAX_CURSOR_LENGTH:
            raise ValueError(f"Cursor too large ({len(encoded)} bytes, max {MAX_CURSOR_LENGTH})")

        try:
            # Validate and decode base64
            # validate=True ensures proper padding and format
            json_bytes = base64.urlsafe_b64decode(encoded.encode())

            if len(json_bytes) > MAX_DECODED_SIZE:
                raise ValueError(
                    f"Decoded cursor too large ({len(json_bytes)} bytes, max {MAX_DECODED_SIZE})"
                )

            json_str = json_bytes.decode("utf-8")
            data = json.loads(json_str)

            # Whitelist allowed fields to prevent injection attacks
            if not isinstance(data, dict):
                raise ValueError("Cursor must be a JSON object")

            if not set(data.keys()).issubset(ALLOWED_FIELDS):
                invalid_fields = set(data.keys()) - ALLOWED_FIELDS
                raise ValueError(f"Invalid cursor fields: {invalid_fields}")

            # Validate required field
            if "value" not in data:
                raise ValueError("Cursor missing required 'value' field")

            # Type validation for values
            value = data["value"]
            if not isinstance(value, (str, int)):
                raise ValueError(f"Invalid value type: {type(value).__name__}")

            sort_value = data.get("sort_value")
            if sort_value is not None and not isinstance(
                sort_value, (str, int, float, bool, type(None))
            ):
                raise ValueError(f"Invalid sort_value type: {type(sort_value).__name__}")

            return cls(value=value, sort_value=sort_value)

        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid cursor format: {e}") from e
        except Exception as e:
            # Catch any other unexpected errors
            raise ValueError(f"Failed to decode cursor: {e}") from e


@dataclass
class CursorPage[T]:
    """Page of results with cursor-based pagination.

    Attributes:
        items: List of items in this page
        has_next: Whether there are more items after this page
        next_cursor: Cursor for fetching the next page (None if no more pages)
    """

    items: list[T]
    has_next: bool
    next_cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        return {
            "items": [
                item.model_dump() if isinstance(item, BaseModel) else item for item in self.items
            ],
            "has_next": self.has_next,
            "next_cursor": self.next_cursor,
        }


class CursorPaginationParams(BaseModel):
    """Query parameters for cursor-based pagination.

    Example:
        ?cursor=eyJ2YWx1ZSI6IjEyMyIsInNvcnRfdmFsdWUiOiIyMDI0LTAxLTAxIn0&limit=50
    """

    cursor: str | None = Field(
        default=None,
        description="Cursor for pagination (base64-encoded position)",
        examples=["eyJ2YWx1ZSI6IjEyMyJ9"],
    )

    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of items to return (1-100)",
        examples=[50],
    )

    def get_cursor(self) -> Cursor | None:
        """Decode cursor if provided.

        Returns:
            Cursor object or None

        Raises:
            ValueError: If cursor is invalid
        """
        if self.cursor:
            return Cursor.decode(self.cursor)
        return None


def create_cursor_page[T](
    items: list[T],
    limit: int,
    cursor_fn: Callable[[T], Cursor],
) -> CursorPage[T]:
    """Create a cursor page from items.

    This helper function implements the standard cursor pagination pattern:
    1. Fetch limit + 1 items
    2. If we got more than limit, there's a next page
    3. Create cursor from the last item

    Args:
        items: List of items (should be limit + 1 items)
        limit: Requested limit
        cursor_fn: Function to extract cursor from an item

    Returns:
        CursorPage with correct pagination metadata

    Example:
        >>> users = await repository.list_with_cursor(cursor, limit=50)
        >>> page = create_cursor_page(
        ...     users, limit=50, cursor_fn=lambda u: Cursor(value=u.id, sort_value=u.created_at)
        ... )
    """
    has_next = len(items) > limit
    page_items = items[:limit] if has_next else items

    next_cursor = None
    if has_next and page_items:
        last_item = page_items[-1]
        cursor = cursor_fn(last_item)
        next_cursor = cursor.encode()

    return CursorPage(
        items=page_items,
        has_next=has_next,
        next_cursor=next_cursor,
    )
