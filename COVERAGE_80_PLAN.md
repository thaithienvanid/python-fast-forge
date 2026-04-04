# Coverage 80%+ Implementation Plan

**Current Status:** 51.18% branch coverage (2332 missed statements, 55 partial branches)
**Target:** 80%+ branch coverage
**Gap to Close:** 28.82% (approximately 1,474 lines to cover)

## Executive Summary

To reach 80%+ coverage, we need to strategically test files with:
1. **High line count** (more impact per test file)
2. **Low current coverage** (biggest gaps)
3. **Core functionality** (critical business logic)

## Coverage Gap Analysis

### Critical Files Needing Tests (0-30% coverage)

| File | Lines | Current % | Missing | Priority | Est. Tests |
|------|-------|-----------|---------|----------|------------|
| `src/app/command_handlers/__init__.py` | 93 | 0% | 93 | HIGH | 15-20 |
| `src/app/commands/__init__.py` | 22 | 0% | 22 | MEDIUM | 5-8 |
| `src/app/queries/__init__.py` | 41 | 0% | 41 | MEDIUM | 8-10 |
| `src/app/query_handlers/__init__.py` | 84 | 0% | 84 | HIGH | 15-18 |
| `src/infrastructure/messaging/*.py` | 456 | 0% | 456 | LOW | 40-50 |
| `src/infrastructure/plugins/*.py` | 574 | 0% | 574 | LOW | 50-60 |
| `src/infrastructure/realtime/websocket_manager.py` | 103 | 17% | 79 | MEDIUM | 10-15 |
| `src/infrastructure/services/email_service.py` | 62 | 18% | 47 | HIGH | 8-12 |
| `src/infrastructure/repositories/base_repository.py` | 117 | 18% | 91 | HIGH | 15-20 |
| `src/app/usecases/user_usecases.py` | 160 | 19% | 118 | HIGH | 20-30 |

### Medium Coverage Files (30-60% coverage)

| File | Lines | Current % | Missing | Priority | Est. Tests |
|------|-------|-----------|---------|----------|------------|
| `src/presentation/api/middleware/error_handling.py` | 60 | 26% | 42 | HIGH | 8-12 |
| `src/presentation/api/middleware/security_headers.py` | 19 | 26% | 13 | MEDIUM | 4-6 |
| `src/infrastructure/security/api_signature.py` | 52 | 27% | 35 | MEDIUM | 6-10 |
| `src/presentation/api/__init__.py` | 51 | 34% | 33 | MEDIUM | 5-8 |
| `src/infrastructure/compliance/iso27001.py` | 149 | 41% | 73 | MEDIUM | 12-18 |
| `src/infrastructure/compliance/hipaa.py` | 107 | 42% | 58 | MEDIUM | 10-15 |
| `src/infrastructure/compliance/soc2.py` | 171 | 47% | 80 | MEDIUM | 15-20 |
| `src/infrastructure/compliance/manager.py` | 47 | 47% | 25 | HIGH | 5-8 |
| `src/infrastructure/compliance/gdpr.py` | 156 | 51% | 65 | MEDIUM | 10-15 |

## Strategic Implementation Plan

### Phase 1: Quick Wins (Target: 60% coverage)
**Focus:** High-impact, medium-complexity files
**Effort:** 2-3 hours
**Coverage Gain:** ~9%

1. ✅ **Fix failing tests** (COMPLETED)
   - Fixed 3 unit tests
   - Current: 1065/1065 passing

2. 🔄 **Core Use Cases** (IN PROGRESS - Agent working)
   - `test_user_usecases_extended.py` - 40+ tests
   - Coverage gain: ~3%

3. **Repository Layer**
   - `test_base_repository_extended.py` - 20 tests
   - Coverage gain: ~2%

4. **Email Service**
   - `test_email_service_extended.py` - 12 tests
   - Coverage gain: ~1%

5. **Middleware**
   - `test_error_handling_extended.py` - 12 tests
   - Coverage gain: ~1.5%

6. **Compliance Manager**
   - `test_compliance_manager_extended.py` - 8 tests
   - Coverage gain: ~1.5%

### Phase 2: Core Compliance (Target: 70% coverage)
**Focus:** Security-critical compliance modules
**Effort:** 2-3 hours
**Coverage Gain:** ~10%

7. **HIPAA Compliance** - Priority: HIGH
   - Create: `tests/unit/infrastructure/compliance/test_hipaa_extended.py`
   - Tests needed: 15 comprehensive tests
   - Coverage areas:
     - `encrypt_phi()` / `decrypt_phi()` - PHI encryption/decryption
     - `log_audit_event()` - HIPAA audit logging
     - `verify_controls()` - Control verification
     - `generate_compliance_report()` - Compliance reporting
   - Coverage gain: ~2%

8. **GDPR Compliance** - Priority: HIGH
   - Create: `tests/unit/infrastructure/compliance/test_gdpr_extended.py`
   - Tests needed: 15 comprehensive tests
   - Coverage areas:
     - `record_consent()` / `revoke_consent()` - Consent management
     - `log_data_access()` - Data access logging
     - `anonymize_user_data()` - Data anonymization
     - `export_user_data()` - GDPR data export
   - Coverage gain: ~2.5%

9. **SOC2 Compliance** - Priority: MEDIUM
   - Create: `tests/unit/infrastructure/compliance/test_soc2_extended.py`
   - Tests needed: 20 comprehensive tests
   - Coverage areas:
     - `log_change()` - Change management
     - `verify_controls()` - Trust service criteria
     - `generate_compliance_report()` - SOC2 reporting
   - Coverage gain: ~3%

10. **ISO 27001 Compliance** - Priority: MEDIUM
    - Create: `tests/unit/infrastructure/compliance/test_iso27001_extended.py`
    - Tests needed: 18 comprehensive tests
    - Coverage areas:
      - `log_security_event()` - Security event logging
      - `assess_risk()` - Risk assessment
      - `verify_controls()` - Security controls
    - Coverage gain: ~2.5%

### Phase 3: API & Middleware (Target: 75% coverage)
**Focus:** HTTP layer and middleware
**Effort:** 1-2 hours
**Coverage Gain:** ~5%

11. **Security Headers Middleware**
    - Create: `tests/unit/presentation/api/middleware/test_security_headers_extended.py`
    - Tests: 8 tests
    - Coverage: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
    - Coverage gain: ~0.5%

12. **Request Context Middleware**
    - Create: `tests/unit/presentation/api/middleware/test_request_context_extended.py`
    - Tests: 10 tests
    - Coverage: Context management, request ID, correlation
    - Coverage gain: ~1%

13. **API Signature Security**
    - Create: `tests/unit/infrastructure/security/test_api_signature_extended.py`
    - Tests: 12 tests
    - Coverage: Signature generation, validation, replay protection
    - Coverage gain: ~1.5%

14. **API Initialization**
    - Create: `tests/unit/presentation/api/test_api_init_extended.py`
    - Tests: 8 tests
    - Coverage: App creation, lifespan, middleware setup
    - Coverage gain: ~2%

### Phase 4: Advanced Features (Target: 80%+ coverage)
**Focus:** Remaining gaps in core features
**Effort:** 1-2 hours
**Coverage Gain:** ~5%

15. **WebSocket Manager**
    - Create: `tests/unit/infrastructure/realtime/test_websocket_extended.py`
    - Tests: 15 tests
    - Coverage: Connection management, broadcasting, error handling
    - Coverage gain: ~2%

16. **Command/Query Handlers**
    - Create: `tests/unit/app/test_cqrs_handlers_extended.py`
    - Tests: 25 tests
    - Coverage: Command handlers, query handlers, validation
    - Coverage gain: ~3%

### Phase 5: Optional Stretch Goals (Target: 85%+)
**Focus:** Nice-to-have coverage for completeness
**Effort:** Variable

17. **Messaging Queue** (if time permits)
    - Coverage: RabbitMQ, Redis Queue implementations
    - Tests: 40-50 tests
    - Coverage gain: ~4%

18. **Plugin System** (if time permits)
    - Coverage: Plugin manager, built-in plugins
    - Tests: 50-60 tests
    - Coverage gain: ~5%

## Implementation Strategy

### Test Writing Best Practices

1. **AAA Pattern** (Arrange-Act-Assert)
   ```python
   async def test_example(self):
       # Arrange
       mock_repo = AsyncMock()
       use_case = SomeUseCase(mock_repo)

       # Act
       result = await use_case.execute()

       # Assert
       assert result is not None
   ```

2. **Parametrized Tests** for multiple scenarios
   ```python
   @pytest.mark.parametrize(
       ("input", "expected"),
       [(1, "success"), (0, "error")],
   )
   def test_scenarios(self, input, expected):
       ...
   ```

3. **Mock External Dependencies**
   - Use `AsyncMock` for async methods
   - Use `patch()` for imports
   - Mock database, external APIs, file system

4. **Test Edge Cases**
   - None/empty values
   - Boundary values (min/max)
   - Error conditions
   - Concurrent access

5. **Coverage-Driven Development**
   - Run coverage after each test file
   - Target specific uncovered lines
   - Use `--cov-report=html` to visualize gaps

## Progress Tracking

### Coverage Milestones ✅ **COMPLETED**

- [x] **Baseline:** 51.18% (January 2026)
- [x] **Phase 1 Complete:** 56.36% (Quick wins) - +5.18%
- [x] **Phase 2 Complete:** 66.70% (CQRS handlers) - +10.34%
- [x] **Phase 3 Complete:** 74.50% (Messaging & resilience) - +7.80%
- [x] **Phase 4 Complete:** 80.15% (Compliance & advanced) - +5.65% ✅ **TARGET ACHIEVED**

**Final Achievement: 80.15% branch coverage (+28.97% from baseline)**

### Test File Tracking

#### Phase 1: Quick Wins ✅ COMPLETED
- [x] `tests/unit/app/usecases/test_user_usecases_extended.py` (43 tests)
- [x] `tests/unit/infrastructure/repositories/test_base_repository_extended.py` (31 tests)
- [x] `tests/unit/infrastructure/services/test_email_service_extended.py` (23 tests)
- [x] `tests/unit/presentation/api/middleware/test_error_handling_extended.py` (33 tests)
- [x] `tests/unit/infrastructure/compliance/test_compliance_manager_extended.py` (34 tests)

#### Phase 2: CQRS & Handlers ✅ COMPLETED
- [x] `tests/unit/app/test_cqrs_handlers.py` (50+ tests) - Command/Query handlers

#### Phase 3: Infrastructure ✅ COMPLETED
- [x] `tests/unit/infrastructure/resilience/test_circuit_breaker.py` (64 tests)
- [x] `tests/unit/infrastructure/messaging/test_message_queue.py` (75 tests)
- [x] `tests/unit/infrastructure/messaging/test_scheduler.py` (57 tests)
- [x] `tests/unit/infrastructure/plugins/test_plugins.py` (64 tests)

#### Phase 4: Compliance & Advanced ✅ COMPLETED
- [x] `tests/unit/infrastructure/compliance/test_hipaa.py` (37 tests)
- [x] `tests/unit/infrastructure/compliance/test_gdpr.py` (47 tests)
- [x] `tests/unit/infrastructure/compliance/test_soc2.py` (41 tests)
- [x] `tests/unit/infrastructure/compliance/test_iso27001.py` (51 tests)
- [x] `tests/unit/infrastructure/realtime/test_websocket_manager.py` (WebSocket tests)
- [x] `tests/unit/infrastructure/security/test_security_extended.py` (Security tests)
- [x] `tests/unit/presentation/api/middleware/test_middleware_extended.py` (Middleware tests)
- [x] `tests/unit/presentation/api/test_init_extended.py` (API init tests)

## Verification Commands

```bash
# Run all tests with branch coverage
.venv/bin/pytest tests/unit --cov=src --cov-report=term-missing --cov-branch -v

# Generate HTML coverage report
.venv/bin/pytest tests/unit --cov=src --cov-report=html --cov-branch

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Check specific file coverage
.venv/bin/pytest tests/unit --cov=src.app.usecases --cov-report=term-missing --cov-branch

# Run only new extended tests
.venv/bin/pytest tests/unit -k "extended" -v
```

## Success Criteria

✅ **Must Have (80% Target):**
- Branch coverage ≥ 80%
- All unit tests passing (1065+)
- No failing tests
- No skipped critical tests

✅ **Nice to Have:**
- Statement coverage ≥ 85%
- Branch coverage ≥ 85%
- Integration test coverage ≥ 60%
- All compliance modules ≥ 80%

## Risk Mitigation

### Potential Blockers

1. **Complex mocking scenarios**
   - Solution: Use dependency injection patterns
   - Refactor if needed to make testable

2. **External service dependencies**
   - Solution: Mock all external calls
   - Use test doubles for third-party libraries

3. **Database-dependent code**
   - Solution: Use repository mocks
   - Focus on unit tests, not integration

4. **Time constraints**
   - Solution: Prioritize by phase
   - Focus on Phases 1-4 for 80% target

### Fallback Strategy

If we can't reach 80% with planned tests:
1. Add more parametrized tests to existing files
2. Focus on high-impact partial branches
3. Add property-based tests with Hypothesis
4. Test error paths and edge cases more thoroughly

## Time Estimates

- **Phase 1 (Quick Wins):** 2-3 hours → 60% coverage
- **Phase 2 (Compliance):** 2-3 hours → 70% coverage
- **Phase 3 (API/Middleware):** 1-2 hours → 75% coverage
- **Phase 4 (Advanced):** 1-2 hours → 80% coverage

**Total Estimated Time:** 6-10 hours of focused work

## Final Results ✅

### Achievement Summary

**Target:** 80%+ branch coverage
**Achieved:** 80.15% branch coverage ✅
**Improvement:** +28.97% from baseline (51.18% → 80.15%)

### Test Suite Statistics

- **Total Tests:** 1,872 (all passing)
- **Total Test Files Created:** 18 new files
- **Total Lines of Test Code:** 10,000+ lines
- **Branch Coverage:** 80.15%
- **Statement Coverage:** 82.50%
- **Test Execution Time:** ~31 seconds

### High-Impact Coverage Improvements

| Module | Before | After | Gain |
|--------|--------|-------|------|
| CircuitBreaker | 0% | 96.36% | +96.36% |
| MessageQueue | 0% | 100% | +100% |
| Scheduler | 0% | 98.16% | +98.16% |
| PluginManager | 0% | 96.71% | +96.71% |
| GDPRCompliance | 51% | 96.63% | +45.63% |
| HIPAACompliance | 42% | 96.69% | +54.69% |
| ISO27001 | 40% | 95.19% | +55.19% |
| SOC2 | 46% | 98.46% | +52.46% |
| UserUseCases | 19% | 96.43% | +77.43% |
| BaseRepository | 18% | 87.94% | +69.94% |
| EmailService | 18% | 98.78% | +80.78% |

### Commits

1. **Phase 1 Tests** (commit 8abc43e)
   - 5 test files: user_usecases, base_repository, email_service, error_handling, compliance_manager
   - Coverage: 51.18% → 56.36% (+5.18%)

2. **CQRS Handlers** (commit 8f2d863)
   - test_cqrs_handlers.py (50+ tests)
   - Coverage: 56.36% → 66.70% (+10.34%)

3. **Infrastructure & Compliance Suite** (commit 0007c46)
   - 13 test files across resilience, messaging, plugins, compliance, realtime, security, API
   - Coverage: 66.70% → 80.15% (+13.45%)

---

**Last Updated:** 2026-02-27 (Final)
**Created By:** Claude (Sonnet 4.5)
**Status:** ✅ **COMPLETED - 80.15% Coverage Achieved**
