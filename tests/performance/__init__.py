"""
Performance Test Suite for PayFlow AI
=====================================

Benchmarks the platform's critical paths to catch performance regressions
and document system capabilities.

Test Categories
---------------

1. AI Performance (test_ai_performance.py)
   - Single transaction categorization latency
   - Batch categorization throughput
   - Generative summary latency
   - Risk scoring throughput

2. Pipeline Performance (test_pipeline_performance.py)
   - Full PayPal → AI → ES pipeline
   - Forecasting latency
   - Anomaly detection latency
   - Portfolio risk computation

3. Data Layer Performance (test_data_layer_performance.py)
   - Elasticsearch indexing throughput
   - Search query latency at scale
   - Bulk operations performance

Running Performance Tests
-------------------------

    # Run all performance tests
    pytest tests/performance/ -v

    # Run with benchmark comparison (against saved baseline)
    pytest tests/performance/ --benchmark-compare

    # Save baseline for future comparison
    pytest tests/performance/ --benchmark-save=v1.0

    # Run only fast benchmarks (skip slow ones)
    pytest tests/performance/ -m "not slow"

    # Generate benchmark report as JSON
    pytest tests/performance/ --benchmark-json=benchmarks.json

    # Generate CSV report
    pytest tests/performance/ --benchmark-csv=benchmarks.csv

Benchmark Thresholds
--------------------

Thresholds are set conservatively to avoid flaky CI failures. They represent
**upper bounds** — actual performance should be significantly better. If a
test exceeds its threshold, it indicates a regression worth investigating.

Note: Performance tests are excluded from the default test run via the
`performance` marker. Run them explicitly when needed.

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Andre Zimin"
__license__ = "Apache-2.0"
__all__: list[str] = []
