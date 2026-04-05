# API Versioning Strategy

## Overview

This document outlines the API versioning strategy for the Python FastAPI Boilerplate. Proper API versioning ensures backward compatibility, smooth migrations, and clear communication with API consumers about changes.

## Current Versioning Approach

### URL Path Versioning (v1)

The boilerplate currently uses **URL path versioning** with the prefix `/api/v1`:

```python
# src/infrastructure/config.py
api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
```

**Advantages:**
- Clear and explicit versioning
- Easy to route different versions to different codebases
- Visible in documentation (Swagger UI)
- Simple for API consumers to understand

**Current Structure:**
```
/api/v1/users          # User endpoints
/api/v1/health         # Health checks
/health                # Un-versioned health check
```

---

## Versioning Policy

### Semantic Versioning for APIs

We follow **semantic versioning** principles adapted for REST APIs:

- **Major version (v1, v2, v3):** Breaking changes
- **Minor changes:** Additive, backward-compatible changes
- **Patch changes:** Bug fixes, no version change needed

### What Constitutes a Breaking Change?

**Breaking changes require a new major version:**

1. **Removing endpoints**
   ```python
   # v1: DELETE /api/v1/users/{id}
   # v2: Endpoint removed - BREAKING
   ```

2. **Removing response fields**
   ```json
   // v1
   {"id": "123", "name": "John", "email": "john@example.com"}

   // v2 - Removed "email" field - BREAKING
   {"id": "123", "name": "John"}
   ```

3. **Changing field types**
   ```json
   // v1
   {"id": "123"}  // String

   // v2 - Changed to integer - BREAKING
   {"id": 123}
   ```

4. **Changing endpoint behavior**
   ```python
   # v1: Soft delete (sets deleted_at)
   DELETE /api/v1/users/{id}

   # v2: Hard delete (permanent) - BREAKING
   DELETE /api/v2/users/{id}
   ```

5. **Renaming fields**
   ```json
   // v1
   {"full_name": "John Doe"}

   // v2 - Renamed field - BREAKING
   {"name": "John Doe"}
   ```

6. **Making optional fields required**
   ```python
   # v1: full_name is optional
   POST /api/v1/users {"email": "...", "username": "..."}

   # v2: full_name now required - BREAKING
   POST /api/v2/users {"email": "...", "username": "...", "full_name": "..."}
   ```

7. **Changing authentication requirements**
   ```python
   # v1: Public endpoint
   GET /api/v1/users

   # v2: Requires authentication - BREAKING
   GET /api/v2/users  # Requires Authorization header
   ```

### Non-Breaking Changes (No Version Bump)

**These changes are backward-compatible:**

1. **Adding new endpoints**
   ```python
   # v1: Existing endpoints
   GET /api/v1/users
   POST /api/v1/users

   # v1: Add new endpoint - NOT BREAKING
   GET /api/v1/users/search
   ```

2. **Adding optional request fields**
   ```python
   # v1: Only email and username required
   POST /api/v1/users {"email": "...", "username": "..."}

   # v1: Add optional field - NOT BREAKING
   POST /api/v1/users {"email": "...", "username": "...", "phone": "..."}
   ```

3. **Adding response fields**
   ```json
   // v1
   {"id": "123", "name": "John"}

   // v1: Add new field - NOT BREAKING
   {"id": "123", "name": "John", "created_at": "2025-01-01T00:00:00Z"}
   ```

4. **Expanding enum values**
   ```python
   # v1: status can be "active" or "inactive"
   {"status": "active"}

   # v1: Add "pending" - NOT BREAKING
   {"status": "pending"}  # Clients should handle unknown values gracefully
   ```

5. **Bug fixes**
   ```python
   # v1: Fix incorrect validation logic
   # This is a patch, not a version change
   ```

---

## Implementation Guide

### Step 1: Creating a New API Version

When breaking changes are needed, create a new API version:

```bash
# 1. Create new version directory
mkdir -p src/presentation/api/v2
mkdir -p src/presentation/api/v2/endpoints

# 2. Copy router structure from v1
cp src/presentation/api/v1/__init__.py src/presentation/api/v2/
cp src/presentation/api/v1/endpoints/users.py src/presentation/api/v2/endpoints/

# 3. Update imports and make breaking changes
```

### Step 2: Register New Version in API

```python
# src/presentation/api/__init__.py
from src.presentation.api.v1 import api_router as api_v1_router
from src.presentation.api.v2 import api_router as api_v2_router  # New

def create_app() -> FastAPI:
    app = FastAPI(...)

    # Register both versions
    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(api_v2_router, prefix="/api/v2")  # New

    return app
```

### Step 3: Update Configuration

```python
# src/infrastructure/config.py
class Settings(BaseSettings):
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    api_v2_prefix: str = Field(default="/api/v2", alias="API_V2_PREFIX")  # New
```

### Step 4: Document Differences

Create a migration guide for API consumers:

```markdown
# docs/how-to/migrate-v1-to-v2.md

## Migrating from v1 to v2

### Breaking Changes

1. **User email field removed**
   - **v1:** `GET /api/v1/users/{id}` returns `{"id": "...", "email": "..."}`
   - **v2:** `GET /api/v2/users/{id}` returns `{"id": "...", "username": "..."}`
   - **Migration:** Use `GET /api/v2/users/{id}/email` to get email separately

2. **Delete endpoint behavior changed**
   - **v1:** Soft delete (recoverable)
   - **v2:** Hard delete (permanent)
   - **Migration:** Use `POST /api/v2/users/{id}/archive` for soft delete
```

---

## Deprecation Policy

### Deprecation Timeline

1. **Announce deprecation:** At least 6 months before removal
2. **Add deprecation warnings:** Return deprecation header
3. **Support window:** Maintain deprecated version for 12 months minimum
4. **Sunset:** Remove after support window expires

### Deprecation Headers

Add custom headers to deprecated endpoints:

```python
# src/presentation/api/v1/endpoints/users.py
from fastapi import Response

@router.get("/{user_id}")
async def get_user(user_id: UUID, response: Response):
    """Get user by ID.

    **DEPRECATED:** This endpoint will be removed in v3.0 (2026-06-01).
    Please migrate to /api/v2/users/{id} which includes additional fields.
    """
    # Add deprecation headers
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Sat, 01 Jun 2026 00:00:00 GMT"
    response.headers["Link"] = '</api/v2/users/{id}>; rel="successor-version"'

    # ... existing code
```

### Deprecation Announcement Template

```markdown
## API Deprecation Notice: v1 User Endpoints

**Effective Date:** 2025-12-01
**Sunset Date:** 2026-06-01

### Affected Endpoints
- `GET /api/v1/users/{id}`
- `POST /api/v1/users`

### Migration Path
Use v2 endpoints: `/api/v2/users/*`

### Changes in v2
1. Email field moved to separate endpoint
2. Added pagination to list endpoints
3. Improved error responses

### Support
Contact: api-support@example.com
Migration guide: https://docs.example.com/migrate-v1-to-v2
```

---

## Version Detection & Routing

### Client Version Header (Optional)

Allow clients to specify version via header (in addition to URL):

```python
# src/presentation/api/dependencies.py
from fastapi import Header, HTTPException

async def get_api_version(
    x_api_version: str | None = Header(None, alias="X-API-Version")
) -> str:
    """Get API version from header or default to latest."""
    if x_api_version is None:
        return "v2"  # Default to latest

    if x_api_version not in ["v1", "v2"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported API version: {x_api_version}"
        )

    return x_api_version
```

---

## Testing Strategy

### Version-Specific Tests

Organize tests by version:

```
tests/
├── integration/
│   ├── v1/
│   │   ├── test_users_v1.py
│   │   └── test_auth_v1.py
│   └── v2/
│       ├── test_users_v2.py
│       └── test_auth_v2.py
```

### Backward Compatibility Tests

Create tests that verify v1 behavior remains unchanged:

```python
# tests/integration/v1/test_backward_compatibility.py
import pytest

def test_v1_user_response_format(client):
    """Verify v1 response format hasn't changed."""
    response = client.get("/api/v1/users/123")

    assert response.status_code == 200
    data = response.json()

    # Verify required fields still exist
    assert "id" in data
    assert "email" in data
    assert "username" in data
    assert "created_at" in data

    # Verify field types haven't changed
    assert isinstance(data["id"], str)
    assert isinstance(data["email"], str)
```

---

## Documentation

### OpenAPI/Swagger

Version docs are automatically separated in Swagger UI:

```python
# src/presentation/api/__init__.py
app = FastAPI(
    title="Python FastAPI Boilerplate",
    version="2.0.0",  # Overall API version
    openapi_tags=[
        {
            "name": "v1-users",
            "description": "User endpoints (v1) - **DEPRECATED**",
        },
        {
            "name": "v2-users",
            "description": "User endpoints (v2) - Current",
        },
    ]
)
```

### Version Badge

Add version badges to endpoint descriptions:

```python
@router.get("/{user_id}", tags=["v1-users"])
async def get_user(user_id: UUID):
    """
    Get user by ID.

    **Version:** v1
    **Status:** DEPRECATED (Sunset: 2026-06-01)
    **Migration:** Use `/api/v2/users/{id}` instead
    """
```

---

## Best Practices

### 1. Avoid Breaking Changes When Possible

**Prefer additive changes:**
- Add new fields instead of modifying existing ones
- Add new endpoints instead of changing behavior
- Use feature flags for gradual rollouts

### 2. Version at the Macro Level

**Do:**
```
/api/v1/users
/api/v1/orders
/api/v2/users  # New version
/api/v2/orders
```

**Don't:**
```
/api/users/v1
/api/users/v2  # Inconsistent
/api/orders
```

### 3. Keep Versions Consistent

When releasing v2, update **all** endpoints together, not piecemeal:

**Do:**
```
/api/v2/users
/api/v2/orders
/api/v2/products
```

**Don't:**
```
/api/v2/users
/api/v1/orders  # Confusing mix
/api/v1/products
```

### 4. Document Everything

- Maintain separate API docs for each version
- Provide migration guides
- Include examples of old vs. new formats
- Communicate changes via changelog

### 5. Use Feature Flags for Gradual Rollouts

```python
# src/infrastructure/config.py
enable_v2_search: bool = Field(default=False, alias="ENABLE_V2_SEARCH")

# src/presentation/api/v2/endpoints/users.py
@router.get("/search")
async def search_users(settings: Settings = Depends(get_settings)):
    if not settings.enable_v2_search:
        raise HTTPException(status_code=404, detail="Endpoint not available yet")
    # ... new search logic
```

---

## Monitoring & Analytics

### Track Version Usage

```python
# src/presentation/api/middleware/versioning.py
from starlette.middleware.base import BaseHTTPMiddleware

class VersionTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Extract version from path
        if request.url.path.startswith("/api/v1/"):
            version = "v1"
        elif request.url.path.startswith("/api/v2/"):
            version = "v2"
        else:
            version = "unknown"

        # Log version usage
        logger.info(
            "api_request",
            version=version,
            path=request.url.path,
            method=request.method
        )

        response = await call_next(request)
        response.headers["X-API-Version"] = version
        return response
```

### Version Sunset Alerts

Monitor API usage and alert teams when deprecated versions still have traffic:

```python
# Alert if v1 traffic exceeds threshold after deprecation date
if version == "v1" and datetime.now() > DEPRECATION_DATE:
    if v1_request_rate > THRESHOLD:
        send_alert("v1 API still has significant traffic")
```

---

## Checklist for New Version Release

- [ ] Document all breaking changes
- [ ] Create migration guide
- [ ] Update OpenAPI/Swagger docs
- [ ] Add deprecation headers to old version
- [ ] Update tests for both versions
- [ ] Announce deprecation (email, blog, docs)
- [ ] Set sunset date (minimum 12 months)
- [ ] Monitor version usage metrics
- [ ] Provide support period
- [ ] Remove old version after sunset

---

## Resources

- **RFC 5829:** Link Relations for Simple Version Navigation
- **Semantic Versioning:** https://semver.org
- **API Versioning Best Practices:** https://restfulapi.net/versioning/

## Related Documentation

- [API Reference](../reference/api.md)
- [Deployment Guide](../how-to/deployment.md)
- [Architecture Overview](../reference/architecture.md)
