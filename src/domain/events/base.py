"""Base domain event class.

Domain events represent something that happened in the domain that domain
experts care about. They are immutable facts about the past.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base class for all domain events.

    Domain events are immutable records of something that happened in the domain.
    They should be named in past tense (e.g., UserCreated, OrderPlaced).

    Attributes:
        event_id: Unique identifier for this event occurrence
        aggregate_id: ID of the aggregate root that generated the event
        occurred_at: When the event occurred (UTC)
        event_version: Version number for event schema evolution

    Example:
        >>> class OrderPlacedEvent(DomainEvent):
        ...     order_id: UUID
        ...     total_amount: Decimal
        ...     customer_id: UUID
    """

    # Event metadata (inherited by all events)
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    aggregate_id: UUID = Field(..., description="ID of aggregate that generated event")
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When event occurred (UTC)",
    )
    event_version: int = Field(default=1, description="Event schema version")

    class Config:
        """Pydantic config."""

        frozen = True  # Events are immutable
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }

    @property
    def event_type(self) -> str:
        """Get the event type name.

        Returns:
            The class name of the event (e.g., "UserCreatedEvent")

        Example:
            >>> event = UserCreatedEvent(...)
            >>> event.event_type
            'UserCreatedEvent'
        """
        return self.__class__.__name__

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary.

        Returns:
            Dictionary representation including event metadata

        Example:
            >>> event = UserCreatedEvent(user_id=uuid4(), email="test@example.com")
            >>> data = event.to_dict()
            >>> assert "event_type" in data
            >>> assert "occurred_at" in data
        """
        data = self.model_dump()
        data["event_type"] = self.event_type
        return data

    def __str__(self) -> str:
        """String representation of event."""
        return f"{self.event_type}(aggregate_id={self.aggregate_id}, occurred_at={self.occurred_at})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"<{self.event_type} id={self.event_id} aggregate={self.aggregate_id}>"
