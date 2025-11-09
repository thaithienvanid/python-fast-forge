"""Dependency injection container configuration."""

from typing import Any

from dependency_injector import containers, providers

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
from src.domain.interfaces import IUserRepository
from src.domain.models.user import User
from src.external.email_service import EmailService
from src.infrastructure.cache.redis_cache import RedisCache
from src.infrastructure.config import get_settings
from src.infrastructure.patterns.circuit_breaker import CircuitBreakerService
from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.unit_of_work import UnitOfWork
from src.infrastructure.repositories.cached_user_repository import CachedUserRepository
from src.infrastructure.repositories.user_repository import UserRepository


class UseCases(containers.DeclarativeContainer):
    """Use cases container for better organization."""

    user_repository: providers.Dependency[IUserRepository[User]] = providers.Dependency()
    uow_factory: providers.Dependency[Any] = providers.Dependency()

    get_user = providers.Factory(GetUserUseCase, user_repository=user_repository)
    list_users = providers.Factory(ListUsersUseCase, user_repository=user_repository)
    create_user = providers.Factory(CreateUserUseCase, user_repository=user_repository)
    update_user = providers.Factory(UpdateUserUseCase, user_repository=user_repository)
    delete_user = providers.Factory(DeleteUserUseCase, user_repository=user_repository)
    batch_create_users = providers.Factory(BatchCreateUsersUseCase, uow_factory=uow_factory)
    restore_user = providers.Factory(RestoreUserUseCase, user_repository=user_repository)
    force_delete_user = providers.Factory(ForceDeleteUserUseCase, user_repository=user_repository)
    get_deleted_users = providers.Factory(GetDeletedUsersUseCase, user_repository=user_repository)
    search_users = providers.Factory(SearchUsersUseCase, repository=user_repository)


class Container(containers.DeclarativeContainer):
    """Application dependency injection container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.presentation.api.v1.endpoints.users",
            "src.presentation.api.v1.endpoints.health",
        ]
    )

    # Configuration
    config = providers.Singleton(get_settings)

    # Infrastructure
    database = providers.Singleton(Database, settings=config)
    cache = providers.Singleton(RedisCache, settings=config)
    circuit_breaker = providers.Singleton(CircuitBreakerService)

    # Provide database session as a context manager
    db_session = providers.Factory(
        database.provided.session,
    )

    # Repositories - using Decorator Pattern for caching
    # Base repository (pure DB operations)
    user_repository_base = providers.Factory(
        UserRepository,
        session=db_session,
    )

    # Cached repository (decorates base with caching)
    user_repository_cached = providers.Factory(
        CachedUserRepository,
        repository=user_repository_base,
        cache=cache,
    )

    # Selector for repository based on cache_enabled setting
    # Caching can be toggled via CACHE_ENABLED environment variable
    # - CACHE_ENABLED=true  → Uses CachedUserRepository (Redis caching)
    # - CACHE_ENABLED=false → Uses UserRepository (direct DB, no cache)
    # Note: For now, always use cached repository (it handles cache misses gracefully)
    user_repository = user_repository_cached

    # Session factory for Unit of Work
    session_factory_provider = providers.Callable(database.provided.get_session_factory)

    # Unit of Work factory for transactional operations
    uow_factory = providers.Factory(
        UnitOfWork,
        session_factory=session_factory_provider,
    )

    # External Services
    email_service = providers.Singleton(
        EmailService,
        circuit_breaker=circuit_breaker,
        api_key=config.provided.email_api_key,
    )

    # Use Cases (nested container)
    use_cases = providers.Container(
        UseCases,
        user_repository=user_repository,
        uow_factory=uow_factory.provider,
    )
