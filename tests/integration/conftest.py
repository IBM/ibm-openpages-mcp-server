"""
Pytest configuration and custom reporting for integration tests
"""
import pytest
from datetime import datetime
from typing import Optional


def pytest_configure(config):
    """Configure pytest with custom markers and settings"""
    config.addinivalue_line(
        "markers", "health: mark test as health check test"
    )
    config.addinivalue_line(
        "markers", "protocol: mark test as MCP protocol test"
    )
    config.addinivalue_line(
        "markers", "resources: mark test as resource test"
    )
    config.addinivalue_line(
        "markers", "query: mark test as query execution test"
    )
    config.addinivalue_line(
        "markers", "crud: mark test as CRUD operation test"
    )
    config.addinivalue_line(
        "markers", "timeout: mark test with timeout limit in seconds"
    )
    config.addinivalue_line(
        "markers", "order: mark test execution order for sequential tests"
    )


class TestResultCollector:
    """Collect test results for summary reporting"""
    def __init__(self):
        self.results = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.server_url: Optional[str] = None
    
    def add_result(self, nodeid, outcome, duration):
        """Add a test result"""
        # Extract test class and method name
        parts = nodeid.split("::")
        if len(parts) >= 3:
            test_class = parts[1]
            test_method = parts[2]
        else:
            test_class = "Unknown"
            test_method = nodeid
        
        self.results.append({
            "class": test_class,
            "method": test_method,
            "outcome": outcome,
            "duration": duration
        })
    
    def set_server_url(self, url: str):
        """Set the server URL for the summary"""
        self.server_url = url


collector = TestResultCollector()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to collect test results"""
    outcome = yield
    report = outcome.get_result()
    
    if report.when == "call":
        collector.add_result(
            item.nodeid,
            report.outcome,
            report.duration
        )


def pytest_sessionstart(session):
    """Record session start time"""
    collector.start_time = datetime.now()


def pytest_sessionfinish(session, exitstatus):
    """Print detailed summary after all tests complete"""
    collector.end_time = datetime.now()
    
    if collector.start_time is None or collector.end_time is None:
        duration = 0.0
    else:
        duration = (collector.end_time - collector.start_time).total_seconds()
    
    # Group results by test class
    by_class = {}
    for result in collector.results:
        class_name = result["class"]
        if class_name not in by_class:
            by_class[class_name] = []
        by_class[class_name].append(result)
    
    # Print summary
    print("\n" + "="*80)
    print("INTEGRATION TEST SUITE SUMMARY")
    print("="*80)
    
    # Print server URL if available
    if collector.server_url:
        print(f"\nServer: {collector.server_url}")
    
    # Map class names to friendly descriptions
    class_descriptions = {
        "TestHealthEndpoint": "Health Endpoint Tests",
        "TestMCPProtocol": "MCP Protocol Tests",
        "TestResourceDiscovery": "Resource Discovery Tests (via tools)",
        "TestResourceRetrieval": "Resource Retrieval Tests (via MCP)",
        "TestQueryExecution": "Query Execution Tests",
        "TestObjectUpsert": "Object Upsert Tests",
        "TestObjectAssociations": "Object Association Tests",
        "TestObjectDeletion": "Object Deletion Tests"
    }
    
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    
    for class_name in sorted(by_class.keys()):
        results = by_class[class_name]
        description = class_descriptions.get(class_name, class_name)
        
        passed = sum(1 for r in results if r["outcome"] == "passed")
        failed = sum(1 for r in results if r["outcome"] == "failed")
        skipped = sum(1 for r in results if r["outcome"] == "skipped")
        
        total_passed += passed
        total_failed += failed
        total_skipped += skipped
        
        # Print class summary
        print(f"\n{description}:")
        for result in results:
            status_icon = "✓" if result["outcome"] == "passed" else "✗" if result["outcome"] == "failed" else "⊘"
            status_color = "\033[92m" if result["outcome"] == "passed" else "\033[91m" if result["outcome"] == "failed" else "\033[93m"
            reset_color = "\033[0m"
            
            # Clean up test method name
            method_name = result["method"].replace("test_", "").replace("_", " ").title()
            duration_str = f"{result['duration']:.2f}s"
            
            print(f"  {status_color}{status_icon}{reset_color} {method_name:<50} {duration_str:>8}")
    
    # Print overall summary
    print("\n" + "-"*80)
    print(f"Total Tests: {total_passed + total_failed + total_skipped}")
    print(f"  \033[92m✓ Passed: {total_passed}\033[0m")
    if total_failed > 0:
        print(f"  \033[91m✗ Failed: {total_failed}\033[0m")
    if total_skipped > 0:
        print(f"  \033[93m⊘ Skipped: {total_skipped}\033[0m")
    print(f"\nTotal Duration: {duration:.2f}s")
    print("="*80 + "\n")

# Made with Bob
