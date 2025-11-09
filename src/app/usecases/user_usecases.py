"""User use cases implementing business logic."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import EntityNotFoundError, ValidationError
from src.domain.interfaces import IUserRepository
from src.domain.models.user import User
from src.infrastructure.persistence.unit_of_work import UnitOfWork


class GetUserUseCase:
    """Use case for getting a user by ID."""

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(self, user_id: UUID, tenant_id: UUID | None = None) -> User:
        """Execute the use case.

        Args:
            user_id: The ID of the user to retrieve
            tenant_id: Optional tenant ID for multi-tenancy filtering

        Returns:
            The user entity

        Raises:
            EntityNotFoundError: If user is not found
        """
        user = await self._repository.get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        # Enforce tenant isolation if tenant_id provided
        if tenant_id and user.tenant_id != tenant_id:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        return user


class ListUsersUseCase:
    """Use case for listing users with pagination."""

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
    ) -> list[User]:
        """Execute the use case.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for multi-tenancy filtering

        Returns:
            List of user entities

        Raises:
            ValidationError: If parameters are invalid
        """
        if skip < 0:
            raise ValidationError("Skip must be non-negative")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        return await self._repository.get_all(skip=skip, limit=limit, tenant_id=tenant_id)


class CreateUserUseCase:
    """Use case for creating a new user."""

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(
        self,
        email: str,
        username: str,
        full_name: str | None = None,
        tenant_id: UUID | None = None,
    ) -> User:
        """Execute the use case.

        Args:
            email: User email address
            username: User username
            full_name: User full name (optional)
            tenant_id: Tenant ID for multi-tenancy (optional)

        Returns:
            The created user entity

        Raises:
            ValidationError: If user already exists (duplicate email/username)
        """
        # Create new user - rely on database unique constraints for validation
        user = User(
            email=email,
            username=username,
            full_name=full_name,
            tenant_id=tenant_id,
        )

        try:
            created_user = await self._repository.create(user)
        except IntegrityError as e:
            # Parse database constraint violation to provide helpful error
            error_msg = str(e.orig).lower() if hasattr(e, "orig") else str(e).lower()

            if "email" in error_msg or "ix_users_email" in error_msg:
                raise ValidationError(f"User with email {email} already exists") from e
            if "username" in error_msg or "ix_users_username" in error_msg:
                raise ValidationError(f"User with username {username} already exists") from e
            # Re-raise if it's a different integrity error
            raise

        # Send welcome email asynchronously (Temporal workflow)
        try:
            from src.app.tasks.user_tasks import SendWelcomeEmailWorkflow
            from src.infrastructure.temporal_client import get_temporal_client

            client = await get_temporal_client()
            await client.start_workflow(
                SendWelcomeEmailWorkflow.run,
                args=[str(created_user.id), email],
                id=f"send-welcome-email-{created_user.id}",
                task_queue="fastapi-tasks",
            )
        except Exception as e:
            # Log error but don't fail user creation if workflow start fails
            from src.infrastructure.logging.config import get_logger

            logger = get_logger(__name__)
            logger.error(
                "failed_to_start_welcome_email_workflow", error=str(e), user_id=str(created_user.id)
            )

        return created_user


class UpdateUserUseCase:
    """Use case for updating an existing user."""

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(
        self,
        user_id: UUID,
        email: str | None = None,
        username: str | None = None,
        full_name: str | None = None,
        is_active: bool | None = None,
        tenant_id: UUID | None = None,
    ) -> User:
        """Execute the use case.

        Args:
            user_id: ID of the user to update
            email: New email (optional)
            username: New username (optional)
            full_name: New full name (optional)
            is_active: New active status (optional)
            tenant_id: Optional tenant ID for multi-tenancy filtering

        Returns:
            The updated user entity

        Raises:
            EntityNotFoundError: If user is not found
            ValidationError: If email/username already exists
        """
        user = await self._repository.get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        # Enforce tenant isolation if tenant_id provided
        if tenant_id and user.tenant_id != tenant_id:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        # Apply updates
        if email is not None and email != user.email:
            user.email = email

        if username is not None and username != user.username:
            user.username = username

        if full_name is not None:
            user.full_name = full_name

        if is_active is not None:
            user.is_active = is_active

        # Update user - rely on database constraints for duplicate validation
        try:
            return await self._repository.update(user)
        except IntegrityError as e:
            # Parse database constraint violation
            error_msg = str(e.orig).lower() if hasattr(e, "orig") else str(e).lower()

            if "email" in error_msg or "ix_users_email" in error_msg:
                raise ValidationError(f"User with email {email} already exists") from e
            if "username" in error_msg or "ix_users_username" in error_msg:
                raise ValidationError(f"User with username {username} already exists") from e
            raise


class DeleteUserUseCase:
    """Use case for soft deleting a user.

    This performs a soft delete by setting the deleted_at timestamp.
    The user will be excluded from normal queries but can be restored later.
    """

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(self, user_id: UUID, tenant_id: UUID | None = None) -> bool:
        """Execute the soft delete use case.

        Args:
            user_id: ID of the user to soft delete
            tenant_id: Optional tenant ID for multi-tenancy filtering

        Returns:
            True if soft deleted successfully

        Raises:
            EntityNotFoundError: If user is not found or already deleted
        """
        # Check tenant isolation before deletion
        if tenant_id:
            user = await self._repository.get_by_id(user_id, include_deleted=False)
            if not user:
                raise EntityNotFoundError(f"User with ID {user_id} not found")
            if user.tenant_id != tenant_id:
                raise EntityNotFoundError(f"User with ID {user_id} not found")

        if not await self._repository.delete(user_id):
            raise EntityNotFoundError(f"User with ID {user_id} not found")
        return True


class BatchCreateUsersUseCase:
    """Use case for batch creating multiple users in a single transaction.

    This use case demonstrates the Unit of Work pattern by ensuring
    that either all users are created successfully, or none are created
    if any failure occurs (atomicity).

    Example:
        ```python
        use_case = BatchCreateUsersUseCase(uow_factory)
        results = await use_case.execute(
            [
                {"email": "user1@example.com", "username": "user1"},
                {"email": "user2@example.com", "username": "user2"},
            ]
        )
        ```
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        """Initialize the use case.

        Args:
            uow_factory: Factory function to create UnitOfWork instances
        """
        self._uow_factory = uow_factory

    async def execute(
        self,
        users_data: list[dict[str, Any]],
        tenant_id: UUID | None = None,
    ) -> list[User]:
        """Execute batch user creation in a single transaction.

        Args:
            users_data: List of user data dictionaries with keys:
                - email (str): User email address
                - username (str): User username
                - full_name (str | None): Optional full name
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            List of created user entities

        Raises:
            ValidationError: If any user data is invalid or duplicates exist
            ValueError: If users_data is empty

        Note:
            All users are created within a single transaction using UnitOfWork.
            If any user creation fails, the entire batch is rolled back automatically.
        """
        if not users_data:
            raise ValueError("users_data cannot be empty")

        if len(users_data) > 100:
            raise ValidationError("Cannot create more than 100 users at once")

        created_users: list[User] = []

        try:
            # Use Unit of Work to ensure all operations are in a single transaction
            async with self._uow_factory() as uow:
                # Check for duplicates within the batch
                emails = [user_data["email"] for user_data in users_data]
                usernames = [user_data["username"] for user_data in users_data]

                # Check for duplicates within the batch itself
                if len(emails) != len(set(emails)):
                    raise ValidationError("Duplicate emails found in batch")
                if len(usernames) != len(set(usernames)):
                    raise ValidationError("Duplicate usernames found in batch")

                # Check for existing users with same email or username
                for email in emails:
                    existing = await uow.users.get_by_email(email)
                    if existing:
                        raise ValidationError(f"User with email {email} already exists")

                for username in usernames:
                    existing = await uow.users.get_by_username(username)
                    if existing:
                        raise ValidationError(f"User with username {username} already exists")

                # Create all users
                for user_data in users_data:
                    user = User(
                        email=user_data["email"],
                        username=user_data["username"],
                        full_name=user_data.get("full_name"),
                        tenant_id=tenant_id,
                    )
                    created_user = await uow.users.create(user)
                    created_users.append(created_user)

                # Transaction is automatically committed on successful exit
                # If any error occurs above, transaction is automatically rolled back

        except IntegrityError as e:
            # Handle database constraint violations
            error_msg = str(e.orig).lower() if hasattr(e, "orig") else str(e).lower()

            if "email" in error_msg or "ix_users_email" in error_msg:
                raise ValidationError("One or more emails already exist") from e
            if "username" in error_msg or "ix_users_username" in error_msg:
                raise ValidationError("One or more usernames already exist") from e
            raise

        return created_users


class RestoreUserUseCase:
    """Use case for restoring a soft-deleted user.

    This clears the deleted_at timestamp, making the user active again
    and available in normal queries.
    """

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(self, user_id: UUID, tenant_id: UUID | None = None) -> User:
        """Execute the restore use case.

        Args:
            user_id: ID of the user to restore
            tenant_id: Optional tenant ID for multi-tenancy filtering

        Returns:
            The restored user entity

        Raises:
            EntityNotFoundError: If user is not found or not deleted
        """
        # Get the deleted user to check existence and tenant
        user = await self._repository.get_by_id(user_id, include_deleted=True)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        # Enforce tenant isolation if tenant_id provided
        if tenant_id and user.tenant_id != tenant_id:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        # Check if user is actually deleted
        if not user.is_deleted:
            raise ValidationError(f"User with ID {user_id} is not deleted")

        if not await self._repository.restore(user_id):
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        # Fetch and return the restored user
        restored_user = await self._repository.get_by_id(user_id, include_deleted=False)
        if not restored_user:
            raise EntityNotFoundError(f"Failed to restore user with ID {user_id}")

        return restored_user


class ForceDeleteUserUseCase:
    """Use case for permanently deleting a user.

    This performs a hard delete, removing the user record from the database entirely.
    This action is irreversible - use with caution!
    """

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(self, user_id: UUID, tenant_id: UUID | None = None) -> bool:
        """Execute the force delete use case.

        Args:
            user_id: ID of the user to permanently delete
            tenant_id: Optional tenant ID for multi-tenancy filtering

        Returns:
            True if permanently deleted successfully

        Raises:
            EntityNotFoundError: If user is not found
        """
        # Get user (including deleted) to check existence and tenant
        user = await self._repository.get_by_id(user_id, include_deleted=True)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        # Enforce tenant isolation if tenant_id provided
        if tenant_id and user.tenant_id != tenant_id:
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        if not await self._repository.force_delete(user_id):
            raise EntityNotFoundError(f"User with ID {user_id} not found")

        return True


class GetDeletedUsersUseCase:
    """Use case for retrieving only soft-deleted users.

    This is useful for administrative tasks like reviewing deleted users
    before permanent deletion or for restoring accidentally deleted users.
    """

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
    ) -> list[User]:
        """Execute the get deleted users use case.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for multi-tenancy filtering

        Returns:
            List of soft-deleted user entities

        Raises:
            ValidationError: If parameters are invalid
        """
        if skip < 0:
            raise ValidationError("Skip must be non-negative")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        return await self._repository.get_deleted(skip=skip, limit=limit, tenant_id=tenant_id)


class SearchUsersUseCase:
    """Use case for searching users with FilterSet."""

    def __init__(self, repository: IUserRepository[User]) -> None:
        """Initialize the use case.

        Args:
            repository: User repository
        """
        self._repository = repository

    async def execute(
        self,
        filterset: Any,  # FilterSet type (avoiding circular import)
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[User], int]:
        """Search users with FilterSet.

        Args:
            filterset: FilterSet instance with filter criteria
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of users, total count)
        """
        # Get total count
        total = await self._repository.count(filterset)

        # Get users with pagination
        users = await self._repository.find(
            filterset=filterset,
            skip=skip,
            limit=limit,
        )

        return users, total
