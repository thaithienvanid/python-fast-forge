"""Tests for ArrayFilter functionality.

Test Organization:
- TestArrayFilterCreation: Filter field creation and metadata
- TestArrayFilterDefaults: Default values and behavior
- TestArrayFilterInFilterSet: Integration with FilterSet
- TestArrayContainsOperator: @> operator tests
- TestArrayOverlapOperator: && operator tests
- TestArrayContainedByOperator: <@ operator tests
- TestArrayLengthOperators: Length comparison operators
- TestArrayFilterApplication: Applying filters to queries
- TestArrayFilterValidation: Type validation
- TestArrayFilterDocumentation: OpenAPI schema
- TestArrayFilterEdgeCases: Edge cases and boundaries
- TestArrayFilterErrors: Error handling
"""

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.infrastructure.filtering import ArrayFilter, FilterSet


# ============================================================================
# Test Models
# ============================================================================


class Base(DeclarativeBase):
    """Base class for test models."""


class Product(Base):
    """Test model with PostgreSQL array fields."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(postgresql.ARRAY(String), nullable=False, default=list)
    categories: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(String), nullable=False, default=list
    )
    prices: Mapped[list[int]] = mapped_column(
        postgresql.ARRAY(Integer), nullable=False, default=list
    )


class ProductFilterSet(FilterSet):
    """Test filterset with comprehensive array filters."""

    model = Product

    # Array contains filters
    tags_contain: list[str] | None = ArrayFilter(
        field_name="tags",
        lookup="array_contains",
        description="Filter products with all specified tags",
    )

    # Array overlap filters
    tags_overlap: list[str] | None = ArrayFilter(
        field_name="tags",
        lookup="array_overlap",
        description="Filter products with any of the specified tags",
    )

    # Array contained by filters
    tags_contained_by: list[str] | None = ArrayFilter(
        field_name="tags",
        lookup="array_contained_by",
        description="Filter products whose tags are all in the specified list",
    )

    # Array length filters
    min_tags: int | None = ArrayFilter(
        field_name="tags",
        lookup="array_length_gte",
        description="Filter products with at least N tags",
    )

    max_tags: int | None = ArrayFilter(
        field_name="tags",
        lookup="array_length_lte",
        description="Filter products with at most N tags",
    )

    exact_tag_count: int | None = ArrayFilter(
        field_name="tags",
        lookup="array_length",
        description="Filter products with exactly N tags",
    )

    # Array on different field
    categories_overlap: list[str] | None = ArrayFilter(
        field_name="categories",
        lookup="array_overlap",
        description="Filter products by category overlap",
    )


# ============================================================================
# Test ArrayFilter Creation
# ============================================================================


class TestArrayFilterCreation:
    """Test ArrayFilter field creation and metadata."""

    def test_creates_field_with_proper_metadata(self) -> None:
        """Test ArrayFilter creates Field with filter metadata.

        Arrange: Create ArrayFilter with specific parameters
        Act: Access filter metadata
        Assert: Metadata is correctly set
        """
        # Arrange & Act
        filter_field = ArrayFilter(
            field_name="tags",
            lookup="array_contains",
            description="Test array filter",
        )

        # Assert
        assert filter_field.default is None
        assert filter_field.description == "Test array filter"
        assert "_filter" in filter_field.json_schema_extra
        assert filter_field.json_schema_extra["_filter"].field_name == "tags"
        assert filter_field.json_schema_extra["_filter"].lookup == "array_contains"

    def test_creates_field_with_array_overlap_lookup(self) -> None:
        """Test ArrayFilter creates field with array_overlap lookup.

        Arrange: Create ArrayFilter with array_overlap
        Act: Access lookup type
        Assert: Lookup is array_overlap
        """
        # Arrange
        filter_field = ArrayFilter(
            field_name="tags",
            lookup="array_overlap",
            description="Overlap filter",
        )

        # Act
        filter_descriptor = filter_field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.lookup == "array_overlap"

    def test_creates_field_with_array_contained_by_lookup(self) -> None:
        """Test ArrayFilter creates field with array_contained_by lookup.

        Arrange: Create ArrayFilter with array_contained_by
        Act: Access lookup type
        Assert: Lookup is array_contained_by
        """
        # Arrange
        filter_field = ArrayFilter(
            field_name="tags",
            lookup="array_contained_by",
            description="Contained by filter",
        )

        # Act
        filter_descriptor = filter_field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.lookup == "array_contained_by"

    def test_creates_field_with_array_length_lookup(self) -> None:
        """Test ArrayFilter creates field with array_length lookup.

        Arrange: Create ArrayFilter with array_length
        Act: Access lookup type
        Assert: Lookup is array_length
        """
        # Arrange
        filter_field = ArrayFilter(
            field_name="tags",
            lookup="array_length",
            description="Exact length filter",
        )

        # Act
        filter_descriptor = filter_field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.lookup == "array_length"

    def test_creates_field_with_array_length_gte_lookup(self) -> None:
        """Test ArrayFilter creates field with array_length_gte lookup.

        Arrange: Create ArrayFilter with array_length_gte
        Act: Access lookup type
        Assert: Lookup is array_length_gte
        """
        # Arrange
        filter_field = ArrayFilter(
            field_name="tags",
            lookup="array_length_gte",
            description="Min length filter",
        )

        # Act
        filter_descriptor = filter_field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.lookup == "array_length_gte"

    def test_creates_field_with_array_length_lte_lookup(self) -> None:
        """Test ArrayFilter creates field with array_length_lte lookup.

        Arrange: Create ArrayFilter with array_length_lte
        Act: Access lookup type
        Assert: Lookup is array_length_lte
        """
        # Arrange
        filter_field = ArrayFilter(
            field_name="tags",
            lookup="array_length_lte",
            description="Max length filter",
        )

        # Act
        filter_descriptor = filter_field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.lookup == "array_length_lte"

    def test_stores_description_for_openapi(self) -> None:
        """Test ArrayFilter stores description for OpenAPI docs.

        Arrange: Create ArrayFilter with description
        Act: Access description
        Assert: Description is stored in Field
        """
        # Arrange
        description = "Filter products by tags"
        filter_field = ArrayFilter(
            field_name="tags",
            lookup="array_contains",
            description=description,
        )

        # Act & Assert
        assert filter_field.description == description


# ============================================================================
# Test ArrayFilter Defaults
# ============================================================================


class TestArrayFilterDefaults:
    """Test ArrayFilter default values and behavior."""

    def test_defaults_to_array_contains_lookup(self) -> None:
        """Test ArrayFilter defaults to array_contains when lookup not specified.

        Arrange: Create ArrayFilter without specifying lookup
        Act: Access lookup type
        Assert: Lookup defaults to array_contains
        """
        # Arrange
        filter_field = ArrayFilter()

        # Act
        filter_descriptor = filter_field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.lookup == "array_contains"

    def test_defaults_to_none_value(self) -> None:
        """Test ArrayFilter defaults to None value.

        Arrange: Create ArrayFilter
        Act: Access default value
        Assert: Default is None
        """
        # Arrange
        filter_field = ArrayFilter(field_name="tags")

        # Act & Assert
        assert filter_field.default is None

    def test_allows_none_field_name(self) -> None:
        """Test ArrayFilter allows None field_name (inferred later).

        Arrange: Create ArrayFilter without field_name
        Act: Access field_name
        Assert: Field name is None
        """
        # Arrange
        filter_field = ArrayFilter(lookup="array_contains")

        # Act
        filter_descriptor = filter_field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.field_name is None

    def test_allows_none_description(self) -> None:
        """Test ArrayFilter allows None description.

        Arrange: Create ArrayFilter without description
        Act: Access description
        Assert: Description is None
        """
        # Arrange
        filter_field = ArrayFilter(field_name="tags")

        # Act & Assert
        assert filter_field.description is None


# ============================================================================
# Test ArrayFilter in FilterSet
# ============================================================================


class TestArrayFilterInFilterSet:
    """Test ArrayFilter integration with FilterSet."""

    def test_single_array_filter_in_filterset(self) -> None:
        """Test single ArrayFilter works in FilterSet.

        Arrange: Create ProductFilterSet with tags_contain
        Act: Access filter value
        Assert: Value is set correctly
        """
        # Arrange
        tags = ["python", "fastapi"]

        # Act
        filterset = ProductFilterSet(tags_contain=tags)

        # Assert
        assert filterset.tags_contain == tags
        assert filterset.tags_overlap is None

    def test_multiple_array_filters_in_filterset(self) -> None:
        """Test multiple ArrayFilters work together in FilterSet.

        Arrange: Create ProductFilterSet with multiple filters
        Act: Access filter values
        Assert: All values are set correctly
        """
        # Arrange
        tags_contain = ["python", "fastapi"]
        tags_overlap = ["rust", "go"]
        min_tags = 2

        # Act
        filterset = ProductFilterSet(
            tags_contain=tags_contain,
            tags_overlap=tags_overlap,
            min_tags=min_tags,
        )

        # Assert
        assert filterset.tags_contain == tags_contain
        assert filterset.tags_overlap == tags_overlap
        assert filterset.min_tags == min_tags

    def test_accepts_list_with_multiple_values(self) -> None:
        """Test ArrayFilter accepts list with multiple string values.

        Arrange: Create list with 3 tags
        Act: Create filterset with tags
        Assert: All tags are stored
        """
        # Arrange
        tags = ["python", "fastapi", "postgresql"]

        # Act
        filterset = ProductFilterSet(tags_contain=tags)

        # Assert
        assert len(filterset.tags_contain) == 3
        assert "python" in filterset.tags_contain
        assert "fastapi" in filterset.tags_contain
        assert "postgresql" in filterset.tags_contain

    def test_accepts_integer_value_for_length_filter(self) -> None:
        """Test ArrayFilter accepts integer for length filters.

        Arrange: Create integer value for min_tags
        Act: Create filterset with min_tags
        Assert: Integer value is stored
        """
        # Arrange
        min_tags = 5

        # Act
        filterset = ProductFilterSet(min_tags=min_tags)

        # Assert
        assert filterset.min_tags == 5
        assert isinstance(filterset.min_tags, int)

    def test_different_fields_with_same_type(self) -> None:
        """Test ArrayFilters on different fields work independently.

        Arrange: Create filters for tags and categories
        Act: Create filterset with both
        Assert: Both filters are set independently
        """
        # Arrange
        tags = ["python"]
        categories = ["backend", "api"]

        # Act
        filterset = ProductFilterSet(
            tags_contain=tags,
            categories_overlap=categories,
        )

        # Assert
        assert filterset.tags_contain == tags
        assert filterset.categories_overlap == categories


# ============================================================================
# Test Array Contains Operator
# ============================================================================


class TestArrayContainsOperator:
    """Test array_contains operator (@>)."""

    def test_generates_contains_expression_for_single_value(self) -> None:
        """Test array_contains generates SQL for single value.

        Arrange: Get filter descriptor for tags_contain
        Act: Generate expression for single tag
        Assert: Expression is not None
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_contain"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)

        # Assert
        assert expr is not None

    def test_generates_contains_expression_for_multiple_values(self) -> None:
        """Test array_contains generates SQL for multiple values.

        Arrange: Get filter descriptor for tags_contain
        Act: Generate expression for multiple tags
        Assert: Expression is not None
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_contain"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python", "fastapi", "postgresql"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)

        # Assert
        assert expr is not None

    def test_contains_uses_sqlalchemy_contains_method(self) -> None:
        """Test array_contains uses SQLAlchemy contains() method.

        Arrange: Get filter descriptor and column
        Act: Generate expression and compile to SQL
        Assert: SQL contains expected operator
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_contain"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python", "fastapi"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)
        expr_str = str(
            expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )

        # Assert: PostgreSQL @> operator should be in the compiled SQL
        assert "@>" in expr_str or "contains" in expr_str.lower()


# ============================================================================
# Test Array Overlap Operator
# ============================================================================


class TestArrayOverlapOperator:
    """Test array_overlap operator (&&)."""

    def test_generates_overlap_expression_for_single_value(self) -> None:
        """Test array_overlap generates SQL for single value.

        Arrange: Get filter descriptor for tags_overlap
        Act: Generate expression for single tag
        Assert: Expression is not None
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_overlap"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)

        # Assert
        assert expr is not None

    def test_generates_overlap_expression_for_multiple_values(self) -> None:
        """Test array_overlap generates SQL for multiple values.

        Arrange: Get filter descriptor for tags_overlap
        Act: Generate expression for multiple tags
        Assert: Expression is not None
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_overlap"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python", "rust", "go"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)

        # Assert
        assert expr is not None

    def test_overlap_uses_sqlalchemy_overlap_method(self) -> None:
        """Test array_overlap uses SQLAlchemy overlap() method.

        Arrange: Get filter descriptor and column
        Act: Generate expression and compile to SQL
        Assert: SQL contains expected operator
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_overlap"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python", "rust"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)
        expr_str = str(
            expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )

        # Assert: PostgreSQL && operator should be in the compiled SQL
        assert "&&" in expr_str or "overlap" in expr_str.lower()


# ============================================================================
# Test Array Contained By Operator
# ============================================================================


class TestArrayContainedByOperator:
    """Test array_contained_by operator (<@)."""

    def test_generates_contained_by_expression(self) -> None:
        """Test array_contained_by generates SQL expression.

        Arrange: Get filter descriptor for tags_contained_by
        Act: Generate expression
        Assert: Expression is not None
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_contained_by"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python", "fastapi", "django", "flask"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)

        # Assert
        assert expr is not None

    def test_contained_by_uses_sqlalchemy_contained_by_method(self) -> None:
        """Test array_contained_by uses SQLAlchemy contained_by() method.

        Arrange: Get filter descriptor and column
        Act: Generate expression and compile to SQL
        Assert: SQL contains expected operator
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_contained_by"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = ["python", "fastapi", "django"]

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)
        expr_str = str(
            expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )

        # Assert: PostgreSQL <@ operator should be in the compiled SQL
        assert "<@" in expr_str or "contained" in expr_str.lower()


# ============================================================================
# Test Array Length Operators
# ============================================================================


class TestArrayLengthOperators:
    """Test array length comparison operators."""

    def test_array_length_exact_generates_expression(self) -> None:
        """Test array_length generates exact match expression.

        Arrange: Get filter descriptor for exact_tag_count
        Act: Generate expression for exact count
        Assert: Expression contains array_length and equals
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["exact_tag_count"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = 3

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)
        expr_str = str(expr.compile(compile_kwargs={"literal_binds": True}))

        # Assert
        assert expr is not None
        assert "array_length" in expr_str.lower()
        assert "=" in expr_str

    def test_array_length_gte_generates_expression(self) -> None:
        """Test array_length_gte generates >= expression.

        Arrange: Get filter descriptor for min_tags
        Act: Generate expression for min count
        Assert: Expression contains array_length and >=
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["min_tags"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = 2

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)
        expr_str = str(expr.compile(compile_kwargs={"literal_binds": True}))

        # Assert
        assert expr is not None
        assert "array_length" in expr_str.lower()
        assert ">=" in expr_str

    def test_array_length_lte_generates_expression(self) -> None:
        """Test array_length_lte generates <= expression.

        Arrange: Get filter descriptor for max_tags
        Act: Generate expression for max count
        Assert: Expression contains array_length and <=
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["max_tags"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = 10

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)
        expr_str = str(expr.compile(compile_kwargs={"literal_binds": True}))

        # Assert
        assert expr is not None
        assert "array_length" in expr_str.lower()
        assert "<=" in expr_str

    def test_array_length_with_zero_value(self) -> None:
        """Test array_length works with zero count.

        Arrange: Get filter descriptor for exact_tag_count
        Act: Generate expression for zero length
        Assert: Expression is generated
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["exact_tag_count"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = 0

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)

        # Assert
        assert expr is not None

    def test_array_length_with_large_value(self) -> None:
        """Test array_length works with large count values.

        Arrange: Get filter descriptor for min_tags
        Act: Generate expression for large length
        Assert: Expression is generated
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["min_tags"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags
        value = 1000

        # Act
        expr = filter_descriptor.get_filter_expression(column, value)

        # Assert
        assert expr is not None


# ============================================================================
# Test Array Filter Application
# ============================================================================


class TestArrayFilterApplication:
    """Test applying array filters to SQLAlchemy queries."""

    def test_single_array_contains_filter_adds_where_clause(self) -> None:
        """Test single array_contains filter adds WHERE clause.

        Arrange: Create filterset with tags_contain
        Act: Apply filter to query
        Assert: Query has WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(tags_contain=["python", "fastapi"])
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_array_overlap_filter_adds_where_clause(self) -> None:
        """Test array_overlap filter adds WHERE clause.

        Arrange: Create filterset with tags_overlap
        Act: Apply filter to query
        Assert: Query has WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(tags_overlap=["python", "rust"])
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_array_length_filter_adds_where_clause(self) -> None:
        """Test array_length filter adds WHERE clause.

        Arrange: Create filterset with min_tags
        Act: Apply filter to query
        Assert: Query has WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(min_tags=2)
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_multiple_array_filters_add_combined_where_clause(self) -> None:
        """Test multiple array filters combine with AND.

        Arrange: Create filterset with multiple array filters
        Act: Apply filters to query
        Assert: Query has WHERE clause with multiple conditions
        """
        # Arrange
        filterset = ProductFilterSet(
            tags_overlap=["python", "rust"],
            min_tags=2,
            max_tags=10,
        )
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_none_filter_value_does_not_add_where_clause(self) -> None:
        """Test None filter value doesn't add WHERE clause.

        Arrange: Create filterset with None value
        Act: Apply filter to query
        Assert: Query has no WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(tags_contain=None)
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is None

    def test_empty_filterset_does_not_add_where_clause(self) -> None:
        """Test empty filterset doesn't add WHERE clause.

        Arrange: Create filterset with no filters
        Act: Apply filter to query
        Assert: Query has no WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet()
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is None


# ============================================================================
# Test Array Filter Validation
# ============================================================================


class TestArrayFilterValidation:
    """Test array filter type validation."""

    def test_accepts_list_of_strings_for_array_filter(self) -> None:
        """Test array filter accepts list of strings.

        Arrange: Create list of string tags
        Act: Create filterset with string list
        Assert: Value is list type
        """
        # Arrange
        tags = ["python", "fastapi"]

        # Act
        filterset = ProductFilterSet(tags_contain=tags)

        # Assert
        assert isinstance(filterset.tags_contain, list)
        assert all(isinstance(tag, str) for tag in filterset.tags_contain)

    def test_accepts_single_element_list(self) -> None:
        """Test array filter accepts single element list.

        Arrange: Create list with one tag
        Act: Create filterset with single tag
        Assert: Value is list with one element
        """
        # Arrange
        tags = ["python"]

        # Act
        filterset = ProductFilterSet(tags_contain=tags)

        # Assert
        assert isinstance(filterset.tags_contain, list)
        assert len(filterset.tags_contain) == 1

    def test_accepts_none_value(self) -> None:
        """Test array filter accepts None value.

        Arrange: Pass None for array filter
        Act: Create filterset with None
        Assert: Value is None
        """
        # Arrange & Act
        filterset = ProductFilterSet(tags_contain=None)

        # Assert
        assert filterset.tags_contain is None

    def test_accepts_integer_for_length_filter(self) -> None:
        """Test length filter accepts integer value.

        Arrange: Create integer for length filter
        Act: Create filterset with integer
        Assert: Value is integer
        """
        # Arrange
        min_count = 5

        # Act
        filterset = ProductFilterSet(min_tags=min_count)

        # Assert
        assert isinstance(filterset.min_tags, int)
        assert filterset.min_tags == 5

    def test_preserves_filter_values(self) -> None:
        """Test filterset preserves exact filter values.

        Arrange: Create specific filter values
        Act: Create filterset
        Assert: Values are preserved exactly
        """
        # Arrange
        tags_contain = ["python", "fastapi"]
        tags_overlap = ["rust"]
        min_tags = 2
        max_tags = 10

        # Act
        filterset = ProductFilterSet(
            tags_contain=tags_contain,
            tags_overlap=tags_overlap,
            min_tags=min_tags,
            max_tags=max_tags,
        )

        # Assert
        assert filterset.tags_contain == tags_contain
        assert filterset.tags_overlap == tags_overlap
        assert filterset.min_tags == min_tags
        assert filterset.max_tags == max_tags


# ============================================================================
# Test Array Filter Documentation
# ============================================================================


class TestArrayFilterDocumentation:
    """Test array filter OpenAPI documentation."""

    def test_array_filter_has_description(self) -> None:
        """Test array filter field has description.

        Arrange: Access tags_contain field
        Act: Get description
        Assert: Description exists and is meaningful
        """
        # Arrange
        field = ProductFilterSet.model_fields["tags_contain"]

        # Act
        description = field.description

        # Assert
        assert description is not None
        assert "all specified tags" in description.lower()

    def test_overlap_filter_has_description(self) -> None:
        """Test overlap filter has appropriate description.

        Arrange: Access tags_overlap field
        Act: Get description
        Assert: Description mentions 'any'
        """
        # Arrange
        field = ProductFilterSet.model_fields["tags_overlap"]

        # Act
        description = field.description

        # Assert
        assert description is not None
        assert "any of the specified tags" in description.lower()

    def test_filterset_has_all_array_filter_fields(self) -> None:
        """Test FilterSet contains all defined array filter fields.

        Arrange: Access ProductFilterSet model fields
        Act: Check for expected fields
        Assert: All array filter fields are present
        """
        # Arrange
        fields = ProductFilterSet.model_fields

        # Act & Assert
        assert "tags_contain" in fields
        assert "tags_overlap" in fields
        assert "tags_contained_by" in fields
        assert "min_tags" in fields
        assert "max_tags" in fields
        assert "exact_tag_count" in fields

    def test_filter_metadata_accessible(self) -> None:
        """Test filter metadata is accessible from field.

        Arrange: Access field with filter
        Act: Get filter descriptor from metadata
        Assert: Descriptor has correct attributes
        """
        # Arrange
        field = ProductFilterSet.model_fields["tags_contain"]

        # Act
        filter_descriptor = field.json_schema_extra["_filter"]

        # Assert
        assert filter_descriptor.field_name == "tags"
        assert filter_descriptor.lookup == "array_contains"

    def test_length_filter_descriptions_are_clear(self) -> None:
        """Test length filter descriptions clearly indicate behavior.

        Arrange: Access length filter fields
        Act: Get descriptions
        Assert: Descriptions indicate min/max/exact
        """
        # Arrange
        min_field = ProductFilterSet.model_fields["min_tags"]
        max_field = ProductFilterSet.model_fields["max_tags"]
        exact_field = ProductFilterSet.model_fields["exact_tag_count"]

        # Act & Assert
        assert "at least" in min_field.description.lower()
        assert "at most" in max_field.description.lower()
        assert "exactly" in exact_field.description.lower()


# ============================================================================
# Test Array Filter Edge Cases
# ============================================================================


class TestArrayFilterEdgeCases:
    """Test edge cases for array filters."""

    def test_empty_array_filter_adds_where_clause(self) -> None:
        """Test empty array value still generates WHERE clause.

        Arrange: Create filterset with empty array
        Act: Apply filter to query
        Assert: Query has WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(tags_contain=[])
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_single_element_array_filter(self) -> None:
        """Test single element array filter works.

        Arrange: Create filterset with one-element array
        Act: Apply filter to query
        Assert: Query has WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(tags_contain=["python"])
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_zero_length_filter(self) -> None:
        """Test zero length filter works.

        Arrange: Create filterset with exact_tag_count=0
        Act: Apply filter to query
        Assert: Query has WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(exact_tag_count=0)
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_large_array_filter(self) -> None:
        """Test large array filter works.

        Arrange: Create filterset with many tags
        Act: Apply filter to query
        Assert: Query has WHERE clause
        """
        # Arrange
        many_tags = [f"tag{i}" for i in range(100)]
        filterset = ProductFilterSet(tags_contain=many_tags)
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_array_with_special_characters(self) -> None:
        """Test array filter with special characters in strings.

        Arrange: Create tags with special characters
        Act: Create filterset and generate expression
        Assert: Expression is created successfully
        """
        # Arrange
        special_tags = ["python-3.11", "C++", "F#"]
        filterset = ProductFilterSet(tags_contain=special_tags)
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_array_with_unicode_characters(self) -> None:
        """Test array filter with Unicode characters.

        Arrange: Create tags with Unicode
        Act: Create filterset and generate expression
        Assert: Expression is created successfully
        """
        # Arrange
        unicode_tags = ["Python™", "日本語", "emoji🐍"]
        filterset = ProductFilterSet(tags_contain=unicode_tags)
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None

    def test_combining_all_filter_types(self) -> None:
        """Test combining contains, overlap, and length filters.

        Arrange: Create filterset with all filter types
        Act: Apply filters to query
        Assert: Query has complex WHERE clause
        """
        # Arrange
        filterset = ProductFilterSet(
            tags_contain=["python"],
            tags_overlap=["rust", "go"],
            tags_contained_by=["python", "rust", "go", "java"],
            min_tags=1,
            max_tags=5,
            exact_tag_count=3,
        )
        query = select(Product)

        # Act
        filtered_query = filterset.apply(query, exclude_deleted=False)

        # Assert
        assert filtered_query.whereclause is not None


# ============================================================================
# Test Array Filter Errors
# ============================================================================


class TestArrayFilterErrors:
    """Test error handling in array filters."""

    def test_get_filter_expression_returns_none_for_none_value(self) -> None:
        """Test get_filter_expression returns None when value is None.

        Arrange: Get filter descriptor
        Act: Call get_filter_expression with None
        Assert: Returns None
        """
        # Arrange
        field_info = ProductFilterSet.model_fields["tags_contain"]
        filter_descriptor = field_info.json_schema_extra["_filter"]
        column = Product.tags

        # Act
        expr = filter_descriptor.get_filter_expression(column, None)

        # Assert
        assert expr is None

    def test_filterset_apply_requires_model(self) -> None:
        """Test FilterSet.apply raises error when model not set.

        Arrange: Create FilterSet without model
        Act: Call apply()
        Assert: Raises ValueError
        """

        # Arrange
        class InvalidFilterSet(FilterSet):
            # Intentionally not setting model
            tags: list[str] | None = ArrayFilter()

        filterset = InvalidFilterSet()
        query = select(Product)

        # Act & Assert
        with pytest.raises(ValueError, match="model class variable must be set"):
            filterset.apply(query)

    def test_filterset_get_count_query_requires_model(self) -> None:
        """Test FilterSet.get_count_query raises error when model not set.

        Arrange: Create FilterSet without model
        Act: Call get_count_query()
        Assert: Raises ValueError
        """

        # Arrange
        class InvalidFilterSet(FilterSet):
            # Intentionally not setting model
            tags: list[str] | None = ArrayFilter()

        filterset = InvalidFilterSet()

        # Act & Assert
        with pytest.raises(ValueError, match="model class variable must be set"):
            filterset.get_count_query()
