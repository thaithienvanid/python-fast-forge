"""Database migration tests.

Verifies that Alembic migrations can be applied and reversed correctly.

Note: Most tests require a PostgreSQL test database and are skipped by default.
See docs/how-to/running-tests.md for setup instructions.
"""

import os

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import command


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def test_db_engine() -> AsyncEngine:
    """Create a test database engine for migration testing.

    Uses a separate test database to avoid interfering with development data.

    Yields:
        AsyncEngine: SQLAlchemy async engine for test database

    Note:
        Assumes PostgreSQL database exists at:
        postgresql+asyncpg://postgres:postgres@localhost:5432/test_migrations_db
    """
    # Use a separate test database URL
    database_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_migrations_db"
    engine = create_async_engine(database_url, echo=True)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def alembic_config() -> Config:
    """Create Alembic configuration for testing.

    Returns:
        Config: Alembic configuration pointing to test database
    """
    # Set environment variable for test database
    # The Settings class will automatically pick this up
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/test_migrations_db"
    )

    config = Config("alembic.ini")
    return config


# ============================================================================
# Test Classes
# ============================================================================


class TestMigrationUpgradeDowngrade:
    """Test migration upgrade and downgrade operations.

    These tests verify that migrations can be applied (upgraded)
    and reversed (downgraded) without errors.
    """

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    def test_upgrades_to_head_and_downgrades_to_base(self, alembic_config: Config) -> None:
        """Test full upgrade to head and downgrade to base.

        Arrange: Start from base (no tables)
        Act: Upgrade to head, then downgrade to base
        Assert: Operations complete without errors
        """
        # Arrange: Start from clean state
        command.downgrade(alembic_config, "base")

        # Act: Apply all migrations
        command.upgrade(alembic_config, "head")

        # Act: Remove all migrations
        command.downgrade(alembic_config, "base")

        # Assert: No exceptions raised (implicit)

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    def test_downgrades_one_step_and_upgrades_back(self, alembic_config: Config) -> None:
        """Test single-step downgrade and re-upgrade.

        Arrange: Upgrade to head
        Act: Downgrade one step, then upgrade back to head
        Assert: Operations complete without errors
        """
        # Arrange: Start from head
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")

        # Act: Downgrade one step
        command.downgrade(alembic_config, "-1")

        # Act: Upgrade back to head
        command.upgrade(alembic_config, "head")

        # Assert: No exceptions raised (implicit)

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    def test_all_migrations_are_reversible(self, alembic_config: Config) -> None:
        """Test that each migration can be reversed.

        Iterates through all migrations and ensures each one can be
        downgraded and re-upgraded without errors.

        Arrange: Get all migration revisions
        Act: Downgrade and upgrade each revision
        Assert: All operations complete without errors
        """
        # Arrange: Get all migration revisions
        script = ScriptDirectory.from_config(alembic_config)
        command.upgrade(alembic_config, "head")
        revisions = list(script.walk_revisions("base", "head"))

        # Act & Assert: Test downgrade/upgrade for each revision
        for revision in revisions:
            if revision.down_revision is None:
                # Base revision, skip
                continue

            # Act: Downgrade one step
            command.downgrade(alembic_config, revision.down_revision)

            # Act: Upgrade back
            command.upgrade(alembic_config, revision.revision)

            # Assert: No exceptions raised (implicit)


class TestMigrationTableCreation:
    """Test that migrations create expected database tables.

    Verifies the initial migration creates the correct schema.
    """

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    async def test_initial_migration_creates_users_table(
        self, test_db_engine: AsyncEngine, alembic_config: Config
    ) -> None:
        """Test that initial migration creates users table.

        Arrange: Start from base, get first migration revision
        Act: Apply first migration
        Assert: Users table exists in database
        """
        # Arrange: Start from base
        command.downgrade(alembic_config, "base")

        # Arrange: Get the first migration revision
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())
        first_revision = revisions[-1].revision if revisions else None

        if not first_revision:
            pytest.skip("No migrations found")

        # Act: Apply first migration only
        command.upgrade(alembic_config, first_revision)

        # Assert: Check that users table exists
        async with test_db_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'users'"
                )
            )
            tables = [row[0] for row in result]
            assert "users" in tables, "Users table not created by migration"

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    async def test_users_table_has_all_required_columns(
        self, test_db_engine: AsyncEngine, alembic_config: Config
    ) -> None:
        """Test that users table has all required columns.

        Arrange: Apply all migrations to head
        Act: Query users table columns
        Assert: All expected columns exist
        """
        # Arrange: Ensure migrations are applied
        command.upgrade(alembic_config, "head")

        # Act: Get column names
        async with test_db_engine.connect() as conn:

            def get_columns(connection):
                inspector = inspect(connection)
                return [col["name"] for col in inspector.get_columns("users")]

            columns = await conn.run_sync(get_columns)

        # Assert: Expected columns exist
        expected_columns = {
            "id",
            "email",
            "username",
            "full_name",
            "is_active",
            "tenant_id",
            "created_at",
            "updated_at",
        }

        assert expected_columns.issubset(set(columns)), (
            f"Missing columns: {expected_columns - set(columns)}"
        )

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    async def test_users_table_has_required_indexes(
        self, test_db_engine: AsyncEngine, alembic_config: Config
    ) -> None:
        """Test that users table has expected indexes.

        Arrange: Apply all migrations to head
        Act: Query users table indexes
        Assert: Email and username indexes exist
        """
        # Arrange: Ensure migrations are applied
        command.upgrade(alembic_config, "head")

        # Act: Get index names
        async with test_db_engine.connect() as conn:

            def get_indexes(connection):
                inspector = inspect(connection)
                return [idx["name"] for idx in inspector.get_indexes("users")]

            indexes = await conn.run_sync(get_indexes)

        # Assert: Check for important indexes
        assert any("email" in idx.lower() for idx in indexes), "Email index not found"
        assert any("username" in idx.lower() for idx in indexes), "Username index not found"


class TestMigrationDataIntegrity:
    """Test that migrations preserve data correctly.

    Verifies that upgrade/downgrade operations don't inadvertently
    lose or corrupt data.
    """

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    async def test_data_persists_after_insert(
        self, test_db_engine: AsyncEngine, alembic_config: Config
    ) -> None:
        """Test that inserted data persists in database.

        Note: Most downgrades will drop tables and lose data.
        This test verifies data exists before any destructive operations.

        Arrange: Apply all migrations, insert test data
        Act: Query for inserted data
        Assert: Data exists as inserted
        """
        # Arrange: Upgrade to head
        command.upgrade(alembic_config, "head")

        # Arrange: Insert test data with unique email and username to avoid conflicts
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        unique_email = f"test-{unique_id}@example.com"
        unique_username = f"testuser{unique_id}"

        # Arrange: Insert test data
        async with test_db_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, username, is_active, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :email, :username, true, NOW(), NOW())"
                ),
                {"email": unique_email, "username": unique_username},
            )

        # Act: Query for inserted data
        async with test_db_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM users WHERE email = :email"), {"email": unique_email}
            )
            count = result.scalar()

        # Assert: Data exists
        assert count == 1, "Test data not persisted in database"


class TestMigrationStructure:
    """Test migration file structure and integrity.

    Verifies that migration files are properly structured
    and don't have common issues like duplicate revisions
    or multiple heads.
    """

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    def test_no_duplicate_revision_ids(self, alembic_config: Config) -> None:
        """Test that there are no duplicate migration revisions.

        Arrange: Get all migration revisions
        Act: Extract revision IDs
        Assert: No duplicate IDs exist
        """
        # Arrange: Get all migration revisions
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        # Act: Get all revision IDs
        revision_ids = [rev.revision for rev in revisions]

        # Assert: Check for duplicates
        assert len(revision_ids) == len(set(revision_ids)), "Duplicate migration revisions found"

    @pytest.mark.skip(reason="Requires test database setup - run manually")
    def test_only_one_migration_head_exists(self, alembic_config: Config) -> None:
        """Test that there is only one migration head.

        Multiple heads indicate branching in migrations, which should
        be avoided. Use 'alembic merge' to fix multiple heads.

        Arrange: Get migration script directory
        Act: Query for heads
        Assert: Exactly one head exists
        """
        # Arrange: Get migration script directory
        script = ScriptDirectory.from_config(alembic_config)

        # Act: Get heads
        heads = script.get_heads()

        # Assert: Only one head exists
        assert len(heads) == 1, (
            f"Multiple migration heads found: {heads}. Use 'alembic merge' to fix."
        )


class TestMigrationBestPractices:
    """Test migration best practices and conventions.

    Verifies that migration files follow quality standards
    and have proper documentation.
    """

    def test_all_migrations_have_docstrings(self, alembic_config: Config) -> None:
        """Test that migrations have descriptive docstrings.

        Arrange: Get all migration revisions
        Act: Check each revision for docstring
        Assert: All revisions have non-empty docstrings
        """
        # Arrange: Get all migration revisions
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        # Act & Assert: Check each revision
        for revision in revisions:
            assert revision.doc is not None and len(revision.doc.strip()) > 0, (
                f"Migration {revision.revision} is missing a docstring"
            )

    def test_migration_messages_are_descriptive(self, alembic_config: Config) -> None:
        """Test that migration messages are descriptive and meaningful.

        Arrange: Get all migration revisions
        Act: Check each revision message
        Assert: Messages are at least 10 characters and not generic
        """
        # Arrange: Get all migration revisions
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        # Act & Assert: Check each revision message
        for revision in revisions:
            # Message should be at least 10 characters
            assert len(revision.doc.strip()) >= 10, (
                f"Migration {revision.revision} has too short description: {revision.doc}"
            )

            # Should not just be generic words
            message_lower = revision.doc.lower()
            assert message_lower != "revision", (
                f"Migration {revision.revision} has generic message 'revision'"
            )
            assert message_lower != "migration", (
                f"Migration {revision.revision} has generic message 'migration'"
            )

    def test_migration_revisions_follow_naming_convention(self, alembic_config: Config) -> None:
        """Test that migration revision IDs follow expected format.

        Arrange: Get all migration revisions
        Act: Check each revision ID format
        Assert: Revision IDs are valid (non-empty strings)
        """
        # Arrange: Get all migration revisions
        script = ScriptDirectory.from_config(alembic_config)
        revisions = list(script.walk_revisions())

        # Act & Assert: Check each revision ID
        for revision in revisions:
            # Revision ID should be a non-empty string
            assert isinstance(revision.revision, str), (
                f"Migration {revision.revision} has invalid revision ID type"
            )
            assert len(revision.revision) > 0, "Migration has empty revision ID"

    def test_migrations_directory_exists(self, alembic_config: Config) -> None:
        """Test that migrations directory exists and is accessible.

        Arrange: Get script directory from config
        Act: Access script directory
        Assert: Directory exists and is accessible
        """
        # Arrange & Act: Get script directory
        script = ScriptDirectory.from_config(alembic_config)

        assert script is not None, "Migrations directory not accessible"
