"""Tests for JSON serialization utilities.

Test Organization:
- TestUUIDSerialization: UUID object serialization
- TestDateTimeSerialization: datetime, date, time types
- TestTimedeltaSerialization: timedelta handling
- TestDecimalSerialization: Decimal numeric type
- TestEnumSerialization: Enum value extraction
- TestBytesSerialization: bytes to base64 encoding
- TestPathSerialization: Path object to string
- TestSetSerialization: set and frozenset to list
- TestPydanticModelSerialization: Pydantic BaseModel
- TestCustomObjectSerialization: Objects with __dict__
- TestNestedStructureSerialization: Complex nested data
- TestDumpsBytesFunction: dumps_bytes() function
- TestLoadsFunction: loads() function
- TestSerializationKwargs: Kwargs passthrough
- TestSerializationEdgeCases: Edge cases and special values
"""

import base64
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from uuid_extension import uuid7

from src.utils.serialization import dumps, dumps_bytes, loads


# ============================================================================
# Test Fixtures and Models
# ============================================================================


class Status(Enum):
    """Test enum for status values."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class Priority(Enum):
    """Test enum with integer values."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class SampleModel(BaseModel):
    """Sample Pydantic model for testing."""

    id: UUID
    name: str


class NestedModel(BaseModel):
    """Nested Pydantic model for testing."""

    user_id: UUID
    status: str
    count: int


# ============================================================================
# Test UUID Serialization
# ============================================================================


class TestUUIDSerialization:
    """Test UUID object serialization."""

    def test_serializes_uuid7_to_string(self) -> None:
        """Test UUID7 serializes to string representation.

        Arrange: Create UUID7
        Act: Serialize to JSON and parse
        Assert: UUID becomes string
        """
        # Arrange
        test_uuid = uuid7()

        # Act
        result = dumps({"id": test_uuid})
        data = loads(result)

        # Assert
        assert data["id"] == str(test_uuid)
        assert isinstance(data["id"], str)

    def test_serializes_uuid_in_list(self) -> None:
        """Test UUID in list serializes correctly.

        Arrange: Create list of UUIDs
        Act: Serialize and parse
        Assert: All UUIDs become strings
        """
        # Arrange
        uuids = [uuid7(), uuid7(), uuid7()]

        # Act
        result = dumps({"ids": uuids})
        data = loads(result)

        # Assert
        assert len(data["ids"]) == 3
        assert all(isinstance(id_str, str) for id_str in data["ids"])
        assert data["ids"] == [str(u) for u in uuids]

    def test_serializes_uuid_as_dict_key(self) -> None:
        """Test UUID as dictionary value (keys must be strings).

        Arrange: Create dict with UUID value
        Act: Serialize and parse
        Assert: UUID value becomes string
        """
        # Arrange
        test_uuid = uuid7()
        data_in = {"user": {"id": test_uuid, "name": "Test"}}

        # Act
        result = dumps(data_in)
        data_out = loads(result)

        # Assert
        assert data_out["user"]["id"] == str(test_uuid)

    def test_preserves_uuid_format(self) -> None:
        """Test UUID format is preserved in string form.

        Arrange: Create UUID with known format
        Act: Serialize and parse
        Assert: String matches UUID's string representation
        """
        # Arrange
        test_uuid = uuid7()
        uuid_str = str(test_uuid)

        # Act
        result = dumps({"id": test_uuid})
        data = loads(result)

        # Assert
        assert data["id"] == uuid_str
        assert len(data["id"]) == 36  # Standard UUID string length
        assert data["id"].count("-") == 4  # UUID format has 4 hyphens


# ============================================================================
# Test DateTime Serialization
# ============================================================================


class TestDateTimeSerialization:
    """Test datetime, date, and time serialization."""

    def test_serializes_datetime_to_isoformat(self) -> None:
        """Test datetime serializes to ISO format string.

        Arrange: Create datetime
        Act: Serialize and parse
        Assert: Becomes ISO format string
        """
        # Arrange
        now = datetime(2024, 1, 15, 10, 30, 0)

        # Act
        result = dumps({"timestamp": now})
        data = loads(result)

        # Assert
        assert data["timestamp"] == "2024-01-15T10:30:00"

    def test_serializes_date_to_isoformat(self) -> None:
        """Test date serializes to ISO format string.

        Arrange: Create date
        Act: Serialize and parse
        Assert: Becomes YYYY-MM-DD string
        """
        # Arrange
        today = date(2024, 1, 15)

        # Act
        result = dumps({"date": today})
        data = loads(result)

        # Assert
        assert data["date"] == "2024-01-15"

    def test_serializes_time_to_isoformat(self) -> None:
        """Test time serializes to ISO format string.

        Arrange: Create time
        Act: Serialize and parse
        Assert: Becomes HH:MM:SS string
        """
        # Arrange
        t = time(10, 30, 0)

        # Act
        result = dumps({"time": t})
        data = loads(result)

        # Assert
        assert data["time"] == "10:30:00"

    def test_serializes_datetime_with_microseconds(self) -> None:
        """Test datetime with microseconds preserves precision.

        Arrange: Create datetime with microseconds
        Act: Serialize and parse
        Assert: Microseconds included in ISO format
        """
        # Arrange
        precise_time = datetime(2024, 1, 15, 10, 30, 0, 123456)

        # Act
        result = dumps({"timestamp": precise_time})
        data = loads(result)

        # Assert
        assert data["timestamp"] == "2024-01-15T10:30:00.123456"

    def test_serializes_time_with_microseconds(self) -> None:
        """Test time with microseconds preserves precision.

        Arrange: Create time with microseconds
        Act: Serialize and parse
        Assert: Microseconds included
        """
        # Arrange
        precise_time = time(10, 30, 0, 123456)

        # Act
        result = dumps({"time": precise_time})
        data = loads(result)

        # Assert
        assert data["time"] == "10:30:00.123456"

    def test_serializes_multiple_datetime_types(self) -> None:
        """Test mixing datetime, date, and time in one structure.

        Arrange: Create dict with all datetime types
        Act: Serialize and parse
        Assert: All convert to appropriate ISO formats
        """
        # Arrange
        data_in = {
            "datetime": datetime(2024, 1, 15, 10, 30, 0),
            "date": date(2024, 1, 15),
            "time": time(10, 30, 0),
        }

        # Act
        result = dumps(data_in)
        data_out = loads(result)

        # Assert
        assert data_out["datetime"] == "2024-01-15T10:30:00"
        assert data_out["date"] == "2024-01-15"
        assert data_out["time"] == "10:30:00"


# ============================================================================
# Test Timedelta Serialization
# ============================================================================


class TestTimedeltaSerialization:
    """Test timedelta serialization to total seconds."""

    def test_serializes_timedelta_to_seconds(self) -> None:
        """Test timedelta serializes to total seconds as float.

        Arrange: Create timedelta
        Act: Serialize and parse
        Assert: Becomes total seconds
        """
        # Arrange
        td = timedelta(hours=2, minutes=30)

        # Act
        result = dumps({"duration": td})
        data = loads(result)

        # Assert
        assert data["duration"] == 9000.0  # 2.5 hours = 9000 seconds

    def test_serializes_timedelta_days(self) -> None:
        """Test timedelta with days serializes correctly.

        Arrange: Create timedelta with days
        Act: Serialize and parse
        Assert: Total seconds includes days
        """
        # Arrange
        td = timedelta(days=1, hours=2)

        # Act
        result = dumps({"duration": td})
        data = loads(result)

        # Assert
        # 1 day (86400 seconds) + 2 hours (7200 seconds) = 93600
        assert data["duration"] == 93600.0

    def test_serializes_timedelta_with_microseconds(self) -> None:
        """Test timedelta with microseconds preserves precision.

        Arrange: Create timedelta with microseconds
        Act: Serialize and parse
        Assert: Microseconds included in total seconds
        """
        # Arrange
        td = timedelta(seconds=1, microseconds=500000)

        # Act
        result = dumps({"duration": td})
        data = loads(result)

        # Assert
        assert data["duration"] == 1.5  # 1.5 seconds

    def test_serializes_zero_timedelta(self) -> None:
        """Test zero timedelta serializes to 0.0.

        Arrange: Create zero timedelta
        Act: Serialize and parse
        Assert: Becomes 0.0
        """
        # Arrange
        td = timedelta(0)

        # Act
        result = dumps({"duration": td})
        data = loads(result)

        # Assert
        assert data["duration"] == 0.0

    def test_serializes_negative_timedelta(self) -> None:
        """Test negative timedelta serializes to negative seconds.

        Arrange: Create negative timedelta
        Act: Serialize and parse
        Assert: Negative total seconds
        """
        # Arrange
        td = timedelta(hours=-2)

        # Act
        result = dumps({"duration": td})
        data = loads(result)

        # Assert
        assert data["duration"] == -7200.0


# ============================================================================
# Test Decimal Serialization
# ============================================================================


class TestDecimalSerialization:
    """Test Decimal numeric type serialization."""

    def test_serializes_decimal_to_float(self) -> None:
        """Test Decimal serializes to float.

        Arrange: Create Decimal
        Act: Serialize and parse
        Assert: Becomes float
        """
        # Arrange
        price = Decimal("99.99")

        # Act
        result = dumps({"price": price})
        data = loads(result)

        # Assert
        assert data["price"] == 99.99
        assert isinstance(data["price"], float)

    def test_serializes_decimal_with_high_precision(self) -> None:
        """Test Decimal with high precision (note: some precision may be lost).

        Arrange: Create high-precision Decimal
        Act: Serialize and parse
        Assert: Converts to float (some precision loss acceptable)
        """
        # Arrange
        precise = Decimal("123.456789012345")

        # Act
        result = dumps({"value": precise})
        data = loads(result)

        # Assert
        assert isinstance(data["value"], float)
        # Note: float precision is lower than Decimal, so we use approx comparison
        assert abs(data["value"] - 123.456789012345) < 0.000000000001

    def test_serializes_decimal_zero(self) -> None:
        """Test Decimal zero serializes correctly.

        Arrange: Create Decimal zero
        Act: Serialize and parse
        Assert: Becomes 0.0
        """
        # Arrange
        zero = Decimal("0.0")

        # Act
        result = dumps({"value": zero})
        data = loads(result)

        # Assert
        assert data["value"] == 0.0

    def test_serializes_decimal_negative(self) -> None:
        """Test negative Decimal serializes correctly.

        Arrange: Create negative Decimal
        Act: Serialize and parse
        Assert: Negative float
        """
        # Arrange
        negative = Decimal("-42.50")

        # Act
        result = dumps({"value": negative})
        data = loads(result)

        # Assert
        assert data["value"] == -42.50

    def test_serializes_decimal_in_list(self) -> None:
        """Test Decimal values in list serialize correctly.

        Arrange: Create list of Decimals
        Act: Serialize and parse
        Assert: All become floats
        """
        # Arrange
        prices = [Decimal("10.99"), Decimal("20.50"), Decimal("5.25")]

        # Act
        result = dumps({"prices": prices})
        data = loads(result)

        # Assert
        assert data["prices"] == [10.99, 20.50, 5.25]


# ============================================================================
# Test Enum Serialization
# ============================================================================


class TestEnumSerialization:
    """Test Enum value extraction."""

    def test_serializes_enum_to_value(self) -> None:
        """Test Enum serializes to its value.

        Arrange: Create Enum with string value
        Act: Serialize and parse
        Assert: Becomes value string
        """
        # Arrange
        status = Status.ACTIVE

        # Act
        result = dumps({"status": status})
        data = loads(result)

        # Assert
        assert data["status"] == "active"

    def test_serializes_enum_with_integer_value(self) -> None:
        """Test Enum with integer value serializes correctly.

        Arrange: Create Enum with int value
        Act: Serialize and parse
        Assert: Becomes integer
        """
        # Arrange
        priority = Priority.HIGH

        # Act
        result = dumps({"priority": priority})
        data = loads(result)

        # Assert
        assert data["priority"] == 3

    def test_serializes_multiple_enum_values(self) -> None:
        """Test multiple Enum values in dict.

        Arrange: Create dict with multiple Enums
        Act: Serialize and parse
        Assert: All become their values
        """
        # Arrange
        data_in = {
            "status": Status.PENDING,
            "priority": Priority.MEDIUM,
        }

        # Act
        result = dumps(data_in)
        data_out = loads(result)

        # Assert
        assert data_out["status"] == "pending"
        assert data_out["priority"] == 2

    def test_serializes_enum_in_list(self) -> None:
        """Test Enum values in list serialize correctly.

        Arrange: Create list of Enums
        Act: Serialize and parse
        Assert: All become their values
        """
        # Arrange
        statuses = [Status.ACTIVE, Status.INACTIVE, Status.PENDING]

        # Act
        result = dumps({"statuses": statuses})
        data = loads(result)

        # Assert
        assert data["statuses"] == ["active", "inactive", "pending"]


# ============================================================================
# Test Bytes Serialization
# ============================================================================


class TestBytesSerialization:
    """Test bytes to base64 encoding."""

    def test_serializes_bytes_to_base64(self) -> None:
        """Test bytes serialize to base64 string.

        Arrange: Create bytes
        Act: Serialize and parse
        Assert: Becomes base64 encoded string
        """
        # Arrange
        data_bytes = b"hello world"

        # Act
        result = dumps({"data": data_bytes})
        data = loads(result)

        # Assert
        expected = base64.b64encode(data_bytes).decode("utf-8")
        assert data["data"] == expected

    def test_serializes_empty_bytes(self) -> None:
        """Test empty bytes serialize correctly.

        Arrange: Create empty bytes
        Act: Serialize and parse
        Assert: Becomes empty base64 string
        """
        # Arrange
        data_bytes = b""

        # Act
        result = dumps({"data": data_bytes})
        data = loads(result)

        # Assert
        expected = base64.b64encode(data_bytes).decode("utf-8")
        assert data["data"] == expected

    def test_serializes_bytes_with_binary_data(self) -> None:
        """Test bytes with binary data serialize correctly.

        Arrange: Create bytes with binary (non-ASCII) content
        Act: Serialize and parse
        Assert: Base64 encoding preserves data
        """
        # Arrange
        data_bytes = bytes([0, 1, 2, 255, 254, 253])

        # Act
        result = dumps({"data": data_bytes})
        data = loads(result)

        # Assert
        expected = base64.b64encode(data_bytes).decode("utf-8")
        assert data["data"] == expected
        # Verify it can be decoded back
        decoded = base64.b64decode(data["data"])
        assert decoded == data_bytes

    def test_serializes_bytes_in_list(self) -> None:
        """Test multiple bytes objects in list.

        Arrange: Create list of bytes
        Act: Serialize and parse
        Assert: All become base64 strings
        """
        # Arrange
        byte_list = [b"first", b"second", b"third"]

        # Act
        result = dumps({"items": byte_list})
        data = loads(result)

        # Assert
        expected = [base64.b64encode(b).decode("utf-8") for b in byte_list]
        assert data["items"] == expected


# ============================================================================
# Test Path Serialization
# ============================================================================


class TestPathSerialization:
    """Test Path object to string conversion."""

    def test_serializes_path_to_string(self) -> None:
        """Test Path serializes to string representation.

        Arrange: Create Path
        Act: Serialize and parse
        Assert: Becomes string
        """
        # Arrange
        path = Path("/home/user/test.txt")

        # Act
        result = dumps({"path": path})
        data = loads(result)

        # Assert
        assert data["path"] == "/home/user/test.txt"

    def test_serializes_relative_path(self) -> None:
        """Test relative Path serializes correctly.

        Arrange: Create relative Path
        Act: Serialize and parse
        Assert: Becomes relative path string
        """
        # Arrange
        path = Path("relative/path/to/file.txt")

        # Act
        result = dumps({"path": path})
        data = loads(result)

        # Assert
        assert data["path"] == "relative/path/to/file.txt"

    def test_serializes_windows_path(self) -> None:
        """Test Windows-style Path serializes correctly.

        Arrange: Create Windows Path
        Act: Serialize and parse
        Assert: Preserves Windows path format
        """
        # Arrange
        path = Path("C:/Users/test/file.txt")

        # Act
        result = dumps({"path": path})
        data = loads(result)

        # Assert
        # Path might normalize separators, but string form is preserved
        assert "file.txt" in data["path"]

    def test_serializes_multiple_paths(self) -> None:
        """Test multiple Path objects in dict.

        Arrange: Create dict with multiple Paths
        Act: Serialize and parse
        Assert: All become strings
        """
        # Arrange
        paths = {
            "input": Path("/input/file.txt"),
            "output": Path("/output/result.txt"),
        }

        # Act
        result = dumps(paths)
        data = loads(result)

        # Assert
        assert data["input"] == "/input/file.txt"
        assert data["output"] == "/output/result.txt"


# ============================================================================
# Test Set Serialization
# ============================================================================


class TestSetSerialization:
    """Test set and frozenset to list conversion."""

    def test_serializes_set_to_list(self) -> None:
        """Test set serializes to list.

        Arrange: Create set
        Act: Serialize and parse
        Assert: Becomes list with same elements
        """
        # Arrange
        tags = {"python", "fastapi", "api"}

        # Act
        result = dumps({"tags": tags})
        data = loads(result)

        # Assert
        assert isinstance(data["tags"], list)
        assert set(data["tags"]) == tags

    def test_serializes_frozenset_to_list(self) -> None:
        """Test frozenset serializes to list.

        Arrange: Create frozenset
        Act: Serialize and parse
        Assert: Becomes list
        """
        # Arrange
        tags = frozenset({"python", "fastapi"})

        # Act
        result = dumps({"tags": tags})
        data = loads(result)

        # Assert
        assert isinstance(data["tags"], list)
        assert set(data["tags"]) == set(tags)

    def test_serializes_empty_set(self) -> None:
        """Test empty set serializes to empty list.

        Arrange: Create empty set
        Act: Serialize and parse
        Assert: Becomes empty list
        """
        # Arrange
        empty = set()

        # Act
        result = dumps({"tags": empty})
        data = loads(result)

        # Assert
        assert data["tags"] == []

    def test_serializes_set_preserves_all_elements(self) -> None:
        """Test all set elements are preserved (order may vary).

        Arrange: Create set with known elements
        Act: Serialize and parse
        Assert: All elements present in list
        """
        # Arrange
        numbers = {1, 2, 3, 4, 5}

        # Act
        result = dumps({"numbers": numbers})
        data = loads(result)

        # Assert
        assert len(data["numbers"]) == 5
        assert set(data["numbers"]) == numbers

    def test_serializes_set_with_mixed_types(self) -> None:
        """Test set with different types serializes correctly.

        Arrange: Create set with strings and numbers
        Act: Serialize and parse
        Assert: All elements preserved
        """
        # Arrange
        # Note: JSON keys must be strings, so this tests values
        mixed = {1, 2, "three", "four"}

        # Act
        result = dumps({"items": mixed})
        data = loads(result)

        # Assert
        assert set(data["items"]) == mixed


# ============================================================================
# Test Pydantic Model Serialization
# ============================================================================


class TestPydanticModelSerialization:
    """Test Pydantic BaseModel serialization."""

    def test_serializes_pydantic_model_to_dict(self) -> None:
        """Test Pydantic model serializes via model_dump().

        Arrange: Create Pydantic model instance
        Act: Serialize and parse
        Assert: Becomes dict with model fields
        """
        # Arrange
        test_id = uuid7()
        model = SampleModel(id=test_id, name="Test")

        # Act
        result = dumps({"model": model})
        data = loads(result)

        # Assert
        assert data["model"]["id"] == str(test_id)
        assert data["model"]["name"] == "Test"

    def test_serializes_nested_pydantic_model(self) -> None:
        """Test nested Pydantic model serializes correctly.

        Arrange: Create Pydantic model with nested data
        Act: Serialize and parse
        Assert: All fields serialized correctly
        """
        # Arrange
        user_id = uuid7()
        nested = NestedModel(user_id=user_id, status="active", count=42)

        # Act
        result = dumps({"data": nested})
        data = loads(result)

        # Assert
        assert data["data"]["user_id"] == str(user_id)
        assert data["data"]["status"] == "active"
        assert data["data"]["count"] == 42

    def test_serializes_list_of_pydantic_models(self) -> None:
        """Test list of Pydantic models serializes correctly.

        Arrange: Create list of model instances
        Act: Serialize and parse
        Assert: Becomes list of dicts
        """
        # Arrange
        models = [
            SampleModel(id=uuid7(), name="First"),
            SampleModel(id=uuid7(), name="Second"),
        ]

        # Act
        result = dumps({"models": models})
        data = loads(result)

        # Assert
        assert len(data["models"]) == 2
        assert data["models"][0]["name"] == "First"
        assert data["models"][1]["name"] == "Second"


# ============================================================================
# Test Custom Object Serialization
# ============================================================================


class TestCustomObjectSerialization:
    """Test custom objects with __dict__ attribute."""

    def test_serializes_object_with_dict(self) -> None:
        """Test custom object with __dict__ serializes to dict.

        Arrange: Create custom object with attributes
        Act: Serialize and parse
        Assert: __dict__ becomes JSON object
        """

        # Arrange
        class CustomObject:
            def __init__(self):
                self.value = 42
                self.name = "test"

        obj = CustomObject()

        # Act
        result = dumps({"obj": obj})
        data = loads(result)

        # Assert
        assert data["obj"]["value"] == 42
        assert data["obj"]["name"] == "test"

    def test_serializes_object_without_dict_fallback_to_str(self) -> None:
        """Test object without __dict__ falls back to str().

        Arrange: Create object with __slots__ (no __dict__)
        Act: Serialize and parse
        Assert: Becomes string via __str__
        """

        # Arrange
        class MinimalObject:
            def __str__(self):
                return "minimal_object"

            __slots__ = ()  # No __dict__

        obj = MinimalObject()

        # Act
        result = dumps({"obj": obj})
        data = loads(result)

        # Assert
        assert data["obj"] == "minimal_object"

    def test_serializes_object_with_nested_attributes(self) -> None:
        """Test object with nested attributes serializes correctly.

        Arrange: Create object with nested data
        Act: Serialize and parse
        Assert: All nested attributes included
        """

        # Arrange
        class Container:
            def __init__(self):
                self.metadata = {"version": "1.0"}
                self.items = [1, 2, 3]

        obj = Container()

        # Act
        result = dumps({"container": obj})
        data = loads(result)

        # Assert
        assert data["container"]["metadata"]["version"] == "1.0"
        assert data["container"]["items"] == [1, 2, 3]


# ============================================================================
# Test Nested Structure Serialization
# ============================================================================


class TestNestedStructureSerialization:
    """Test serialization of complex nested structures."""

    def test_serializes_deeply_nested_structure(self) -> None:
        """Test deeply nested dict with mixed types.

        Arrange: Create complex nested structure
        Act: Serialize and parse
        Assert: All types converted correctly
        """
        # Arrange
        test_uuid = uuid7()
        now = datetime(2024, 1, 15, 10, 30, 0)
        data_in = {
            "user": {
                "id": test_uuid,
                "created_at": now,
                "balance": Decimal("100.50"),
                "status": Status.ACTIVE,
                "tags": {"python", "fastapi"},
            },
            "metadata": {"count": 42, "enabled": True},
        }

        # Act
        result = dumps(data_in)
        parsed = loads(result)

        # Assert
        assert parsed["user"]["id"] == str(test_uuid)
        assert parsed["user"]["created_at"] == "2024-01-15T10:30:00"
        assert parsed["user"]["balance"] == 100.50
        assert parsed["user"]["status"] == "active"
        assert isinstance(parsed["user"]["tags"], list)
        assert set(parsed["user"]["tags"]) == {"python", "fastapi"}

    def test_serializes_list_of_mixed_types(self) -> None:
        """Test list containing various types serializes correctly.

        Arrange: Create list with mixed types
        Act: Serialize and parse
        Assert: All elements converted appropriately
        """
        # Arrange
        mixed_list = [
            uuid7(),
            datetime(2024, 1, 15),
            Decimal("99.99"),
            Status.ACTIVE,
            {"nested": "dict"},
        ]

        # Act
        result = dumps({"items": mixed_list})
        data = loads(result)

        # Assert
        assert isinstance(data["items"][0], str)  # UUID
        assert isinstance(data["items"][1], str)  # datetime
        assert isinstance(data["items"][2], float)  # Decimal
        assert data["items"][3] == "active"  # Enum
        assert data["items"][4] == {"nested": "dict"}  # dict


# ============================================================================
# Test dumps_bytes Function
# ============================================================================


class TestDumpsBytesFunction:
    """Test dumps_bytes() function."""

    def test_returns_bytes_type(self) -> None:
        """Test dumps_bytes returns bytes type.

        Arrange: Create simple dict
        Act: Call dumps_bytes
        Assert: Returns bytes
        """
        # Arrange
        data = {"key": "value"}

        # Act
        result = dumps_bytes(data)

        # Assert
        assert isinstance(result, bytes)
        assert result == b'{"key": "value"}'

    def test_encodes_to_utf8(self) -> None:
        """Test dumps_bytes uses UTF-8 encoding.

        Arrange: Create dict with Unicode
        Act: Call dumps_bytes and decode
        Assert: UTF-8 encoded correctly
        """
        # Arrange
        data = {"unicode": "Hello 世界"}

        # Act
        result = dumps_bytes(data)

        # Assert
        assert isinstance(result, bytes)
        decoded = result.decode("utf-8")
        # JSON may escape Unicode or preserve it, both are valid
        assert "Hello" in decoded
        assert "unicode" in decoded

    def test_handles_extended_types(self) -> None:
        """Test dumps_bytes works with extended types.

        Arrange: Create dict with UUID
        Act: Call dumps_bytes and parse
        Assert: UUID serialized correctly
        """
        # Arrange
        test_uuid = uuid7()

        # Act
        result = dumps_bytes({"id": test_uuid})

        # Assert
        assert isinstance(result, bytes)
        data = loads(result)
        assert data["id"] == str(test_uuid)

    def test_accepts_kwargs(self) -> None:
        """Test dumps_bytes accepts and forwards kwargs.

        Arrange: Create dict
        Act: Call with indent kwarg
        Assert: Output is indented
        """
        # Arrange
        data = {"key": "value"}

        # Act
        result = dumps_bytes(data, indent=2)

        # Assert
        assert isinstance(result, bytes)
        assert b"\n" in result  # Indentation creates newlines


# ============================================================================
# Test loads Function
# ============================================================================


class TestLoadsFunction:
    """Test loads() function."""

    def test_loads_from_string(self) -> None:
        """Test loads deserializes string input.

        Arrange: Create JSON string
        Act: Call loads
        Assert: Returns dict
        """
        # Arrange
        json_str = '{"key": "value"}'

        # Act
        result = loads(json_str)

        # Assert
        assert result == {"key": "value"}

    def test_loads_from_bytes(self) -> None:
        """Test loads deserializes bytes input.

        Arrange: Create JSON bytes
        Act: Call loads
        Assert: Returns dict
        """
        # Arrange
        json_bytes = b'{"key": "value"}'

        # Act
        result = loads(json_bytes)

        # Assert
        assert result == {"key": "value"}

    def test_loads_empty_dict(self) -> None:
        """Test loads handles empty dict.

        Arrange: Create empty JSON object string
        Act: Call loads
        Assert: Returns empty dict
        """
        # Arrange
        json_str = "{}"

        # Act
        result = loads(json_str)

        # Assert
        assert result == {}

    def test_loads_list(self) -> None:
        """Test loads handles list.

        Arrange: Create JSON array string
        Act: Call loads
        Assert: Returns list
        """
        # Arrange
        json_str = "[1, 2, 3]"

        # Act
        result = loads(json_str)

        # Assert
        assert result == [1, 2, 3]

    def test_loads_with_kwargs(self) -> None:
        """Test loads forwards kwargs to json.loads.

        Arrange: Create JSON with float
        Act: Call with parse_float kwarg
        Assert: Float parsed as Decimal
        """
        # Arrange
        json_str = '{"value": 1.5}'

        # Act
        result = loads(json_str, parse_float=Decimal)

        # Assert
        assert isinstance(result["value"], Decimal)
        assert result["value"] == Decimal("1.5")


# ============================================================================
# Test Serialization Kwargs
# ============================================================================


class TestSerializationKwargs:
    """Test kwargs passthrough to underlying json functions."""

    def test_dumps_forwards_indent_kwarg(self) -> None:
        """Test dumps forwards indent kwarg to json.dumps.

        Arrange: Create dict
        Act: Call dumps with indent
        Assert: Output is indented
        """
        # Arrange
        data = {"key": "value", "number": 42}

        # Act
        result = dumps(data, indent=2)

        # Assert
        assert "\n" in result  # Indentation creates newlines

    def test_dumps_forwards_sort_keys_kwarg(self) -> None:
        """Test dumps forwards sort_keys kwarg.

        Arrange: Create dict with multiple keys
        Act: Call dumps with sort_keys
        Assert: Keys are sorted
        """
        # Arrange
        data = {"zebra": 1, "alpha": 2, "beta": 3}

        # Act
        result = dumps(data, sort_keys=True)

        # Assert
        # "alpha" should come before "zebra" in sorted output
        assert result.index('"alpha"') < result.index('"zebra"')

    def test_dumps_combines_indent_and_sort_keys(self) -> None:
        """Test dumps handles multiple kwargs together.

        Arrange: Create dict
        Act: Call dumps with indent and sort_keys
        Assert: Both applied
        """
        # Arrange
        data = {"key": "value", "number": 42}

        # Act
        result = dumps(data, indent=2, sort_keys=True)

        # Assert
        assert "\n" in result  # Indented
        assert result.index('"key"') < result.index('"number"')  # Sorted


# ============================================================================
# Test Serialization Edge Cases
# ============================================================================


class TestSerializationEdgeCases:
    """Test edge cases and special values."""

    def test_serializes_none_value(self) -> None:
        """Test None serializes to null.

        Arrange: Create dict with None
        Act: Serialize and parse
        Assert: None preserved
        """
        # Arrange
        data = {"value": None}

        # Act
        result = dumps(data)
        parsed = loads(result)

        # Assert
        assert parsed["value"] is None

    def test_serializes_empty_collections(self) -> None:
        """Test empty collections serialize correctly.

        Arrange: Create dict with empty list, dict, set
        Act: Serialize and parse
        Assert: All become empty JSON equivalents
        """
        # Arrange
        data = {
            "empty_list": [],
            "empty_dict": {},
            "empty_set": set(),
        }

        # Act
        result = dumps(data)
        parsed = loads(result)

        # Assert
        assert parsed["empty_list"] == []
        assert parsed["empty_dict"] == {}
        assert parsed["empty_set"] == []  # set becomes list

    def test_serializes_boolean_values(self) -> None:
        """Test boolean values serialize correctly.

        Arrange: Create dict with True and False
        Act: Serialize and parse
        Assert: Booleans preserved
        """
        # Arrange
        data = {"enabled": True, "disabled": False}

        # Act
        result = dumps(data)
        parsed = loads(result)

        # Assert
        assert parsed["enabled"] is True
        assert parsed["disabled"] is False

    def test_serializes_zero_values(self) -> None:
        """Test zero values of various types.

        Arrange: Create dict with zero values
        Act: Serialize and parse
        Assert: All zeros preserved
        """
        # Arrange
        data = {
            "int_zero": 0,
            "float_zero": 0.0,
            "decimal_zero": Decimal(0),
        }

        # Act
        result = dumps(data)
        parsed = loads(result)

        # Assert
        assert parsed["int_zero"] == 0
        assert parsed["float_zero"] == 0.0
        assert parsed["decimal_zero"] == 0.0  # Decimal becomes float

    def test_serializes_negative_numbers(self) -> None:
        """Test negative numbers serialize correctly.

        Arrange: Create dict with negative values
        Act: Serialize and parse
        Assert: Negative signs preserved
        """
        # Arrange
        data = {
            "negative_int": -42,
            "negative_float": -3.14,
            "negative_decimal": Decimal("-99.99"),
        }

        # Act
        result = dumps(data)
        parsed = loads(result)

        # Assert
        assert parsed["negative_int"] == -42
        assert parsed["negative_float"] == -3.14
        assert parsed["negative_decimal"] == -99.99

    def test_serializes_special_string_characters(self) -> None:
        """Test strings with special characters serialize correctly.

        Arrange: Create dict with special chars
        Act: Serialize and parse
        Assert: Characters preserved
        """
        # Arrange
        data = {
            "newline": "line1\nline2",
            "tab": "col1\tcol2",
            "quote": 'He said "hello"',
            "backslash": "path\\to\\file",
        }

        # Act
        result = dumps(data)
        parsed = loads(result)

        # Assert
        assert parsed["newline"] == "line1\nline2"
        assert parsed["tab"] == "col1\tcol2"
        assert parsed["quote"] == 'He said "hello"'
        assert parsed["backslash"] == "path\\to\\file"

    def test_roundtrip_preserves_data_integrity(self) -> None:
        """Test dumps + loads roundtrip preserves basic types.

        Arrange: Create dict with basic types
        Act: Serialize then deserialize
        Assert: Data matches original
        """
        # Arrange
        original = {
            "string": "test",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        # Act
        serialized = dumps(original)
        deserialized = loads(serialized)

        # Assert
        assert deserialized == original
