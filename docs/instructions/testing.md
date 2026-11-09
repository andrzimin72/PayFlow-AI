## 🧪 PayFlow AI — Testing Guide

**The complete guide to testing the PayFlow AI platform.**

**Version:** 1.0.0  
**Last Updated:** November 2026  
**Maintainer:** Andre Zimin  

---

### 📋 Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Test Suite Structure](#test-suite-structure)
5. [Running Tests](#running-tests)
6. [Test Categories](#test-categories)
7. [Coverage Reporting](#coverage-reporting)
8. [Writing New Tests](#writing-new-tests)
9. [Mocking Strategy](#mocking-strategy)
10. [Fixtures Reference](#fixtures-reference)
11. [Performance Benchmarking](#performance-benchmarking)
12. [CI/CD Integration](#cicd-integration)
13. [Troubleshooting](#troubleshooting)
14. [Test Maintenance](#test-maintenance)
15. [Metrics and Goals](#metrics-and-goals)

---

### 🎯 Testing Philosophy

Testing in PayFlow AI is guided by four principles:

1. **Tests are documentation.** A well-written test explains what the code does and why. If a test is confusing, the code probably is too.

2. **Mock external services, test internal logic.** We never call real PayPal, Hugging Face, or Zapier APIs during tests. We mock at the boundary and verify our logic in isolation.

3. **Integration tests prove composition.** Unit tests verify individual modules; integration tests verify that modules work together correctly. Both are essential.

4. **Performance tests catch regressions.** Latency and throughput are first-class concerns. Benchmarks run alongside functional tests to catch performance degradation early.

---

### 🛠️ Prerequisites

#### Required Software

| Software | Version | Purpose |
|:---|:---|:---|
| Python | 3.9 – 3.11 | Runtime |
| pip | Latest | Package management |
| Docker | 20.10+ | For integration tests (optional) |

#### Install Test Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate        # macOS / Linux
# OR: .venv\Scripts\activate     # Windows

# Install all dependencies (including test tools)
pip install -r requirements-dev.txt
```

This installs:
- `pytest` — test runner
- `pytest-asyncio` — async test support
- `pytest-cov` — coverage reporting
- `pytest-xdist` — parallel test execution
- `pytest-mock` — mocking utilities
- `pytest-benchmark` — performance benchmarking
- `pytest-timeout` — test timeouts
- `httpx` — FastAPI TestClient
- `faker` — realistic test data generation

#### Verify Installation

```bash
pytest --version
# Expected: pytest 7.4.x or higher
```

---

### 🚀 Quick Start

#### Run All Tests (Recommended Starting Point)

```bash
pytest
```

This runs all unit, integration, and performance tests with verbose output and coverage reporting.

#### Common Commands

| Command | What It Does |
|:---|:---|
| `pytest` | Run all tests with coverage |
| `pytest tests/ -v` | Verbose output |
| `pytest tests/ -k "risk"` | Run only tests matching "risk" |
| `pytest tests/ -m "not slow"` | Skip slow tests |
| `pytest tests/ -x` | Stop on first failure |
| `pytest tests/ --lf` | Rerun only last failed tests |
| `pytest tests/ -n auto` | Run tests in parallel |

---

### 📂 Test Suite Structure

```
tests/
├── __init__.py                      # Test utilities and helpers
├── conftest.py                      # Shared fixtures (25+ fixtures)
│
├── test_ai_engine.py                # 17 tests
├── test_paypal_client.py            # 13 tests
├── test_api.py                      # 18 tests
├── test_forecasting.py              # 8 tests
├── test_elastic_manager.py          # 17 tests
├── test_invoice_manager.py          # 12 tests
├── test_dispute_manager.py          # 12 tests
├── test_risk_engine.py              # 47 tests
│
├── integration/                     # Integration tests
│   ├── __init__.py
│   ├── test_data_pipelines.py       # 6 tests
│   ├── test_risk_pipeline.py        # 6 tests
│   ├── test_api_integration.py      # 8 tests
│   └── test_webhook_integration.py  # 10 tests
│
└── performance/                     # Performance benchmarks
    ├── __init__.py
    ├── conftest.py                  # Benchmark fixtures
    ├── test_ai_performance.py       # 12 benchmarks
    ├── test_pipeline_performance.py # 7 benchmarks
    └── test_data_layer_performance.py # 9 benchmarks
```

**Total: 155 tests/benchmarks**
- 97 unit tests
- 30 integration tests
- 28 performance benchmarks

---

### ▶️ Running Tests

#### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_risk_engine.py

# Run a specific test class
pytest tests/test_risk_engine.py::TestCalculateRiskScore

# Run a specific test method
pytest tests/test_risk_engine.py::TestCalculateRiskScore::test_minimum_possible_score
```

#### Filtering Tests

```bash
# By name pattern
pytest -k "risk"              # Tests containing "risk"
pytest -k "not slow"          # Exclude slow tests
pytest -k "webhook or invoice" # Union of patterns

# By marker
pytest -m unit                # Unit tests only
pytest -m integration         # Integration tests only
pytest -m performance         # Performance benchmarks only
pytest -m "not performance"   # Everything except performance
pytest -m "slow and not integration"  # Combined markers
```

#### Parallel Execution

For faster test runs on multi-core machines:

```bash
# Auto-detect CPU cores
pytest -n auto

# Specify number of workers
pytest -n 4
```

⚠️ **Note:** Some tests share module-level state and may not be safe to parallelize. If you see flaky behavior with `-n`, run without parallelism.

#### Stopping Conditions

```bash
# Stop on first failure
pytest -x

# Stop after N failures
pytest --maxfail=3

# Rerun only previously failed tests
pytest --lf

# Rerun all tests, with failed tests first
pytest --ff
```

---

### 📊 Test Categories

#### Unit Tests

**Location:** `tests/test_*.py`  
**Purpose:** Verify individual modules in isolation  
**Characteristics:**
- Fast (< 1 second per test)
- Mock all external dependencies
- Test one behavior per test
- Clear naming: `test_<what>_<condition>_<expected>`

**Example:**
```python
def test_minimum_possible_score(self):
    """Test that minimum inputs produce a score near 0."""
    score = calculate_risk_score(
        anomaly_score=0.0,
        ai_confidence=1.0,
        amount=10.0,
        avg_amount=100.0
    )
    assert 0.0 <= score <= 10.0
```

#### Integration Tests

**Location:** `tests/integration/`  
**Purpose:** Verify modules work together correctly  
**Characteristics:**
- Use in-memory Elasticsearch mock
- Mock external APIs (PayPal, Hugging Face, Zapier)
- Test multi-module flows
- Slower than unit tests (1-5 seconds)
- Marked with `@pytest.mark.integration`

**Example:**
```python
@pytest.mark.integration
def test_full_ingestion_pipeline(
    self, mock_http_get, integration_es_client, mock_classifier
):
    """Verify PayPal → AI → ES → Search flow."""
    raw = paypal_client.fetch_transactions("token")
    categorized = ai_engine.process_transactions(raw, mock_classifier)
    elastic_manager.index_transactions(categorized)
    results = elastic_manager.search_transactions("Adobe")
    assert len(results) >= 1
```

#### Performance Benchmarks

**Location:** `tests/performance/`  
**Purpose:** Measure latency and throughput, catch regressions  
**Characteristics:**
- Use `pytest-benchmark` fixture
- Run multiple iterations (default: 5 rounds)
- Report min/max/mean/median/stddev
- Marked with `@pytest.mark.performance` and `@pytest.mark.slow`
- Have explicit thresholds

**Example:**
```python
@pytest.mark.performance
def test_medium_batch_throughput(
    self, benchmark, fast_mock_classifier, medium_batch_transactions
):
    """Throughput for 100 transactions. Threshold: < 200ms."""
    def categorize_batch():
        return ai_engine.process_transactions(
            medium_batch_transactions, fast_mock_classifier
        )
    result = benchmark(categorize_batch)
    assert len(result) == 100
    assert benchmark.stats.mean < 0.200  # 200ms threshold
```

---

### 📈 Coverage Reporting

#### Generate Coverage Report

```bash
# HTML report (recommended for exploration)
pytest --cov=. --cov-report=html
# Open htmlcov/index.html in your browser

# Terminal report with missing lines
pytest --cov=. --cov-report=term-missing

# XML report (for CI/CD)
pytest --cov=. --cov-report=xml

# All formats at once
pytest --cov=. \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-report=xml
```

#### Coverage Requirements

| Metric | Threshold | Enforced By |
|:---|:---|:---|
| **Minimum coverage** | 70% | `pytest.ini` (`--cov-fail-under=70`) |
| **Target coverage** | 85%+ | Team goal |
| **Current coverage** | ~92% | As of v4.1.0 |

#### What's Excluded from Coverage

Per `pytest.ini`, these are excluded:
- `tests/` directory (test code itself)
- `migrations/` (database migrations)
- Virtual environments
- `__init__.py` files (typically empty)
- Setup scripts

#### Interpreting Coverage Reports

In the HTML report:
- **Green lines** = executed during tests (covered)
- **Red lines** = not executed (uncovered)
- **Yellow lines** = partial coverage (e.g., only one branch of an `if`)
- **Gray lines** = non-executable (comments, imports, blank lines)

**Goal:** Eliminate red lines in critical paths (risk engine, security, AI pipeline).

---

### ✍️ Writing New Tests

#### File Naming Convention

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<descriptive_name>`

#### Test Structure (AAA Pattern)

Every test should follow **Arrange → Act → Assert**:

```python
def test_calculate_risk_score_with_high_anomaly(self):
    # ARRANGE: Set up inputs
    anomaly_score = 0.9
    ai_confidence = 0.3
    amount = 5000.0
    avg_amount = 100.0

    # ACT: Call the function under test
    score = calculate_risk_score(anomaly_score, ai_confidence, amount, avg_amount)

    # ASSERT: Verify the result
    assert score >= 60.0
    assert score <= 100.0
```

#### Use Fixtures for Shared Setup

```python
# ❌ Bad: Duplicated setup in every test
def test_something(self):
    transactions = [
        {"transaction_info": {"transaction_id": "TX1", ...}},
        {"transaction_info": {"transaction_id": "TX2", ...}},
    ]
    classifier = MagicMock(side_effect=...)
    result = process_transactions(transactions, classifier)
    assert len(result) == 2

# ✅ Good: Use fixtures from conftest.py
def test_something(self, sample_paypal_transactions, mock_classifier):
    result = process_transactions(sample_paypal_transactions, mock_classifier)
    assert len(result) == len(sample_paypal_transactions)
```

#### Test Naming Best Practices

```python
# ✅ Good: Descriptive, explains what's being tested
def test_risk_score_is_zero_for_normal_transaction(self): ...
def test_webhook_rejected_when_signature_invalid(self): ...
def test_forecast_returns_empty_when_insufficient_data(self): ...

# ❌ Bad: Vague or implementation-focused
def test_risk(self): ...
def test_webhook(self): ...
def test_forecast(self): ...
```

#### Markers for Test Classification

```python
import pytest

@pytest.mark.unit
def test_fast_isolated_behavior(self): ...

@pytest.mark.integration
def test_multi_module_flow(self): ...

@pytest.mark.performance
@pytest.mark.slow
def test_large_batch_throughput(self): ...

@pytest.mark.security
def test_webhook_signature_verification(self): ...

@pytest.mark.requires_elasticsearch
def test_real_es_query(self): ...
```

---

### 🎭 Mocking Strategy

#### What to Mock

| Dependency | Mock Approach | Why |
|:---|:---|:---|
| PayPal API | `unittest.mock.patch` on `requests.get/post` | Avoid real API calls, rate limits, and sandbox data requirements |
| Hugging Face Inference API | Mock `InferenceClient.text_generation` | Avoid rate limits and API costs |
| Zapier | Mock `requests.post` in webhook listener | Avoid triggering real notifications |
| Elasticsearch (unit tests) | Mock `Elasticsearch` class | Fast, deterministic, no Docker required |
| Elasticsearch (integration tests) | In-memory mock via `integration_es_client` fixture | Realistic behavior without external dependencies |

#### What NOT to Mock

- **Internal module interactions** in integration tests — this is the whole point
- **Standard library functions** — they're reliable and fast
- **Pure functions** — they have no side effects to mock
- **Data transformations** — test the real logic

#### Mocking Pattern Examples

**Mocking an HTTP call:**
```python
from unittest.mock import patch, MagicMock

@patch("paypal_client.requests.get")
def test_fetch_transactions_success(self, mock_get, mock_paypal_token):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "transaction_details": [{"transaction_info": {"transaction_id": "TX1"}}]
    }
    mock_get.return_value = mock_response

    result = paypal_client.fetch_transactions(mock_paypal_token)
    assert len(result) == 1
```

**Mocking a module dependency:**
```python
@patch("risk_engine.anomaly_detector.get_anomaly_data_with_scores")
def test_score_all_returns_list(self, mock_get_anomaly, sample_transaction):
    mock_df = pd.DataFrame([sample_transaction])
    mock_get_anomaly.return_value = mock_df

    result = risk_engine.score_all_transactions()
    assert isinstance(result, list)
```

#### The In-Memory Elasticsearch Mock

For integration tests, we use a custom in-memory Elasticsearch mock that supports:
- Index creation/deletion
- Document indexing
- Multi-match search (simplified)
- Sorting by `indexed_at`
- Count operations

Access it via the `integration_es_client` fixture:

```python
def test_full_pipeline(self, integration_es_client, mock_classifier):
    # integration_es_client provides a realistic in-memory ES
    raw = [{"transaction_info": {...}}]
    categorized = ai_engine.process_transactions(raw, mock_classifier)
    elastic_manager.index_transactions(categorized)
    results = elastic_manager.get_all_transactions()
    assert len(results) == 1
```

---

### 🔧 Fixtures Reference

All shared fixtures are defined in `tests/conftest.py`. Key fixtures include:

#### PayPal Transaction Fixtures

| Fixture | Description |
|:---|:---|
| `sample_paypal_transactions` | 4 realistic PayPal payloads (income, subscription, expense, suspicious) |
| `empty_paypal_transactions` | Empty list for edge cases |
| `malformed_paypal_transaction` | Transaction with missing fields |
| `large_paypal_transactions` | 100 transactions for performance testing |

#### AI/ML Fixtures

| Fixture | Description |
|:---|:---|
| `mock_classifier` | Keyword-based zero-shot classifier mock |
| `sample_categorized_df` | DataFrame with 4 categorized transactions |
| `empty_categorized_df` | Empty DataFrame |
| `high_confidence_df` | DataFrame with all confidence > 0.9 |
| `low_confidence_df` | DataFrame with all confidence < 0.6 |

#### Integration Fixtures

| Fixture | Description |
|:---|:---|
| `integration_es_client` | In-memory Elasticsearch mock |
| `mock_hf_client` | Mock Hugging Face client with deterministic responses |
| `mock_zapier` | Mock Zapier webhook endpoint |
| `valid_webhook_payload` | Realistic PayPal webhook payload |
| `high_risk_webhook_payload` | Webhook payload that triggers high-risk alert |

#### API Fixtures

| Fixture | Description |
|:---|:---|
| `api_client` | FastAPI TestClient with mocked classifier |

#### Autouse Fixtures

These run automatically for every test:

| Fixture | Purpose |
|:---|:---|
| `mock_env_vars` | Sets test environment variables (prevents dependence on local `.env`) |
| `reset_module_state` | Resets module-level state between tests (prevents leakage) |

---

### 📊 Performance Benchmarking

#### Running Benchmarks

```bash
# Run all performance tests
pytest tests/performance/ -v

# Save baseline for comparison
pytest tests/performance/ --benchmark-save=v1.0

# Compare against baseline
pytest tests/performance/ --benchmark-compare=v1.0

# Generate JSON report
pytest tests/performance/ --benchmark-json=benchmarks.json

# Generate CSV report
pytest tests/performance/ --benchmark-csv=benchmarks.csv
```

#### Understanding Benchmark Output

```
Name                              Min       Max      Mean    StdDev
test_single_tx_latency          1.23ms    2.34ms   1.56ms   0.23ms
test_small_batch_throughput    12.34ms   15.67ms  13.45ms   0.89ms
```

- **Min/Max**: Fastest and slowest runs
- **Mean**: Average latency
- **StdDev**: Variability (lower = more consistent)

#### Performance Thresholds

| Operation | Threshold | Rationale |
|:---|:---|:---|
| Single AI categorization | < 10ms | Framework overhead only |
| 100 transactions batch | < 200ms | Typical user request |
| 1000 transactions batch | < 2s | Bulk processing |
| Risk scoring (100 tx) | < 500ms | Real-time requirement |
| ES bulk index (100 docs) | < 500ms | Acceptable latency |
| ES search (any size) | < 500ms | User-facing query |
| Prophet forecast (30 days) | < 3s | Background job |
| Isolation Forest (100 tx) | < 2s | Background job |

---

### 🔄 CI/CD Integration

#### GitHub Actions Workflow

The CI pipeline (`.github/workflows/ci.yml`) runs tests automatically on every push and pull request:

```yaml
- name: Run tests with coverage
  env:
    PAYPAL_CLIENT_ID: test_client_id
    PAYPAL_SECRET: test_secret
    HF_TOKEN: test_token
    ES_HOST: http://localhost:9200
    ENVIRONMENT: test
  run: |
    pytest \
      --cov=. \
      --cov-report=xml \
      --cov-report=term-missing \
      --junitxml=junit/test-results.xml \
      -v
```

#### Local CI Simulation

To run tests exactly as CI does:

```bash
make ci-test
```

This runs:
- All tests with coverage
- XML and HTML reports
- JUnit XML for CI parsers

#### Coverage Upload to Codecov

If you've configured Codecov (recommended for public repos):

```bash
# In CI, coverage is automatically uploaded
# Locally, you can upload manually:
pip install codecov
codecov -f coverage.xml
```

---

### 🐛 Troubleshooting

#### Common Issues

##### Issue: `ModuleNotFoundError: No module named 'pytest'`

**Cause:** Test dependencies not installed.

**Fix:**
```bash
pip install -r requirements-dev.txt
```

##### Issue: Tests fail with "Elasticsearch connection refused"

**Cause:** Integration tests trying to connect to real Elasticsearch.

**Fix:** Use the `integration_es_client` fixture, which provides an in-memory mock:
```python
def test_something(self, integration_es_client):
    # integration_es_client automatically mocks Elasticsearch
    ...
```

##### Issue: Tests fail with "PAYPAL_CLIENT_ID not set"

**Cause:** Environment variables not configured.

**Fix:** The `mock_env_vars` autouse fixture should handle this. If it doesn't:
```bash
export PAYPAL_CLIENT_ID=test_client_id
export PAYPAL_SECRET=test_secret
export HF_TOKEN=test_token
```

##### Issue: Performance benchmarks are flaky

**Cause:** System load varies between runs.

**Fix:**
- Increase benchmark rounds: `pytest --benchmark-min-rounds=10`
- Close other applications during benchmark runs
- Use `--benchmark-warmup=on` to stabilize JIT compilation

##### Issue: Coverage below 70%

**Cause:** New code added without tests.

**Fix:**
```bash
# See which lines are uncovered
pytest --cov=. --cov-report=term-missing

# Write tests for the red lines
# Then re-run to verify coverage improved
```

##### Issue: Tests pass locally but fail in CI

**Cause:** Environment differences (Python version, OS, available resources).

**Fix:**
- Check CI logs for specific failures
- Run tests with the same Python version locally
- Ensure no tests depend on local file paths or system state

---

### 🔧 Test Maintenance

#### When to Update Tests

| Change | Action |
|:---|:---|
| Bug fix | Add a regression test that would have caught the bug |
| New feature | Add tests for the new behavior |
| Refactoring | Update tests if public API changes; keep tests passing |
| Performance regression | Add a benchmark to catch future regressions |
| Dependency upgrade | Run full test suite; fix any breakage |

#### Test Debt Indicators

Watch for these warning signs:
- Tests taking > 5 minutes to run
- Flaky tests (pass sometimes, fail others)
- Coverage dropping below 80%
- Tests that are hard to understand
- Duplicated test setup code

#### Refactoring Tests

When tests become hard to maintain:
1. Extract common setup into fixtures
2. Split large test files into focused modules
3. Use parametrized tests for similar scenarios
4. Remove redundant tests (keep coverage, reduce duplication)

---

### 📈 Metrics and Goals

#### Current State (as of v4.1.0)

| Metric | Value | Status |
|:---|:---|:---|
| Total tests | 155 | ✅ |
| Unit tests | 97 | ✅ |
| Integration tests | 30 | ✅ |
| Performance benchmarks | 28 | ✅ |
| Code coverage | 92% | ✅ (target: 85%+) |
| Test execution time | ~45 seconds | ✅ |
| Flaky tests | 0 | ✅ |

#### Goals

| Goal | Target | Timeline |
|:---|:---|:---|
| Maintain coverage ≥ 85% | Ongoing | Continuous |
| Keep test execution < 2 minutes | Ongoing | Continuous |
| Add tests for new features | 100% of features | Per PR |
| Zero flaky tests | 0 | Ongoing |
| Performance regression detection | All critical paths | Q1 2027 |

#### Measuring Test Quality

Good tests are:
- **Fast** — unit tests < 100ms, integration < 5s
- **Reliable** — same result every run
- **Isolated** — don't depend on execution order
- **Readable** — clear what they're testing
- **Maintainable** — easy to update when code changes

---

### 📚 Additional Resources

- **pytest documentation:** https://docs.pytest.org/
- **pytest-benchmark:** https://pytest-benchmark.readthedocs.io/
- **Our test fixtures:** `tests/conftest.py`
- **pytest configuration:** `pytest.ini`
- **CI/CD pipeline:** `.github/workflows/ci.yml`
- **Risk Register:** `docs/RISK_REGISTER.md` (testing as risk mitigation)

---

### 🎉 Summary

Testing in PayFlow AI is a first-class concern, not an afterthought. With 155 tests across unit, integration, and performance categories, 92% code coverage, and a comprehensive CI/CD pipeline, the platform is built on a foundation of verified correctness.

When adding new features or fixing bugs:
1. **Write the test first** (or alongside the code)
2. **Use existing fixtures** from `conftest.py`
3. **Follow the AAA pattern** (Arrange, Act, Assert)
4. **Run tests locally** before committing
5. **Check coverage** to ensure new code is tested

Happy testing! 🧪

---

*© 2026 Andre Zimin. Licensed under the Apache-2.0 License.*
