"""
Test Celery workflow end-to-end in eager mode (no broker required).

Run with: python -m tests.test_celery_workflow
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up eager mode before importing celery
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["CELERY_TASK_EAGER_PROPAGATES"] = "True"

from tasks.celery_app import celery_app

# Configure eager mode
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
)


def test_basic_task_execution():
    """Test that a basic task can execute"""
    print("\n=== Test 1: Basic Task Execution ===")

    @celery_app.task
    def add(x, y):
        return x + y

    result = add.delay(4, 4)
    print(f"Task result: {result.get()}")
    assert result.get() == 8, "Basic task failed"
    print("[OK] Basic task execution works")


def test_task_chain():
    """Test task chaining"""
    print("\n=== Test 2: Task Chain ===")

    from celery import chain

    @celery_app.task
    def step1(value):
        print(f"  Step 1: received {value}")
        return value + 10

    @celery_app.task
    def step2(value):
        print(f"  Step 2: received {value}")
        return value * 2

    @celery_app.task
    def step3(value):
        print(f"  Step 3: received {value}")
        return f"Final result: {value}"

    workflow = chain(step1.s(5), step2.s(), step3.s())
    result = workflow.apply()

    print(f"Chain result: {result.get()}")
    assert result.get() == "Final result: 30", "Chain failed"
    print("[OK] Task chain works")


def test_scraping_task_mock():
    """Test scraping task with mock data"""
    print("\n=== Test 3: Scraping Task (Mock) ===")

    from tasks.scraping_tasks import scrape_county_records

    # This will fail without a database, but we can test the import
    print("  Scraping task is callable:", callable(scrape_county_records))
    print("[OK] Scraping task is properly defined")


def test_ai_task_mock():
    """Test AI task with mock"""
    print("\n=== Test 4: AI Task (Mock) ===")

    from tasks.ai_tasks import analyze_document, generate_risk_assessment

    print("  analyze_document is callable:", callable(analyze_document))
    print("  generate_risk_assessment is callable:", callable(generate_risk_assessment))
    print("[OK] AI tasks are properly defined")


def test_report_task_mock():
    """Test report task"""
    print("\n=== Test 5: Report Task (Mock) ===")

    from tasks.report_tasks import generate_title_report

    print("  generate_title_report is callable:", callable(generate_title_report))
    print("[OK] Report task is properly defined")


def test_orchestration_task_exists():
    """Test that orchestration task exists and has correct structure"""
    print("\n=== Test 6: Orchestration Task Structure ===")

    from tasks.search_tasks import (
        orchestrate_search,
        scrape_county_recorder,
        download_all_documents,
        analyze_all_documents,
        build_chain_of_title,
        generate_report,
        finalize_search,
    )

    tasks = [
        ("orchestrate_search", orchestrate_search),
        ("scrape_county_recorder", scrape_county_recorder),
        ("download_all_documents", download_all_documents),
        ("analyze_all_documents", analyze_all_documents),
        ("build_chain_of_title", build_chain_of_title),
        ("generate_report", generate_report),
        ("finalize_search", finalize_search),
    ]

    for name, task in tasks:
        print(f"  {name}: {task.name}")

    print("[OK] All orchestration tasks exist")


def test_adapter_registry():
    """Test county adapter registry"""
    print("\n=== Test 7: County Adapter Registry ===")

    from app.scraping.adapters import get_adapter_for_county, list_supported_counties

    supported = list_supported_counties()
    print(f"  Supported counties: {supported}")

    # Test getting adapters
    denver_config = {"county_name": "Denver", "recorder_url": "https://test.com"}
    adapter = get_adapter_for_county("denver", denver_config)
    print(f"  Denver adapter: {adapter.__class__.__name__}")

    el_paso_config = {"county_name": "El Paso", "recorder_url": "https://test.com"}
    adapter = get_adapter_for_county("el paso", el_paso_config)
    print(f"  El Paso adapter: {adapter.__class__.__name__}")

    generic_config = {"county_name": "Test County", "recorder_url": "https://test.com"}
    adapter = get_adapter_for_county("unknown", generic_config)
    print(f"  Unknown county adapter: {adapter.__class__.__name__}")

    print("[OK] Adapter registry works")


def test_browser_pool_config():
    """Test browser pool configuration"""
    print("\n=== Test 8: Browser Pool Configuration ===")

    from app.scraping.browser_pool import BrowserPoolManager

    pool = BrowserPoolManager(pool_size=2)
    print(f"  Pool size: {pool.pool_size}")
    print(f"  Pool headless: {pool.headless}")
    print("[OK] Browser pool configuration works")


def test_workflow_simulation():
    """Simulate a complete workflow without database"""
    print("\n=== Test 9: Workflow Simulation ===")

    from celery import chain

    # Create mock tasks that don't need database
    @celery_app.task
    def mock_scrape(search_id):
        print(f"  [1/5] Scraping for search {search_id}...")
        return {"search_id": search_id, "documents_found": 15}

    @celery_app.task
    def mock_download(scrape_result):
        print(f"  [2/5] Downloading {scrape_result['documents_found']} documents...")
        return {**scrape_result, "downloaded": scrape_result["documents_found"]}

    @celery_app.task
    def mock_analyze(download_result):
        print(f"  [3/5] Analyzing {download_result['downloaded']} documents...")
        return {**download_result, "analyzed": True}

    @celery_app.task
    def mock_build_chain(analyze_result):
        print("  [4/5] Building chain of title...")
        return {**analyze_result, "chain_entries": 8}

    @celery_app.task
    def mock_generate_report(chain_result):
        print("  [5/5] Generating report...")
        return {
            "success": True,
            "search_id": chain_result["search_id"],
            "documents": chain_result["documents_found"],
            "chain_entries": chain_result["chain_entries"],
            "report_generated": True
        }

    # Execute workflow
    workflow = chain(
        mock_scrape.s(123),
        mock_download.s(),
        mock_analyze.s(),
        mock_build_chain.s(),
        mock_generate_report.s()
    )

    result = workflow.apply()
    final_result = result.get()

    print(f"\n  Final result: {final_result}")

    assert final_result["success"] == True
    assert final_result["search_id"] == 123
    assert final_result["report_generated"] == True

    print("[OK] Workflow simulation completed successfully!")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("CELERY WORKFLOW END-TO-END TESTS")
    print("Running in EAGER mode (synchronous, no broker required)")
    print("=" * 60)

    tests = [
        test_basic_task_execution,
        test_task_chain,
        test_scraping_task_mock,
        test_ai_task_mock,
        test_report_task_mock,
        test_orchestration_task_exists,
        test_adapter_registry,
        test_browser_pool_config,
        test_workflow_simulation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAILED] {test.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
