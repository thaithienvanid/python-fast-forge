"""Unit tests for repository mixins.

Tests the reusable query logic mixins using best practices:
- AAA pattern (Arrange-Act-Assert)
- Parametrized tests for similar scenarios
- Descriptive test names
- Isolated tests with proper mocking
- Edge case coverage
"""

import pytest
from sqlalchemy import Select, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.infrastructure.repositories.mixins import (
    CombinedRepositoryMixin,
    OrderingQueryMixin,
    PaginationQueryMixin,
    SoftDeleteQueryMixin,
)


# Test model for mixin testing
class Base(DeclarativeBase):
    """Base for test models."""


class DummyEntity(Base):
    """Dummy entity for mixin testing."""

    __tablename__ = "test_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    deleted_at: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default="2024-01-01")


class TestSoftDeleteQueryMixin:
    """Tests for SoftDeleteQueryMixin.

    Design Pattern: Mixin testing with focused unit tests
    Best Practice: One test class per mixin, descriptive names
    """

    def test_filter_active_excludes_deleted_records(self):
        """Test that filter_active adds WHERE deleted_at IS NULL.

        AAA Pattern:
        - Arrange: Create base query
        - Act: Apply filter_active
        - Assert: Check WHERE clause added
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act
        filtered_query = SoftDeleteQueryMixin.filter_active(base_query, DummyEntity)

        # Assert
        query_str = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at IS NULL" in query_str

    def test_filter_deleted_includes_only_deleted_records(self):
        """Test that filter_deleted adds WHERE deleted_at IS NOT NULL."""
        # Arrange
        base_query = select(DummyEntity)

        # Act
        filtered_query = SoftDeleteQueryMixin.filter_deleted(base_query, DummyEntity)

        # Assert
        query_str = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at IS NOT NULL" in query_str

    @pytest.mark.parametrize(
        ("include_deleted", "expected_clause"),
        [
            (False, "deleted_at IS NULL"),  # Should filter out deleted
            (True, None),  # Should not add any filter
        ],
        ids=["exclude_deleted", "include_deleted"],
    )
    def test_apply_soft_delete_filter_parametrized(
        self, include_deleted: bool, expected_clause: str | None
    ):
        """Test apply_soft_delete_filter with different flags.

        Best Practice: Parametrized tests for similar scenarios
        Reduces code duplication and improves test coverage
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act
        filtered_query = SoftDeleteQueryMixin.apply_soft_delete_filter(
            base_query, DummyEntity, include_deleted=include_deleted
        )

        # Assert
        query_str = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))
        if expected_clause:
            assert expected_clause in query_str
        else:
            # Check that WHERE clause is not present (deleted_at will still be in SELECT)
            assert "WHERE" not in query_str or "deleted_at IS" not in query_str

    def test_filter_active_preserves_existing_where_clauses(self):
        """Test that filter_active doesn't remove existing WHERE clauses.

        Edge Case: Ensure mixin doesn't interfere with existing filters
        """
        # Arrange
        base_query = select(DummyEntity).where(DummyEntity.name == "test")

        # Act
        filtered_query = SoftDeleteQueryMixin.filter_active(base_query, DummyEntity)

        # Assert
        query_str = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))
        assert "name = 'test'" in query_str  # Original WHERE preserved
        assert "deleted_at IS NULL" in query_str  # New WHERE added

    def test_filter_active_returns_select_type(self):
        """Test that filter_active returns Select type for chaining.

        Best Practice: Type safety verification
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act
        result = SoftDeleteQueryMixin.filter_active(base_query, DummyEntity)

        # Assert
        assert isinstance(result, Select)


class TestPaginationQueryMixin:
    """Tests for PaginationQueryMixin.

    Best Practice: Comprehensive edge case coverage
    """

    @pytest.mark.parametrize(
        ("skip", "limit", "expected_offset", "expected_limit"),
        [
            (0, 10, "0", "10"),  # First page
            (10, 10, "10", "10"),  # Second page
            (100, 50, "100", "50"),  # Large offset
            (0, 1, "0", "1"),  # Single item
        ],
        ids=["first_page", "second_page", "large_offset", "single_item"],
    )
    def test_apply_pagination_with_valid_values(
        self, skip: int, limit: int, expected_offset: str, expected_limit: str
    ):
        """Test pagination with various valid skip/limit combinations.

        Best Practice: Parametrized tests for different scenarios
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act
        paginated_query = PaginationQueryMixin.apply_pagination(base_query, skip=skip, limit=limit)

        # Assert
        query_str = str(paginated_query.compile(compile_kwargs={"literal_binds": True}))
        assert f"LIMIT {expected_limit}" in query_str
        assert f"OFFSET {expected_offset}" in query_str

    @pytest.mark.parametrize(
        ("skip", "limit", "error_msg"),
        [
            (-1, 10, "skip must be >= 0"),  # Negative skip
            (0, 0, "limit must be > 0"),  # Zero limit
            (0, -5, "limit must be > 0"),  # Negative limit
            (-10, -10, "skip must be >= 0"),  # Both negative
        ],
        ids=["negative_skip", "zero_limit", "negative_limit", "both_negative"],
    )
    def test_apply_pagination_raises_on_invalid_values(self, skip: int, limit: int, error_msg: str):
        """Test that invalid pagination values raise ValueError.

        Best Practice: Edge case testing with parametrization
        Security: Prevent SQL injection via negative LIMIT/OFFSET
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act & Assert
        with pytest.raises(ValueError, match=error_msg):
            PaginationQueryMixin.apply_pagination(base_query, skip=skip, limit=limit)

    def test_apply_pagination_preserves_existing_clauses(self):
        """Test that pagination doesn't remove existing query clauses.

        Edge Case: Ensure mixin composition works correctly
        """
        # Arrange
        base_query = select(DummyEntity).where(DummyEntity.name == "test").order_by(DummyEntity.id)

        # Act
        paginated_query = PaginationQueryMixin.apply_pagination(base_query, skip=10, limit=20)

        # Assert
        query_str = str(paginated_query.compile(compile_kwargs={"literal_binds": True}))
        assert "name = 'test'" in query_str  # WHERE preserved
        assert "ORDER BY" in query_str  # ORDER BY preserved
        assert "LIMIT 20" in query_str  # LIMIT added
        assert "OFFSET 10" in query_str  # OFFSET added


class TestOrderingQueryMixin:
    """Tests for OrderingQueryMixin.

    Best Practice: Test both ascending and descending order
    """

    @pytest.mark.parametrize(
        ("ascending", "expected_direction"),
        [
            (True, "ASC"),  # Ascending order
            (False, "DESC"),  # Descending order
        ],
        ids=["ascending", "descending"],
    )
    def test_apply_ordering_with_direction(self, ascending: bool, expected_direction: str):
        """Test ordering with different directions.

        Best Practice: Parametrized tests for boolean flags
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act
        ordered_query = OrderingQueryMixin.apply_ordering(
            base_query, DummyEntity.created_at, ascending=ascending
        )

        # Assert
        query_str = str(ordered_query.compile(compile_kwargs={"literal_binds": True}))
        assert "ORDER BY" in query_str
        assert expected_direction in query_str

    def test_apply_ordering_on_different_columns(self):
        """Test ordering on multiple different columns.

        Edge Case: Ensure column parameter works correctly
        """
        # Arrange - Test different columns
        test_cases = [
            (DummyEntity.id, "id"),
            (DummyEntity.name, "name"),
            (DummyEntity.created_at, "created_at"),
        ]

        for column, expected_col_name in test_cases:
            base_query = select(DummyEntity)

            # Act
            ordered_query = OrderingQueryMixin.apply_ordering(base_query, column, ascending=True)

            # Assert
            query_str = str(ordered_query.compile(compile_kwargs={"literal_binds": True}))
            assert expected_col_name in query_str.lower()
            assert "ORDER BY" in query_str

    def test_apply_ordering_preserves_where_clause(self):
        """Test that ordering doesn't remove WHERE clauses.

        Edge Case: Mixin composition
        """
        # Arrange
        base_query = select(DummyEntity).where(DummyEntity.deleted_at.is_(None))

        # Act
        ordered_query = OrderingQueryMixin.apply_ordering(
            base_query, DummyEntity.created_at, ascending=False
        )

        # Assert
        query_str = str(ordered_query.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at IS NULL" in query_str  # WHERE preserved
        assert "ORDER BY" in query_str  # ORDER BY added
        assert "DESC" in query_str  # DESC direction


class TestCombinedRepositoryMixin:
    """Tests for CombinedRepositoryMixin.

    Best Practice: Test mixin composition and interaction
    Design Pattern: Integration testing of multiple mixins
    """

    def test_combined_mixin_has_all_methods(self):
        """Test that CombinedRepositoryMixin inherits all mixin methods.

        Best Practice: Verify interface composition
        """
        # Arrange & Act
        mixin = CombinedRepositoryMixin()

        # Assert - Check all methods are available
        assert hasattr(mixin, "filter_active")
        assert hasattr(mixin, "filter_deleted")
        assert hasattr(mixin, "apply_soft_delete_filter")
        assert hasattr(mixin, "apply_pagination")
        assert hasattr(mixin, "apply_ordering")

    def test_combined_mixin_methods_work_together(self):
        """Test that all mixin methods can be chained together.

        Integration Test: Verify mixin composition works correctly
        Real-world scenario: Typical repository query with all features
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act - Chain all mixin methods together
        combined_query = base_query
        combined_query = CombinedRepositoryMixin.filter_active(combined_query, DummyEntity)
        combined_query = CombinedRepositoryMixin.apply_ordering(
            combined_query, DummyEntity.created_at, ascending=False
        )
        combined_query = CombinedRepositoryMixin.apply_pagination(combined_query, skip=10, limit=20)

        # Assert - All clauses present
        query_str = str(combined_query.compile(compile_kwargs={"literal_binds": True}))
        assert "deleted_at IS NULL" in query_str  # Soft delete filter
        assert "ORDER BY" in query_str  # Ordering
        assert "DESC" in query_str  # Descending order
        assert "LIMIT 20" in query_str  # Pagination limit
        assert "OFFSET 10" in query_str  # Pagination offset

    def test_combined_mixin_order_independence(self):
        """Test that mixin methods can be applied in any order.

        Best Practice: Verify composition is order-independent
        """
        # Arrange
        base_query = select(DummyEntity)

        # Act - Apply in different order
        query1 = base_query
        query1 = CombinedRepositoryMixin.apply_pagination(query1, skip=0, limit=10)
        query1 = CombinedRepositoryMixin.filter_active(query1, DummyEntity)
        query1 = CombinedRepositoryMixin.apply_ordering(query1, DummyEntity.id, ascending=True)

        query2 = base_query
        query2 = CombinedRepositoryMixin.filter_active(query2, DummyEntity)
        query2 = CombinedRepositoryMixin.apply_ordering(query2, DummyEntity.id, ascending=True)
        query2 = CombinedRepositoryMixin.apply_pagination(query2, skip=0, limit=10)

        # Assert - Both produce queries with same clauses (order may differ)
        query1_str = str(query1.compile(compile_kwargs={"literal_binds": True}))
        query2_str = str(query2.compile(compile_kwargs={"literal_binds": True}))

        # Check all clauses present in both
        for expected in ["deleted_at IS NULL", "ORDER BY", "LIMIT 10", "OFFSET 0"]:
            assert expected in query1_str
            assert expected in query2_str


# Performance test marker for optional execution
@pytest.mark.performance
class TestMixinPerformance:
    """Performance tests for mixins.

    Best Practice: Separate performance tests with markers
    Run with: pytest -m performance
    """

    def test_mixin_method_overhead_is_minimal(self):
        """Test that mixin methods don't add significant overhead.

        Best Practice: Performance regression testing
        """
        import timeit

        # Arrange
        setup = """
from sqlalchemy import select
from src.infrastructure.repositories.mixins import SoftDeleteQueryMixin
from tests.unit.infrastructure.repositories.test_mixins import DummyEntity
base_query = select(DummyEntity)
"""

        # Act - Measure time to apply mixin
        mixin_time = timeit.timeit(
            "SoftDeleteQueryMixin.filter_active(base_query, DummyEntity)",
            setup=setup,
            number=10000,
        )

        # Assert - Should be very fast (< 1 second for 10k operations)
        assert mixin_time < 1.0, f"Mixin overhead too high: {mixin_time}s for 10k ops"
