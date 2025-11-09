"""User API endpoints."""

from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path, Query, status

from src.app.usecases.user_usecases import (
    BatchCreateUsersUseCase,
    CreateUserUseCase,
    DeleteUserUseCase,
    ForceDeleteUserUseCase,
    GetDeletedUsersUseCase,
    GetUserUseCase,
    ListUsersUseCase,
    RestoreUserUseCase,
    SearchUsersUseCase,
    UpdateUserUseCase,
)
from src.container import Container
from src.infrastructure.filtering.user_filterset import UserFilterSet
from src.presentation.api.dependencies import get_tenant_id
from src.presentation.schemas.error import ErrorResponse
from src.presentation.schemas.user import (
    BatchUserCreate,
    BatchUserCreateResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
    description="Create a new user with optional tenant isolation",
    responses={
        status.HTTP_201_CREATED: {
            "description": "User created successfully",
            "model": UserResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Conflict - user with email or username already exists",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid request data - missing fields or invalid format",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def create_user(
    input: UserCreate,
    use_case: Annotated[CreateUserUseCase, Depends(Provide[Container.use_cases.create_user])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> UserResponse:
    """Create a new user.

    Args:
        input: User creation data
        use_case: Injected use case instance
        tenant_id: Optional tenant ID for multi-tenancy (from X-Tenant-ID header)

    Returns:
        Created user data
    """
    user = await use_case.execute(
        email=input.email,
        username=input.username,
        full_name=input.full_name,
        tenant_id=tenant_id,
    )
    return UserResponse.model_validate(user)


@router.get(
    "",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Users",
    description="Get a list of users with pagination and optional tenant filtering",
    responses={
        status.HTTP_200_OK: {
            "description": "List of users retrieved successfully",
            "model": UserListResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid pagination parameters",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def list_users(
    use_case: Annotated[ListUsersUseCase, Depends(Provide[Container.use_cases.list_users])],
    skip: Annotated[
        int, Query(ge=0, le=10000, description="Number of records to skip (max 10000)")
    ] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum records to return (max 100)")
    ] = 20,
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> UserListResponse:
    """List users with pagination and optional tenant filtering.

    Args:
        use_case: Injected use case instance
        skip: Number of records to skip (max 10000)
        limit: Maximum number of records to return (max 100)
        tenant_id: Optional tenant ID for filtering (from X-Tenant-ID header)

    Returns:
        Paginated list of users
    """
    users = await use_case.execute(skip=skip, limit=limit, tenant_id=tenant_id)

    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=len(users),
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User",
    description="Get a user by ID with tenant isolation",
    responses={
        status.HTTP_200_OK: {"description": "User retrieved successfully", "model": UserResponse},
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or tenant ID doesn't match",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid user ID format",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def get_user(
    user_id: Annotated[UUID, Path(description="User ID")],
    use_case: Annotated[GetUserUseCase, Depends(Provide[Container.use_cases.get_user])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> UserResponse:
    """Get a user by ID with tenant isolation.

    Args:
        user_id: User ID (UUIDv7 format)
        use_case: Injected use case instance
        tenant_id: Optional tenant ID for isolation (from X-Tenant-ID header)

    Returns:
        User data
    """
    user = await use_case.execute(user_id, tenant_id=tenant_id)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User",
    description="Update a user by ID with tenant isolation",
    responses={
        status.HTTP_200_OK: {"description": "User updated successfully", "model": UserResponse},
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or tenant ID doesn't match",
            "model": ErrorResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Conflict - email or username already exists",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid request data or user ID format",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def update_user(
    user_id: Annotated[UUID, Path(description="User ID")],
    input: UserUpdate,
    use_case: Annotated[UpdateUserUseCase, Depends(Provide[Container.use_cases.update_user])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> UserResponse:
    """Update a user with tenant isolation.

    Args:
        user_id: User ID (UUIDv7 format)
        input: User update data
        use_case: Injected use case instance
        tenant_id: Optional tenant ID for isolation (from X-Tenant-ID header)

    Returns:
        Updated user data
    """
    user = await use_case.execute(
        user_id=user_id,
        email=input.email,
        username=input.username,
        full_name=input.full_name,
        is_active=input.is_active,
        tenant_id=tenant_id,
    )
    return UserResponse.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft Delete User",
    description="Soft delete a user by ID with tenant isolation (sets deleted_at timestamp, can be restored)",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "User soft deleted successfully"},
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or tenant ID doesn't match",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid user ID format",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def delete_user(
    user_id: Annotated[UUID, Path(description="User ID")],
    use_case: Annotated[DeleteUserUseCase, Depends(Provide[Container.use_cases.delete_user])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> None:
    """Soft delete a user with tenant isolation.

    This performs a soft delete by setting the deleted_at timestamp.
    The user will be excluded from normal queries but can be restored later.

    Args:
        user_id: User ID (UUIDv7 format)
        use_case: Injected use case instance
        tenant_id: Optional tenant ID for isolation (from X-Tenant-ID header)
    """
    await use_case.execute(user_id, tenant_id=tenant_id)


@router.post(
    "/batch",
    response_model=BatchUserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch Create Users",
    description="Create multiple users atomically in a single transaction using Unit of Work pattern",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Users created successfully",
            "model": BatchUserCreateResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Validation failed - duplicates within batch or too many users",
            "model": ErrorResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Conflict - users already exist with given emails/usernames",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid request data - missing fields or invalid format",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during batch creation",
            "model": ErrorResponse,
        },
    },
)
@inject
async def batch_create_users(
    input: BatchUserCreate,
    use_case: Annotated[
        BatchCreateUsersUseCase, Depends(Provide[Container.use_cases.batch_create_users])
    ],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> BatchUserCreateResponse:
    """Create multiple users in a single atomic transaction.

    This endpoint demonstrates the Unit of Work pattern by ensuring that
    either all users are created successfully, or none are created if any
    failure occurs. This provides atomicity and consistency for batch operations.

    **Transaction Guarantees:**
    - All users are created in a single database transaction
    - If any user creation fails, the entire batch is rolled back
    - No partial results - all or nothing semantics

    **Validation:**
    - Checks for duplicate emails/usernames within the batch
    - Checks for conflicts with existing users in the database
    - Maximum of 100 users per batch request

    **Error Responses:**
    - 400: Validation failed (duplicates within batch, too many users)
    - 409: Conflict (users already exist with given emails/usernames)
    - 422: Invalid request data (missing fields, invalid email/username format)
    - 500: Internal server error

    Args:
        input: Batch user creation data containing list of users
        use_case: Injected batch create use case instance
        tenant_id: Optional tenant ID for multi-tenancy (from X-Tenant-ID header)

    Returns:
        Batch creation response with all created users
    """
    # Convert UserCreate schemas to dict format expected by use case
    users_data = [
        {
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        }
        for user in input.users
    ]

    # Execute batch creation with UnitOfWork
    created_users = await use_case.execute(users_data=users_data, tenant_id=tenant_id)

    return BatchUserCreateResponse(
        created=[UserResponse.model_validate(user) for user in created_users],
        total=len(created_users),
        message=f"Successfully created {len(created_users)} user(s) in a single transaction",
    )


@router.put(
    "/{user_id}/restore",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore Soft-Deleted User",
    description="Restore a soft-deleted user by clearing the deleted_at timestamp",
    responses={
        status.HTTP_200_OK: {"description": "User restored successfully", "model": UserResponse},
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or tenant ID doesn't match",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid user ID format or user is not deleted",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def restore_user(
    user_id: Annotated[UUID, Path(description="User ID")],
    use_case: Annotated[RestoreUserUseCase, Depends(Provide[Container.use_cases.restore_user])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> UserResponse:
    """Restore a soft-deleted user with tenant isolation.

    This clears the deleted_at timestamp, making the user active again
    and available in normal queries.

    Args:
        user_id: User ID (UUIDv7 format)
        use_case: Injected use case instance
        tenant_id: Optional tenant ID for isolation (from X-Tenant-ID header)

    Returns:
        Restored user data
    """
    user = await use_case.execute(user_id, tenant_id=tenant_id)
    return UserResponse.model_validate(user)


@router.delete(
    "/{user_id}/force",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Force Delete User",
    description="Permanently delete a user from the database (irreversible hard delete)",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "User permanently deleted successfully"},
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found or tenant ID doesn't match",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid user ID format",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def force_delete_user(
    user_id: Annotated[UUID, Path(description="User ID")],
    use_case: Annotated[
        ForceDeleteUserUseCase, Depends(Provide[Container.use_cases.force_delete_user])
    ],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> None:
    """Permanently delete a user with tenant isolation.

    This performs a hard delete, removing the user record from the database entirely.
    This action is irreversible - use with caution!

    Args:
        user_id: User ID (UUIDv7 format)
        use_case: Injected use case instance
        tenant_id: Optional tenant ID for isolation (from X-Tenant-ID header)
    """
    await use_case.execute(user_id, tenant_id=tenant_id)


@router.get(
    "/deleted",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Soft-Deleted Users",
    description="Get a list of soft-deleted users with pagination and optional tenant filtering",
    responses={
        status.HTTP_200_OK: {
            "description": "List of soft-deleted users retrieved successfully",
            "model": UserListResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid pagination parameters",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def list_deleted_users(
    use_case: Annotated[
        GetDeletedUsersUseCase, Depends(Provide[Container.use_cases.get_deleted_users])
    ],
    skip: Annotated[
        int, Query(ge=0, le=10000, description="Number of records to skip (max 10000)")
    ] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum records to return (max 100)")
    ] = 20,
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> UserListResponse:
    """List soft-deleted users with pagination and optional tenant filtering.

    This is useful for administrative tasks like reviewing deleted users
    before permanent deletion or for restoring accidentally deleted users.

    Args:
        use_case: Injected use case instance
        skip: Number of records to skip (max 10000)
        limit: Maximum number of records to return (max 100)
        tenant_id: Optional tenant ID for filtering (from X-Tenant-ID header)

    Returns:
        Paginated list of soft-deleted users
    """
    users = await use_case.execute(skip=skip, limit=limit, tenant_id=tenant_id)

    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=len(users),
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )


@router.get(
    "/search",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Users with Flexible Filters",
    description="""
Search users with flexible filtering using query parameters.

This endpoint demonstrates the FilterSet pattern for declarative filtering,
following Clean Architecture principles with proper layer separation.

**Filter Examples:**
- Search by text: `?username=john&email=gmail.com`
- Filter by status: `?is_active=true`
- Date range: `?created_after=2024-01-01T00:00:00Z&created_before=2024-12-31T23:59:59Z`
- Tenant filter: `?tenant_id=018c5e9e-1234-7000-8000-000000000001`

**Available Filters:**
- `username` - Search in username (case-insensitive)
- `email` - Search in email (case-insensitive)
- `full_name` - Search in full name (case-insensitive)
- `username_exact` - Exact username match
- `email_exact` - Exact email match
- `is_active` - Filter by active status (true/false)
- `tenant_id` - Filter by tenant ID
- `created_after` - Users created after this date
- `created_before` - Users created before this date
- `updated_after` - Users updated after this date

All text filters are case-insensitive substring searches unless marked as "exact".
    """,
    responses={
        status.HTTP_200_OK: {
            "description": "Filtered list of users",
            "model": UserListResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid filter parameters",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)
@inject
async def search_users(
    filters: UserFilterSet = Depends(),
    skip: Annotated[
        int, Query(ge=0, le=10000, description="Number of records to skip (max 10000)")
    ] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum records to return (max 100)")
    ] = 20,
    use_case: Annotated[
        SearchUsersUseCase, Depends(Provide[Container.use_cases.search_users])
    ] = ...,  # type: ignore
) -> UserListResponse:
    """Search users with flexible filters using FilterSet pattern.

    This endpoint follows Clean Architecture principles:
    - Presentation Layer: Receives HTTP request, validates query parameters via FilterSet
    - Application Layer: SearchUsersUseCase orchestrates business logic
    - Infrastructure Layer: Repository handles database queries with SQLAlchemy

    This ensures proper separation of concerns and no SQLAlchemy imports in presentation layer.

    Examples:
        # Search for admin users
        GET /api/v1/users/search?username=admin&is_active=true

        # Find users by email domain
        GET /api/v1/users/search?email=@company.com

        # Get recently created users
        GET /api/v1/users/search?created_after=2024-01-01T00:00:00Z

        # Combine multiple filters
        GET /api/v1/users/search?username=john&is_active=true&created_after=2024-01-01T00:00:00Z

    Args:
        filters: FilterSet automatically populated from query parameters
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        use_case: Injected SearchUsersUseCase instance

    Returns:
        Paginated list of users matching the filters
    """
    # Execute search through use case layer (no SQLAlchemy here!)
    users, total = await use_case.execute(filterset=filters, skip=skip, limit=limit)

    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )
