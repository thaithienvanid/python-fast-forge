"""JSON serialization utilities with support for common Python types.

This module provides a custom JSON encoder that handles types not supported
by the standard json module (UUID, datetime, Decimal, etc.) without requiring
Pydantic models, keeping the cache layer flexible and framework-agnostic.
"""

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ExtendedJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles common Python types.

    Supports:
    - UUID objects → string
    - datetime/date/time → ISO format string
    - timedelta → total seconds (float)
    - Decimal → float
    - Enum → value
    - bytes → base64 string
    - Path → string
    - set/frozenset → list
    - Pydantic models → dict (via model_dump())
    - Other objects → attempt __dict__ or str()

    Example:
        >>> import json
        >>> from uuid_extension import uuid7
        >>> data = {"id": uuid7(), "created_at": datetime.now()}
        >>> json.dumps(data, cls=ExtendedJSONEncoder)
        '{"id": "018c5e9e-...", "created_at": "2024-01-15T10:30:00.123456"}'
    """

    def default(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format.

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable representation

        Raises:
            TypeError: If object cannot be serialized
        """
        # UUID → string
        if isinstance(obj, UUID):
            return str(obj)

        # datetime types → ISO format
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.isoformat()

        # timedelta → total seconds
        if isinstance(obj, timedelta):
            return obj.total_seconds()

        # Decimal → float (some precision loss, but JSON doesn't support Decimal)
        if isinstance(obj, Decimal):
            return float(obj)

        # Enum → value
        if isinstance(obj, Enum):
            return obj.value

        # bytes → base64 string
        if isinstance(obj, bytes):
            import base64

            return base64.b64encode(obj).decode("utf-8")

        # Path → string
        if isinstance(obj, Path):
            return str(obj)

        # set/frozenset → list
        if isinstance(obj, (set, frozenset)):
            return list(obj)

        # Pydantic models → dict
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="python")

        # Try __dict__ for custom objects
        if hasattr(obj, "__dict__"):
            return obj.__dict__

        # Last resort: convert to string
        # This will work for most objects but may not be reversible
        return str(obj)


def dumps(obj: Any, **kwargs: Any) -> str:
    """Serialize object to JSON string with extended type support.

    Args:
        obj: Object to serialize
        **kwargs: Additional arguments to pass to json.dumps()

    Returns:
        JSON string

    Example:
        >>> from uuid_extension import uuid7
        >>> dumps({"id": uuid7(), "count": Decimal("99.99")})
        '{"id": "018c5e9e-...", "count": 99.99}'
    """
    return json.dumps(obj, cls=ExtendedJSONEncoder, **kwargs)


def loads(s: str | bytes, **kwargs: Any) -> Any:
    """Deserialize JSON string to Python object.

    Note: Some type information is lost during serialization (e.g., UUID becomes
    string, Decimal becomes float). For full type preservation, consider using
    Pydantic models or custom deserialization logic.

    Args:
        s: JSON string or bytes to deserialize
        **kwargs: Additional arguments to pass to json.loads()

    Returns:
        Deserialized Python object

    Example:
        >>> data = loads('{"id": "018c5e9e-...", "count": 99.99}')
        >>> data
        {'id': '018c5e9e-...', 'count': 99.99}
    """
    return json.loads(s, **kwargs)


def dumps_bytes(obj: Any, **kwargs: Any) -> bytes:
    """Serialize object to JSON bytes with extended type support.

    Convenient for storing in Redis or other byte-oriented storage.

    Args:
        obj: Object to serialize
        **kwargs: Additional arguments to pass to json.dumps()

    Returns:
        JSON bytes

    Example:
        >>> dumps_bytes({"id": uuid7()})
        b'{"id": "018c5e9e-..."}'
    """
    return dumps(obj, **kwargs).encode("utf-8")
