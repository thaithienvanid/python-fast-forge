"""Repository interfaces defining data access contracts.

This module defines abstract interfaces for repositories, establishing
the contract between the domain and infrastructure layers. These interfaces
enable dependency inversion and facilitate testing with mock implementations.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from uuid import UUID


if TYPE_CHECKING:
    from src.infrastructure.filtering.filterset import FilterSet
else:
    FilterSet = Any


class IRepository[T](ABC):
    """Base repository interface for entity CRUD operations with soft delete support.

    Defines the standard data access contract for all repositories. Implementations
    handle data persistence while the domain layer remains infrastructure-agnostic.

    Type Parameters:
        T: Entity type managed by this repository
    """

    @abstractmethod
    async def get_by_id(self, id: UUID, include_deleted: bool = False) -> T | None:
        """Retrieve entity by its unique identifier.

        Args:
            id: Entity's unique identifier (UUID)
            include_deleted: Whether to include soft-deleted entities in search

        Returns:
            Entity instance if found, None otherwise
        """

    @abstractmethod
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
        include_deleted: bool = False,
    ) -> list[T]:
        """Retrieve all entities with pagination and optional multi-tenant filtering.

        Args:
            skip: Number of records to skip (offset for pagination)
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for multi-tenant data isolation
            include_deleted: Whether to include soft-deleted entities

        Returns:
            List of entity instances matching criteria
        """

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Persist a new entity to the data store.

        Args:
            entity: Entity instance to create

        Returns:
            Created entity with generated fields populated
        """

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Persist changes to an existing entity.

        Args:
            entity: Entity instance with updated values

        Returns:
            Updated entity with refreshed state
        """

    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """Mark entity as deleted without removing from database (soft delete).

        Sets the deleted_at timestamp, hiding the entity from normal queries
        while preserving data for audit purposes or potential restoration.

        Args:
            id: Entity's unique identifier

        Returns:
            True if entity was soft-deleted successfully, False if not found
        """

    @abstractmethod
    async def restore(self, id: UUID) -> bool:
        """Restore a previously soft-deleted entity.

        Clears the deleted_at timestamp, making the entity visible in
        normal queries again.

        Args:
            id: Entity's unique identifier

        Returns:
            True if entity was restored, False if not found or not deleted
        """

    @abstractmethod
    async def force_delete(self, id: UUID) -> bool:
        """Permanently remove entity from database (hard delete).

        This operation is irreversible. Use with caution as it removes
        all traces of the entity from the database.

        Args:
            id: Entity's unique identifier

        Returns:
            True if entity was permanently deleted, False if not found
        """

    @abstractmethod
    async def get_deleted(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
    ) -> list[T]:
        """Retrieve only soft-deleted entities with pagination.

        Useful for administrative tasks like reviewing deleted records
        before permanent deletion or for restoration workflows.

        Args:
            skip: Number of records to skip (offset for pagination)
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for multi-tenant data isolation

        Returns:
            List of soft-deleted entity instances
        """

    @abstractmethod
    async def find(
        self,
        filterset: "FilterSet",
        skip: int = 0,
        limit: int = 100,
    ) -> list[T]:
        """Find entities using dynamic filter criteria with pagination.

        Uses FilterSet to build dynamic queries based on provided filter criteria.
        This enables flexible, type-safe filtering without writing custom queries.
        Follows idiomatic repository patterns (similar to Spring Data's findBy).

        Args:
            filterset: FilterSet instance containing filter criteria
            skip: Number of records to skip (offset for pagination)
            limit: Maximum number of records to return

        Returns:
            List of entities matching all filter criteria

        Example:
            ```python
            filters = UserFilterSet(email__icontains="@example.com", is_active=True)
            users = await repository.find(filters, skip=0, limit=50)
            ```
        """

    @abstractmethod
    async def count(self, filterset: "FilterSet") -> int:
        """Count total entities matching filter criteria without pagination.

        Useful for implementing pagination UI that shows total count.
        Works with the same FilterSet as find() for consistent filtering.

        Args:
            filterset: FilterSet instance containing filter criteria

        Returns:
            Total count of entities matching the filters

        Example:
            ```python
            filters = UserFilterSet(is_active=True)
            total = await repository.count(filters)
            # Use for pagination: total_pages = ceil(total / page_size)
            ```
        """


class IUserRepository[T](IRepository[T]):
    """User-specific repository interface extending base repository operations.

    Adds user-specific query methods for common access patterns like
    email and username lookups. Filtering support is inherited from IRepository.
    """

    @abstractmethod
    async def get_by_email(self, email: str) -> T | None:
        """Retrieve user by email address.

        Args:
            email: User's email address (case-insensitive)

        Returns:
            User instance if found, None otherwise
        """

    @abstractmethod
    async def get_by_username(self, username: str) -> T | None:
        """Retrieve user by username.

        Args:
            username: User's unique username

        Returns:
            User instance if found, None otherwise
        """
