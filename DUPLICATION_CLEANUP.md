# Code Duplication Cleanup Plan

**Date:** 2026-02-27
**Issue:** Multiple duplicate implementations causing confusion and maintenance burden
**Impact:** ~1,110 lines of dead/duplicate code identified

---

## Executive Summary

**Critical Findings:**
1. ❌ **Circuit Breaker**: 2 complete implementations (only 1 used)
2. ❌ **Email Service**: 3 separate implementations (only 1 used)

**Total Dead Code:** ~1,110 lines across 3 files

**Total Savings:** ~1,110 lines to remove

---

## 1. CRITICAL: Circuit Breaker Duplication

### Current State

| File | Lines | Type | Status |
|------|-------|------|--------|
| `src/infrastructure/patterns/circuit_breaker.py` | 147 | pybreaker wrapper | ✅ **USED in container** |
| `src/infrastructure/resilience/circuit_breaker.py` | 324 | Custom async impl | ❌ **NOT used** (has tests) |

### Analysis

**What's Used (Production):**
```python
# src/container.py:24
from src.infrastructure.patterns.circuit_breaker import CircuitBreakerService

# src/container.py:65
circuit_breaker = providers.Singleton(CircuitBreakerService)

# src/external/email_service.py:10
from src.infrastructure.patterns.circuit_breaker import CircuitBreakerService
```

**What's NOT Used:**
```python
# src/infrastructure/resilience/circuit_breaker.py
# Custom CircuitBreaker implementation (324 lines)
# Has comprehensive tests (64 tests) but NOT integrated into container
```

### Comparison

| Feature | patterns/CB (USED) | resilience/CB (UNUSED) |
|---------|-------------------|----------------------|
| **Library** | pybreaker (external) | Custom async implementation |
| **Lines** | 147 | 324 |
| **Async** | Async wrapper | Native async |
| **Dependencies** | Requires pybreaker | Pure Python |
| **Tests** | None | 64 comprehensive tests |
| **Container** | ✅ Registered | ❌ Not registered |
| **Production** | ✅ Active | ❌ Dead code |

### Decision: REMOVE resilience/circuit_breaker.py

**Rationale:**
1. `patterns/circuit_breaker.py` is already in production
2. Switching would require rewriting email_service.py
3. pybreaker is battle-tested, mature library
4. 64 tests for unused code = maintenance burden

**Action Items:**
- ❌ Delete `src/infrastructure/resilience/circuit_breaker.py` (324 lines)
- ❌ Delete `src/infrastructure/resilience/__init__.py` (exports unused CB)
- ❌ Delete `tests/unit/infrastructure/resilience/test_circuit_breaker.py` (64 tests)
- 📝 Update AUDIT_FINDINGS.md to note consolidation

**Lines Saved:** 324 (source) + ~600 (tests) = **~924 lines**

---

## 2. HIGH: Email Service Triplication

### Current State

| File | Lines | Type | Status |
|------|-------|------|--------|
| `src/external/email_service.py` | 106 | HTTP API wrapper | ✅ **USED in container** |
| `src/infrastructure/services/email_service.py` | 291 | SMTP + SendGrid | ❌ **NOT used** |
| `src/infrastructure/plugins/builtin/email.py` | 495 | Plugin system | ❌ **NOT integrated** |

### Analysis

**What's Used (Production):**
```python
# src/container.py:21
from src.external.email_service import EmailService

# src/container.py:106-108
email_service = providers.Singleton(
    EmailService,
    circuit_breaker=circuit_breaker,
)
```

**What's NOT Used:**

**File 1:** `infrastructure/services/email_service.py` (291 lines)
- Full SMTP + SendGrid implementation
- Has factory `get_email_service()`
- **NEVER imported in container**
- Has 23 comprehensive tests

**File 2:** `infrastructure/plugins/builtin/email.py` (495 lines)
- Plugin framework (EmailPlugin, SMTPEmailPlugin, SendGridEmailPlugin)
- Most complete (attachments, async, HTML)
- **Plugin system not activated**
- No tests for this specific file

### Decision: REMOVE 2 unused implementations

**Rationale:**
1. `external/email_service.py` is simple, working, and in production
2. `services/email_service.py` duplicates functionality - dead code
3. `plugins/email.py` is part of incomplete plugin system

**Action Items:**
- ❌ Delete `src/infrastructure/services/email_service.py` (291 lines)
- ❌ Delete `tests/unit/infrastructure/services/test_email_service_extended.py` (23 tests)
- ⚠️ **Keep** `plugins/builtin/email.py` (for now) - part of larger plugin system
  - Document that plugin system is incomplete/not activated
  - Future: Either complete plugin system OR remove entirely

**Lines Saved (Immediate):** 291 (source) + ~200 (tests) = **~491 lines**

**Lines Saved (Future):** If plugin system removed: +495 lines

---

## 3. Summary of Cleanup

### Files to Delete (Immediate)

| File | Lines | Reason |
|------|-------|--------|
| `src/infrastructure/resilience/circuit_breaker.py` | 324 | Duplicate CB implementation |
| `src/infrastructure/resilience/__init__.py` | ~10 | Exports unused CB |
| `tests/unit/infrastructure/resilience/test_circuit_breaker.py` | ~600 | Tests for unused code |
| `src/infrastructure/services/email_service.py` | 291 | Duplicate email service |
| `tests/unit/infrastructure/services/test_email_service_extended.py` | ~200 | Tests for unused code |

**Total to Delete:** ~1,425 lines

### Files to Keep

| File | Lines | Reason |
|------|-------|--------|
| `src/infrastructure/patterns/circuit_breaker.py` | 147 | ✅ Used in production |
| `src/external/email_service.py` | 106 | ✅ Used in production |
| `src/infrastructure/plugins/builtin/email.py` | 495 | ⚠️ Part of plugin system (incomplete) |

---

## 4. Plugin System Assessment (Future Work)

### Status: INCOMPLETE / NOT ACTIVATED

The plugin system (`src/infrastructure/plugins/`) includes:
- `base.py` - Plugin base classes (318 lines) ✅ **HAS TESTS (64 tests)**
- `manager.py` - Plugin lifecycle management (433 lines) ✅ **HAS TESTS (64 tests)**
- `builtin/email.py` - Email plugin (495 lines) ❌ **NO SPECIFIC TESTS**
- `builtin/storage.py` - Storage plugin (660 lines) ❌ **NO TESTS, 0% coverage**
- `builtin/auth.py` - Auth plugin (651 lines) ❌ **NO TESTS, 0% coverage**

**Coverage:**
- `plugins/base.py`: 100% ✅
- `plugins/manager.py`: 96.71% ✅
- `plugins/builtin/email.py`: 0% ❌
- `plugins/builtin/storage.py`: 0% ❌
- `plugins/builtin/auth.py`: 0% ❌

**Decision: DEFER - Document as Incomplete**

The plugin system has good architecture (base + manager tested) but builtin plugins are:
1. Not integrated into container
2. Not covered by tests
3. Duplicating existing services

**Options:**
- **Option A:** Complete plugin system (add tests, integrate)
- **Option B:** Remove builtin plugins, keep only base + manager for extensibility
- **Option C:** Remove entire plugin system

**Recommendation:** Add to AUDIT_FINDINGS.md as "Feature Gap: Plugin System Incomplete"

---

## 5. Execution Plan

### Phase 1: Circuit Breaker Cleanup (IMMEDIATE)
1. Delete `src/infrastructure/resilience/circuit_breaker.py`
2. Delete `src/infrastructure/resilience/__init__.py`
3. Delete `tests/unit/infrastructure/resilience/test_circuit_breaker.py`
4. Run tests: `pytest tests/unit -v`
5. Commit: "Remove duplicate circuit breaker implementation"

**Estimated Time:** 30 minutes
**Risk:** LOW (unused code)

### Phase 2: Email Service Cleanup (IMMEDIATE)
1. Delete `src/infrastructure/services/email_service.py`
2. Delete `tests/unit/infrastructure/services/test_email_service_extended.py`
3. Run tests: `pytest tests/unit -v`
4. Commit: "Remove duplicate email service implementation"

**Estimated Time:** 30 minutes
**Risk:** LOW (unused code)

### Phase 3: Update Documentation (IMMEDIATE)
1. Update AUDIT_FINDINGS.md - note consolidations
2. Update COVERAGE_80_PLAN.md - note removed tests
3. Add plugin system status to AUDIT_FINDINGS.md

**Estimated Time:** 15 minutes
**Risk:** NONE

### Phase 4: Plugin System Decision (FUTURE)
- Evaluate plugin system usage/need
- Either complete (add tests) OR remove entirely
- Decision deferred to next sprint

**Estimated Time:** 4-6 hours (if completing)
**Risk:** MEDIUM (architectural decision)

---

## 6. Testing Strategy

### After Deletion - Verify:
```bash
# 1. All tests still pass
pytest tests/unit -v

# 2. Coverage unchanged (tests removed for unused code)
pytest tests/unit --cov=src --cov-report=term --cov-branch

# 3. No broken imports
python -m compileall src/

# 4. Container still builds
python -c "from src.container import Container; Container()"
```

---

## 7. Risks & Mitigation

### Risk 1: Breaking Imports
**Mitigation:**
- Check all imports with: `grep -r "resilience.circuit_breaker" src/`
- Already verified: only used in tests (being removed)

### Risk 2: Indirect Usage
**Mitigation:**
- Search for any dynamic imports
- Grep for string references: `grep -r "resilience" src/`

### Risk 3: Coverage Drop
**Mitigation:**
- Coverage may appear to drop (removing tests for unused code)
- Actual coverage of **active code** remains 80.15%
- Document in commit message

---

## 8. Metrics

### Before Cleanup
- Total source lines: 5,187
- Total test lines: ~18,000
- Files with 0% coverage: 4 (builtin plugins)
- Duplicate implementations: 5

### After Cleanup
- Source lines: ~4,572 (-615 lines, -11.9%)
- Test lines: ~17,200 (-800 lines, -4.4%)
- Files with 0% coverage: 3 (builtin plugins - deferred)
- Duplicate implementations: 0 ✅

**Total Cleanup:** ~1,415 lines of dead code removed

---

## Appendix: Verification Commands

```bash
# Find all circuit breaker imports
grep -r "circuit_breaker" src/ --include="*.py" | grep -v "patterns/circuit_breaker"

# Find all email service imports
grep -r "services.email_service\|services/email_service" src/ --include="*.py"

# Check for resilience directory usage
grep -r "from src.infrastructure.resilience" src/ --include="*.py"

# Verify container imports
grep -E "CircuitBreaker|EmailService" src/container.py
```

---

**Status:** Ready for execution
**Approval Required:** Yes (deleting tested code)
**Estimated Total Time:** 1.5 hours
**Risk Level:** LOW (removing dead code)
