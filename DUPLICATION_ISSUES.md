# ⚠️ **CRITICAL**: Duplication Creates Inconsistent Behavior

**Date:** 2026-02-27
**Status:** BLOCKING CLEANUP

---

## Problem: Two Email Services in Use Simultaneously

### Current State (BROKEN)

**Container/Production:**
```python
# src/container.py:21, 106-108
from src.external.email_service import EmailService

email_service = providers.Singleton(
    EmailService,
    circuit_breaker=circuit_breaker,
)
```
✅ Uses: `external/email_service.py` (with circuit breaker)

**Temporal Workflows:**
```python
# src/app/tasks/user_tasks.py:10, 31
from src.infrastructure.services import get_email_service

email_service = get_email_service()  # Different instance!
```
❌ Uses: `infrastructure/services/email_service.py` (NO circuit breaker)

---

## Impact

1. **Inconsistent Behavior:**
   - API endpoints use `external/EmailService` (with resilience)
   - Background workflows use `infrastructure/EmailService` (without resilience)

2. **Different Failure Modes:**
   - API calls protected by circuit breaker
   - Workflow calls NOT protected - can cause cascading failures

3. **Configuration Drift:**
   - Two separate email service configurations
   - Changes to one don't affect the other

4. **Testing Issues:**
   - Tests cover both implementations
   - Which one is the "source of truth"?

---

## Root Cause

Temporal workflows **bypass dependency injection** by calling `get_email_service()` directly instead of receiving email service via container.

---

## Solution Options

### Option A: Fix Temporal to Use Container (RECOMMENDED)

**Change `user_tasks.py` to accept email service as parameter:**

```python
# BEFORE (WRONG):
@activity.defn
async def send_welcome_email_activity(user_id: str, email: str):
    email_service = get_email_service()  # Bypasses container!
    await email_service.send_email(...)

# AFTER (CORRECT):
from src.container import Container

@activity.defn
async def send_welcome_email_activity(user_id: str, email: str):
    container = Container()
    email_service = container.email_service()  # Uses container!
    await email_service.send_email(...)
```

**Then DELETE:** `infrastructure/services/email_service.py` (291 lines)

**Pros:**
- Single email service (external/email_service.py)
- Consistent circuit breaker protection
- Proper dependency injection

**Cons:**
- Need to update user_tasks.py
- Container access in Temporal activities

---

### Option B: Consolidate Into services/email_service.py

**Switch container to use `services/email_service.py` instead of `external/email_service.py`**

```python
# src/container.py
from src.infrastructure.services import get_email_service

# Don't use Singleton provider, use factory
email_service = providers.Factory(get_email_service)
```

**Then DELETE:** `external/email_service.py` (106 lines)

**Pros:**
- More complete implementation (SMTP + SendGrid)
- Already used by workflows
- Richer API (HTML, CC, BCC support)

**Cons:**
- Lose circuit breaker integration (would need to add)
- More complex codebase

---

### Option C: Keep Both, Document Intentional Separation

**IF there's a valid reason for two services:**
- API = external/email_service.py (HTTP API calls)
- Workflows = services/email_service.py (SMTP direct)

**Then:** Add circuit breaker to services/email_service.py

**Pros:**
- Separation of concerns

**Cons:**
- Maintains duplication
- Need to explain WHY two services exist

---

## Recommendation: Option A (Fix Temporal)

**Rationale:**
1. Container is the source of truth for dependencies
2. Single email service = easier to maintain
3. Consistent circuit breaker protection everywhere
4. Proper dependency injection pattern

**Implementation Plan:**

### Step 1: Update user_tasks.py
```python
from src.container import Container

@activity.defn
async def send_welcome_email_activity(user_id: str, email: str):
    # Get email service from container (singleton)
    container = Container()
    email_service = container.email_service()

    await email_service.send_email(...)
```

### Step 2: Verify email service interface compatibility

**Check:** Does `external/email_service.py` have `send_email()` method?
```bash
grep "def send_email" src/external/email_service.py
```

**IF NOT:** Add method to match interface OR use adapter pattern

### Step 3: Delete duplicate
```bash
git rm src/infrastructure/services/email_service.py
git rm tests/unit/infrastructure/services/test_email_service_extended.py
```

### Step 4: Update imports
```bash
# Remove from services/__init__.py
git rm src/infrastructure/services/__init__.py  # OR update to remove email exports
```

---

## Verification

After fixing:

```bash
# 1. Check no more imports of services/email_service
grep -r "from src.infrastructure.services import.*email\|from src.infrastructure.services.email_service" src/

# 2. Run all tests
pytest tests/unit -v

# 3. Run integration tests
pytest tests/integration -v

# 4. Verify workflow still works (if temporal available)
# Start temporal server, run workflow
```

---

## Status

- [x] Issue identified
- [ ] Fix user_tasks.py to use container
- [ ] Verify interface compatibility
- [ ] Delete services/email_service.py
- [ ] Update tests
- [ ] Integration test

**Next:** Proceed with Option A implementation
