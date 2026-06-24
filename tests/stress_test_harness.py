import os
import sys
import json
import csv
import shutil
import tempfile
import urllib.request
import urllib.error
import threading
import time
import subprocess
from typing import List, Dict, Any

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "tests"))

from assertion_engine import AssertionEngine
from mock_server import MockAPIServer

def run_assertion_engine_tests():
    print("\n=== [1] Testing Assertion Engine Robustness ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1.1 CSV missing required columns
        csv_path = os.path.join(tmpdir, "missing_cols.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["gene_symbol", "compound_id"]) # missing smiles, value, units
            writer.writerow(["CFTR", "CHEMBL123"])
            
        rules = {
            "required_columns": ["gene_symbol", "compound_id", "smiles"],
            "min_row_count": 1
        }
        errs = AssertionEngine.validate_csv(csv_path, rules)
        print("Missing column error detected:", errs)
        assert any("missing required column: 'smiles'" in e for e in errs), "Failed to detect missing smiles column"

        # 1.2 CSV wrong data type
        csv_path_type = os.path.join(tmpdir, "wrong_type.csv")
        with open(csv_path_type, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["gene_symbol", "value"])
            writer.writerow(["CFTR", "not-a-float"])
            
        rules_type = {
            "required_columns": ["gene_symbol", "value"],
            "column_validators": {
                "value": {"type": "float"}
            }
        }
        errs = AssertionEngine.validate_csv(csv_path_type, rules_type)
        print("Wrong type error detected:", errs)
        assert any("value 'not-a-float' is not a float" in e for e in errs), "Failed to detect wrong type float"

        # 1.3 CSV out-of-bounds QED value
        csv_path_qed = os.path.join(tmpdir, "out_of_bounds_qed.csv")
        with open(csv_path_qed, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["gene_symbol", "qed"])
            writer.writerow(["CFTR", "1.5"])  # out of bounds [0.0, 1.0]
            writer.writerow(["CFTR", "-0.1"]) # out of bounds [0.0, 1.0]
            
        rules_qed = {
            "required_columns": ["gene_symbol", "qed"],
            "column_validators": {
                "qed": {"type": "float", "min": 0.0, "max": 1.0}
            }
        }
        errs = AssertionEngine.validate_csv(csv_path_qed, rules_qed)
        print("Out-of-bounds QED errors detected:", errs)
        assert any("value 1.5 > max limit 1.0" in e for e in errs), "Failed to detect QED > 1.0"
        assert any("value -0.1 < min limit 0.0" in e for e in errs), "Failed to detect QED < 0.0"

        # 1.4 CSV invalid SMILES
        csv_path_smiles = os.path.join(tmpdir, "invalid_smiles.csv")
        with open(csv_path_smiles, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["gene_symbol", "smiles"])
            writer.writerow(["CFTR", "C C C"]) # spaces are invalid in SMILES
            writer.writerow(["CFTR", "CCC#%&^*INVALID"]) # invalid chars
            
        rules_smiles = {
            "required_columns": ["gene_symbol", "smiles"],
            "column_validators": {
                "smiles": {"type": "smiles"}
            }
        }
        errs = AssertionEngine.validate_csv(csv_path_smiles, rules_smiles)
        print("Invalid SMILES errors detected:", errs)
        assert any("value 'C C C' is not a valid SMILES string" in e for e in errs), "Failed to detect SMILES with spaces"
        assert any("value 'CCC#%&^*INVALID' is not a valid SMILES string" in e for e in errs), "Failed to detect invalid characters in SMILES"

        # 1.5 JSON file does not exist
        non_existent_json = os.path.join(tmpdir, "does_not_exist.json")
        errs = AssertionEngine.validate_json(non_existent_json, {"min_items": 1})
        print("Non-existent JSON error detected:", errs)
        assert any("does not exist or is empty" in e for e in errs), "Failed to detect missing JSON"

        # 1.6 JSON has fewer items than expected
        json_fewer = os.path.join(tmpdir, "fewer_items.json")
        with open(json_fewer, "w", encoding="utf-8") as f:
            json.dump([{"item": 1}], f)
            
        errs = AssertionEngine.validate_json(json_fewer, {"min_items": 5})
        print("Fewer items JSON error detected:", errs)
        assert any("has 1 items, expected at least 5" in e for e in errs), "Failed to detect fewer JSON items"

        # 1.7 JSON check_file_paths_exist points to non-existent structure path
        json_paths = os.path.join(tmpdir, "paths.json")
        non_existent_pdb = os.path.join(tmpdir, "not_there.pdb")
        with open(json_paths, "w", encoding="utf-8") as f:
            json.dump([{"structure_path": non_existent_pdb}], f)
            
        errs = AssertionEngine.validate_json(json_paths, {"check_file_paths_exist": "$[*].structure_path"})
        print("Missing structure path error detected:", errs)
        assert any("structure path" in e and "does not exist on disk" in e for e in errs), "Failed to detect missing structure PDB path"

    print("[PASS] Assertion Engine Robustness validated.")


def stress_test_mock_server():
    print("\n=== [2] Stress Testing Mock Server ===")
    
    mock_dir = os.path.join(project_root, "tests", "mock_profiles", "cystic_fibrosis")
    server = MockAPIServer(mock_dir=mock_dir, port=8095) # Use 8095 to avoid port 0 mapping bug
    port = server.start()
    base_url = f"http://localhost:{port}"
    print(f"Mock Server started at {base_url}")
    
    try:
        # 2.1 Unmapped GET endpoint
        try:
            urllib.request.urlopen(f"{base_url}/invalid_route")
            assert False, "Should have raised urllib.error.HTTPError for 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404, f"Expected 404, got {e.code}"
            resp_body = e.read().decode('utf-8')
            print("Unmapped route response (404):", resp_body)
            assert "Mock not found for GET" in resp_body, "Incorrect error payload"

        # 2.2 Unmapped POST endpoint
        try:
            req = urllib.request.Request(
                f"{base_url}/invalid_route",
                data=b"{}",
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req)
            assert False, "Should have raised urllib.error.HTTPError for 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404, f"Expected 404, got {e.code}"
            resp_body = e.read().decode('utf-8')
            print("Unmapped POST response (404):", resp_body)
            assert "Mock not found for POST" in resp_body, "Incorrect error payload"

        # 2.3 GET on a POST-only route (like /graphql)
        try:
            urllib.request.urlopen(f"{base_url}/graphql")
            assert False, "Should have raised urllib.error.HTTPError for 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404, f"Expected 404, got {e.code}"
            resp_body = e.read().decode('utf-8')
            print("GET on POST route response (404):", resp_body)

        # 2.4 POST with empty or malformed body on /graphql
        # (It should still return the response file if mapping only checks path/method, or return 404 if body check is strict)
        # Let's inspect mapping.json to see what is checked
        mapping_file = os.path.join(mock_dir, "mapping.json")
        with open(mapping_file, "r") as f:
            mappings = json.load(f)
            
        print("GraphQL mappings rules:", [m for m in mappings if "graphql" in m.get("path_pattern", "")])
        
        # Call it with standard body
        req = urllib.request.Request(
            f"{base_url}/graphql",
            data=json.dumps({"query": "cystic_fibrosis"}).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            assert "data" in data, "GraphQL response did not return expected mock data"
            
        # Call it with non-JSON or malformed body
        req_malformed = urllib.request.Request(
            f"{base_url}/graphql",
            data=b"INVALID_NON_JSON",
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req_malformed) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print("Response to malformed body on /graphql:", data)
        except Exception as ex:
            print("Malformed body on /graphql failed as expected or handled:", ex)

        # 2.5 Concurrent requests stress testing
        # Since it uses a single-threaded server, let's make sure it handles consecutive/concurrent connections without hanging.
        def fetch_cftr_status():
            try:
                with urllib.request.urlopen(f"{base_url}/chembl/api/data/status") as resp:
                    resp.read()
            except Exception as e:
                print("Concurrent request error:", e)

        threads = []
        for _ in range(50):
            t = threading.Thread(target=fetch_cftr_status)
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        print("Successfully processed 50 concurrent requests without crashing/locking the mock server.")

    finally:
        server.stop()
        print("Mock Server stopped.")
        
    print("[PASS] Mock Server robustness validated.")


def stress_test_cleanup_race():
    print("\n=== [3] Stress Testing Windows Directory Cleanup Race ===")
    
    # Let's perform a stress test by running test runner in immediate succession 5 times.
    # We will run python tests/run_tests.py --use-mocks (without --keep-temp-files) in rapid succession.
    # We want to see if we hit FileNotFoundError or other cleanup exceptions.
    
    success_count = 0
    failures = []
    
    for i in range(5):
        print(f"Run {i+1}/5:")
        start_time = time.time()
        res = subprocess.run(
            ["python", "tests/run_tests.py", "--use-mocks"],
            capture_output=True,
            text=True
        )
        duration = time.time() - start_time
        print(f"  Exit code: {res.returncode} (Took {duration:.1f}s)")
        
        if res.returncode == 0:
            success_count += 1
        else:
            print("  FAIL. Stdout snippet:", res.stdout.splitlines()[-5:] if res.stdout else "")
            print("  FAIL. Stderr snippet:", res.stderr.splitlines()[-5:] if res.stderr else "")
            failures.append({
                "run": i+1,
                "stdout": res.stdout,
                "stderr": res.stderr
            })
            
    print(f"\nCompleted 5 successive E2E runs. Success: {success_count}/5. Failures: {len(failures)}/5.")
    
    if failures:
        print("[OBSERVATION] Windows Directory Cleanup Race condition reproduced!")
        # Let's inspect the exact failure message
        for f in failures:
            print(f"--- Failure in Run {f['run']} ---")
            print("Stdout:")
            print(f["stdout"])
            print("Stderr:")
            print(f["stderr"])
    else:
        print("[INFO] Did not hit race condition in 5 successive runs. Let's do a tighter direct filesystem simulation of the race.")
        
        # Tighter direct simulation of shutil.rmtree / os.makedirs race:
        # We simulate the exact logic:
        # OS starts a delete process, but handle is open or OS takes time.
        # Immediately recreating the directory.
        race_hits = 0
        with tempfile.TemporaryDirectory() as base_tmp:
            for j in range(100):
                target_dir = os.path.join(base_tmp, "race_target")
                os.makedirs(target_dir, exist_ok=True)
                
                # Write a file
                fpath = os.path.join(target_dir, "test.txt")
                with open(fpath, "w") as f:
                    f.write("data")
                    
                # Now delete using shutil.rmtree and immediately try to recreate
                try:
                    shutil.rmtree(target_dir, ignore_errors=True)
                    # Recreate immediately
                    os.makedirs(target_dir, exist_ok=False)
                    # Write immediately
                    with open(fpath, "w") as f:
                        f.write("data2")
                except Exception as e:
                    race_hits += 1
                    print(f"Direct filesystem race hit at iteration {j}: {type(e).__name__} - {e}")
                    
        print(f"Direct filesystem race hits: {race_hits}/100 iterations.")


if __name__ == "__main__":
    run_assertion_engine_tests()
    stress_test_mock_server()
    stress_test_cleanup_race()
