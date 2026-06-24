import os
import sys
import json
import subprocess
import shutil
import time
import urllib.request
import urllib.error
from typing import Dict, Any

# Ensure tests/ is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assertion_engine import AssertionEngine
from mock_server import MockAPIServer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCI_TORCH_PYTHON = r"C:\Users\kcwp264.DS\miniconda3\envs\sci_torch\python.exe"

def robust_rmtree(path, retries=5, delay=0.05):
    for attempt in range(retries):
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
            return
        except Exception:
            time.sleep(delay)
    shutil.rmtree(path, ignore_errors=True)

def run_harness(stress_mode: str, test_case_id: str) -> Dict[str, Any]:
    """
    Executes run_tests.py via subprocess, simulating the specified stress mode,
    and returns the exit code, stdout, stderr, and the resulting test reports.
    """
    env = os.environ.copy()
    env["STRESS_MODE"] = stress_mode
    
    # We will use the mock pipeline runner we wrote
    mock_runner_path = os.path.join(PROJECT_ROOT, "tests", "mock_pipeline_runner.py")
    
    cmd = [
        SCI_TORCH_PYTHON, 
        os.path.join(PROJECT_ROOT, "tests", "run_tests.py"),
        "--test-id", test_case_id,
        "--pipeline-runner", mock_runner_path,
        "--report-dir", os.path.join(PROJECT_ROOT, "reports_stress"),
        "--format", "both",
        "--keep-temp-files"
    ]
    
    # Clean up output dir first using robust delete
    out_dir = os.path.join(PROJECT_ROOT, "tests", "output", "tc_cystic_fibrosis")
    robust_rmtree(out_dir)
        
    start_time = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    duration = time.time() - start_time
    
    # Read the generated JSON report
    report_json_path = os.path.join(PROJECT_ROOT, "reports_stress", "e2e_report.json")
    report_data = None
    if os.path.exists(report_json_path):
        try:
            with open(report_json_path, "r") as f:
                report_data = json.load(f)
        except Exception:
            pass
            
    # Check if logs are generated for failure
    log_dir = os.path.join(PROJECT_ROOT, "reports_stress", "logs")
    stdout_log_exists = os.path.exists(os.path.join(log_dir, f"{test_case_id}_stdout.log"))
    stderr_log_exists = os.path.exists(os.path.join(log_dir, f"{test_case_id}_stderr.log"))
    
    return {
        "exit_code": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "duration": duration,
        "report": report_data,
        "stdout_log_exists": stdout_log_exists,
        "stderr_log_exists": stderr_log_exists
    }

def test_assertion_engine_direct():
    print("\n--- Test 1: Assertion Engine Direct Validation ---")
    
    # Setup temp files
    temp_dir = os.path.join(PROJECT_ROOT, "tests", "temp_direct_test")
    os.makedirs(temp_dir, exist_ok=True)
    
    # A. CSV Missing Column
    csv_path = os.path.join(temp_dir, "missing_col.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("gene_symbol,compound_id\nCFTR,CHEMBL123\n")
    
    rules_missing_col = {
        "required_columns": ["gene_symbol", "smiles"]
    }
    errors = AssertionEngine.validate_csv(csv_path, rules_missing_col)
    print(f"Missing column check: {errors}")
    assert any("missing required column: 'smiles'" in e for e in errors), "Failed to detect missing column"
    
    # B. CSV Wrong Data Type
    csv_path = os.path.join(temp_dir, "wrong_type.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("gene_symbol,value\nCFTR,abc\n")
    
    rules_wrong_type = {
        "column_validators": {
            "value": {"type": "float"}
        }
    }
    errors = AssertionEngine.validate_csv(csv_path, rules_wrong_type)
    print(f"Wrong data type check: {errors}")
    assert any("value 'abc' is not a float" in e for e in errors), "Failed to detect wrong data type"
    
    # C. CSV Out of Bounds QED
    csv_path = os.path.join(temp_dir, "out_of_bounds.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("gene_symbol,qed\nCFTR,1.5\n")
        
    rules_out_of_bounds = {
        "column_validators": {
            "qed": {"type": "float", "min": 0.0, "max": 1.0}
        }
    }
    errors = AssertionEngine.validate_csv(csv_path, rules_out_of_bounds)
    print(f"Out of bounds QED check: {errors}")
    assert any("qed' value 1.5 > max limit 1.0" in e for e in errors), "Failed to detect out-of-bounds"
    
    # D. CSV Invalid SMILES
    csv_path = os.path.join(temp_dir, "invalid_smiles.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write("gene_symbol,smiles\nCFTR,C C?\n")
        
    rules_invalid_smiles = {
        "column_validators": {
            "smiles": {"type": "smiles"}
        }
    }
    errors = AssertionEngine.validate_csv(csv_path, rules_invalid_smiles)
    print(f"Invalid SMILES check: {errors}")
    assert any("is not a valid SMILES string" in e for e in errors), "Failed to detect invalid SMILES"
    
    # E. JSON File Does Not Exist
    json_path = os.path.join(temp_dir, "nonexistent.json")
    errors = AssertionEngine.validate_json(json_path, {"min_items": 1})
    print(f"Nonexistent JSON check: {errors}")
    assert any("does not exist or is empty" in e for e in errors), "Failed to detect nonexistent JSON"
    
    # F. JSON Fewer Items Than Expected
    json_path = os.path.join(temp_dir, "fewer_items.json")
    with open(json_path, "w") as f:
        json.dump([], f)
    errors = AssertionEngine.validate_json(json_path, {"min_items": 1})
    print(f"Fewer JSON items check: {errors}")
    assert any("expected at least 1" in e for e in errors), "Failed to detect fewer JSON items"
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("[PASS] Direct Assertion Engine Validation successful.")

def test_assertion_engine_via_harness():
    print("\n--- Test 2: Assertion Engine Validation via Harness Subprocess ---")
    
    test_cases = [
        {"mode": "MISSING_COL", "expected_err": "missing required column: 'smiles'"},
        {"mode": "WRONG_TYPE", "expected_err": "value 'abc' is not a float"},
        {"mode": "OUT_OF_BOUNDS_QED", "expected_err": "value 1.5 > max limit 1.0"},
        {"mode": "INVALID_SMILES", "expected_err": "is not a valid SMILES string"},
        {"mode": "MISSING_JSON", "expected_err": "does not exist or is empty"},
        {"mode": "FEWER_JSON_ITEMS", "expected_err": "expected at least 1"}
    ]
    
    for tc in test_cases:
        mode = tc["mode"]
        expected_err = tc["expected_err"]
        print(f"Running harness in mode {mode}...")
        res = run_harness(mode, "tc_cystic_fibrosis_mock")
        
        # Check overall result
        print(f"  Exit code: {res['exit_code']}")
        print(f"  Logs generated: stdout_log={res['stdout_log_exists']}, stderr_log={res['stderr_log_exists']}")
        
        assert res["exit_code"] != 0, f"Harness should have failed in mode {mode}"
        assert res["stdout_log_exists"] and res["stderr_log_exists"], "Failing test should generate stdout and stderr logs"
        
        # Verify error message is recorded in report
        report = res["report"]
        assert report is not None, "Report json should have been generated"
        case_res = report["results"][0]
        assert case_res["status"] == "failed", "Test status should be 'failed' in report"
        print(f"  Report error message: {case_res['error_message']}")
        assert expected_err in case_res["error_message"], f"Expected error '{expected_err}' not found in '{case_res['error_message']}'"
        print(f"[OK] Stress mode {mode} correctly handled.")

    # Clean up stress report directory
    shutil.rmtree(os.path.join(PROJECT_ROOT, "reports_stress"), ignore_errors=True)
    print("[PASS] Harness Subprocess Assertion Engine Validation successful.")

def test_mock_server_robustness():
    print("\n--- Test 3: Mock Server Robustness ---")
    
    mock_dir = os.path.join(PROJECT_ROOT, "tests", "mock_profiles", "cystic_fibrosis")
    server = MockAPIServer(mock_dir=mock_dir, port=0)
    server.start()
    port = server.server.server_address[1]
    print(f"Mock server started on port {port}")
    
    base_url = f"http://127.0.0.1:{port}"
    
    try:
        # A. Querying unmapped path
        print("Querying unmapped path...")
        try:
            urllib.request.urlopen(f"{base_url}/invalid_endpoint")
            assert False, "Should have thrown HTTPError 404"
        except urllib.error.HTTPError as e:
            print(f"  Got status: {e.code}")
            assert e.code == 404, "Unmapped path should return 404"
            
        # B. Querying with wrong method (GET instead of POST to graphql)
        print("Querying /graphql with GET (expected POST)...")
        try:
            urllib.request.urlopen(f"{base_url}/graphql")
            assert False, "Should have thrown HTTPError 404"
        except urllib.error.HTTPError as e:
            print(f"  Got status: {e.code}")
            assert e.code == 404, "Wrong method should return 404"
            
        # C. Querying POST with body_contains constraint
        print("Querying endpoint with body_contains constraint...")
        server.mappings.append({
            "path_pattern": "/filter-test",
            "method": "POST",
            "body_contains": "RequiredQuery",
            "response_file": "opentargets_query.json",
            "content_type": "application/json"
        })
        
        # C1. Non-matching body
        req_non_match = urllib.request.Request(
            f"{base_url}/filter-test",
            data=b"UnrelatedQuery",
            headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req_non_match)
            assert False, "Should have thrown HTTPError 404 for non-matching body"
        except urllib.error.HTTPError as e:
            print(f"  Got status (non-matching body): {e.code}")
            assert e.code == 404, "Non-matching body should return 404"
            
        # C2. Matching body
        req_match = urllib.request.Request(
            f"{base_url}/filter-test",
            data=b"RequiredQuery",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_match) as resp:
            print(f"  Got status (matching body): {resp.status}")
            assert resp.status == 200, "Matching body should return 200"
            
        # D. Querying valid endpoint (should succeed)
        print("Querying valid endpoint (/graphql with valid body)...")
        # cystic_fibrosis mock profile mapping.json maps POST /graphql with body_contains: "AssociatedTargets"
        req = urllib.request.Request(
            f"{base_url}/graphql",
            data=json.dumps({"query": "AssociatedTargets"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            print(f"  Got status: {resp.status}")
            assert resp.status == 200, "Valid request should succeed"
            body = json.loads(resp.read().decode('utf-8'))
            assert "data" in body, "Response body should have 'data'"
            
    finally:
        server.stop()
        print("Mock server stopped")
        
    print("[PASS] Mock Server Robustness checks completed successfully.")

def test_windows_cleanup_race():
    print("\n--- Test 4: Windows Directory Cleanup Race ---")
    
    temp_dir = os.path.join(PROJECT_ROOT, "tests", "temp_cleanup_race_test")
    
    print("Testing shutil.rmtree and os.makedirs in rapid succession...")
    
    failures = 0
    iterations = 50
    for i in range(iterations):
        try:
            # 1. Create dir
            os.makedirs(temp_dir, exist_ok=True)
            # 2. Write file
            with open(os.path.join(temp_dir, "temp_file.txt"), "w") as f:
                f.write("test")
            # 3. Delete dir
            shutil.rmtree(temp_dir, ignore_errors=True)
            # 4. Immediately recreate and write file
            os.makedirs(temp_dir, exist_ok=True)
            with open(os.path.join(temp_dir, "temp_file_2.txt"), "w") as f:
                f.write("test2")
            # 5. Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"  [RACE DETECTED] Iteration {i}: {type(e).__name__}: {e}")
            failures += 1
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    print(f"Completed {iterations} iterations. Race failure count: {failures}")
    
    # Propose and test a robust cleanup/delete function
    print("Verifying robust deletion function...")
    
    def robust_rmtree(path, retries=5, delay=0.05):
        for attempt in range(retries):
            try:
                if os.path.exists(path):
                    shutil.rmtree(path)
                return
            except Exception:
                time.sleep(delay)
        # Final fallback
        shutil.rmtree(path, ignore_errors=True)

    failures_robust = 0
    for i in range(iterations):
        try:
            # 1. Create dir
            os.makedirs(temp_dir, exist_ok=True)
            # 2. Write file
            with open(os.path.join(temp_dir, "temp_file.txt"), "w") as f:
                f.write("test")
            # 3. Delete dir using robust function
            robust_rmtree(temp_dir)
            # 4. Immediately recreate and write file
            os.makedirs(temp_dir, exist_ok=True)
            with open(os.path.join(temp_dir, "temp_file_2.txt"), "w") as f:
                f.write("test2")
            # 5. Clean up
            robust_rmtree(temp_dir)
        except Exception as e:
            print(f"  [ROBUST FAILURE] Iteration {i}: {type(e).__name__}: {e}")
            failures_robust += 1
            robust_rmtree(temp_dir)
            
    print(f"Robust function: completed {iterations} iterations. Failure count: {failures_robust}")
    assert failures_robust == 0, "Robust deletion function should have 0 failures"
    
    print("[PASS] Windows Directory Cleanup Race validation completed.")

def main():
    print("======================================================================")
    print(" ADMET Repurposing Engine - Harness Stress Test Runner")
    print("======================================================================")
    
    test_assertion_engine_direct()
    test_assertion_engine_via_harness()
    test_mock_server_robustness()
    test_windows_cleanup_race()
    
    print("\n======================================================================")
    print(" ALL STRESS AND ROBUSTNESS TESTS PASSED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    main()
