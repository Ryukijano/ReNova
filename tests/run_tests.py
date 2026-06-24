import os
import sys
import json
import time
import re
import subprocess
import argparse
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime

# Ensure the tests/ directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assertion_engine import AssertionEngine
from mock_server import MockAPIServer

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MILESTONES = ["M2", "M3", "M4", "M5", "M6"]

def parse_args():
    parser = argparse.ArgumentParser(
        description="ADMET & Drug Repurposing Engine E2E Test Runner (Fixed Version)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Test Selection & Filtering
    filter_group = parser.add_argument_group("Test Selection Filters")
    filter_group.add_argument(
        "--tier",
        type=str,
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Filter tests by Tier"
    )
    filter_group.add_argument(
        "--feature",
        type=str,
        choices=[
            "target_identification",
            "structure_retrieval",
            "chem_screening",
            "admet_prediction",
            "clinical_check",
            "pipeline_integration",
            "all"
        ],
        default="all",
        help="Filter tests by specific pipeline step/feature"
    )
    filter_group.add_argument(
        "--milestone",
        type=str,
        choices=["M2", "M3", "M4", "M5", "M6", "all"],
        default="all",
        help="Filter tests by milestone"
    )
    filter_group.add_argument(
        "--disease",
        type=str,
        help="Run tests targeting a given disease"
    )
    filter_group.add_argument(
        "--test-id",
        type=str,
        help="Run a specific test case by ID"
    )

    # Environment Routing Configuration
    env_group = parser.add_argument_group("Environment & Run Settings")
    env_group.add_argument(
        "--sci-torch-python",
        type=str,
        default=r"C:\Users\kcwp264.DS\miniconda3\envs\sci_torch\python.exe",
        help="Absolute path to the sci_torch Python executable"
    )
    env_group.add_argument(
        "--sci-chem-python",
        type=str,
        default=r"C:\Users\kcwp264.DS\miniconda3\envs\sci_chem\python.exe",
        help="Absolute path to the sci_chem Python executable"
    )
    env_group.add_argument(
        "--use-mocks",
        action="store_true",
        default=True,
        help="Inject mock configuration/API endpoints"
    )

    # Execution Control
    exec_group = parser.add_argument_group("Execution Controls")
    exec_group.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Execution timeout"
    )
    exec_group.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop execution on first failure"
    )
    exec_group.add_argument(
        "--verbose",
        action="store_true",
        help="Print real-time subprocess stdout/stderr"
    )
    exec_group.add_argument(
        "--keep-temp-files",
        action="store_true",
        help="Retain temporary files"
    )
    exec_group.add_argument(
        "--pipeline-runner",
        type=str,
        default=os.path.join(PROJECT_ROOT, "run_pipeline.py"),
        help="Path to pipeline runner"
    )

    # Reporting Options
    report_group = parser.add_argument_group("Reporting Options")
    report_group.add_argument(
        "--report-dir",
        type=str,
        default=os.path.join(PROJECT_ROOT, "reports"),
        help="Directory for reports"
    )
    report_group.add_argument(
        "--format",
        type=str,
        choices=["json", "xml", "both", "none"],
        default="both",
        help="Saved report format"
    )

    return parser.parse_args()

def validate_test_case_structure(tc, filepath):
    required = ["id", "name", "tier", "milestone", "feature", "input", "assertions"]
    for field in required:
        if field not in tc:
            raise ValueError(f"Test case in {filepath} missing required field: '{field}'")
    if "disease" not in tc["input"]:
        raise ValueError(f"Test case in {filepath} input missing required field: 'disease'")
    if "process" not in tc["assertions"]:
        raise ValueError(f"Test case in {filepath} assertions missing required field: 'process'")

def is_milestone_skipped(tc_milestone, cli_milestone):
    if cli_milestone == "all":
        return False
    if tc_milestone not in MILESTONES or cli_milestone not in MILESTONES:
        return False
    return MILESTONES.index(tc_milestone) > MILESTONES.index(cli_milestone)

def generate_junit_xml(results, total_duration):
    suites = {}
    total_tests = len(results)
    total_failures = 0
    total_skipped = 0
    
    for r in results:
        tier_name = f"Tier_{r['tier']}"
        if tier_name not in suites:
            suites[tier_name] = []
        suites[tier_name].append(r)
        if r["status"] == "failed":
            total_failures += 1
        elif r["status"] == "skipped":
            total_skipped += 1
            
    root = ET.Element("testsuites", {
        "name": "ADMET_E2E_Test_Suite",
        "tests": str(total_tests),
        "failures": str(total_failures),
        "disabled": str(total_skipped),
        "errors": "0",
        "time": f"{total_duration:.2f}"
    })
    
    for tier_name, tc_list in suites.items():
        suite_tests = len(tc_list)
        suite_failures = sum(1 for tc in tc_list if tc["status"] == "failed")
        suite_skipped = sum(1 for tc in tc_list if tc["status"] == "skipped")
        suite_time = sum(tc["duration_seconds"] for tc in tc_list)
        
        suite_el = ET.SubElement(root, "testsuite", {
            "name": tier_name,
            "tests": str(suite_tests),
            "failures": str(suite_failures),
            "disabled": str(suite_skipped),
            "errors": "0",
            "time": f"{suite_time:.2f}"
        })
        
        for tc in tc_list:
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', f"{tc['test_id']}_{tc['name']}")
            tc_el = ET.SubElement(suite_el, "testcase", {
                "classname": tc["feature"],
                "name": safe_name,
                "time": f"{tc['duration_seconds']:.2f}"
            })
            
            if tc["status"] == "skipped":
                ET.SubElement(tc_el, "skipped", {
                    "message": tc.get("error_message", "Skipped")
                })
            elif tc["status"] == "failed":
                err_msg = tc.get("error_message", "Test failed")
                fail_el = ET.SubElement(tc_el, "failure", {
                    "message": err_msg
                })
                detailed_text = f"Command executed: {tc.get('command', 'N/A')}\n"
                detailed_text += f"Errors: {tc.get('errors_list', [])}\n"
                detailed_text += f"Captured STDOUT:\n{tc.get('stdout', '')}\n"
                detailed_text += f"Captured STDERR:\n{tc.get('stderr', '')}\n"
                fail_el.text = detailed_text
                
    from xml.dom import minidom
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

def main():
    args = parse_args()
    
    start_utc = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    start_time = time.time()
    
    print("======================================================================")
    print(" ADMET Repurposing Engine - E2E Test Suite Runner (FIXED)")
    print("======================================================================")
    print(f"Start Time:        {start_utc}")
    print(f"sci_torch path:    {args.sci_torch_python}")
    print(f"sci_chem path:     {args.sci_chem_python}")
    print(f"Mock API Mode:     {'ACTIVE (Using local mock profiles)' if args.use_mocks else 'INACTIVE (Live network calls)'}")
    print(f"Filters:           Tier: {args.tier} | Feature: {args.feature} | Milestone: {args.milestone}")
    if args.disease:
        print(f"                   Disease: {args.disease}")
    if args.test_id:
        print(f"                   Test ID: {args.test_id}")
    print("\nRunning test cases...")
    print("----------------------------------------------------------------------")
    
    cases_dir = os.path.join(PROJECT_ROOT, "tests", "cases")
    if not os.path.exists(cases_dir):
        print(f"Error: Cases directory '{cases_dir}' not found.")
        sys.exit(1)
        
    test_files = [os.path.join(cases_dir, f) for f in os.listdir(cases_dir) if f.endswith(".json")]
    all_cases = []
    
    for fpath in test_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                tc = json.load(f)
                validate_test_case_structure(tc, fpath)
                all_cases.append(tc)
        except Exception as e:
            print(f"[ERROR] Failed to load test case from {os.path.basename(fpath)}: {e}")
            
    # Apply Tier, Feature, Disease, Test ID Filters
    filtered_cases = []
    for tc in all_cases:
        if args.tier != "all" and str(tc["tier"]) != args.tier:
            continue
        if args.feature != "all" and tc["feature"] != args.feature:
            continue
        if args.disease and args.disease.lower() not in tc["input"]["disease"].lower():
            continue
        if args.test_id and args.test_id.lower() not in tc["id"].lower():
            continue
        filtered_cases.append(tc)
        
    results = []
    
    for tc in filtered_cases:
        tc_id = tc["id"]
        tc_name = tc["name"]
        tc_tier = tc["tier"]
        tc_milestone = tc["milestone"]
        tc_feature = tc["feature"]
        
        # Check if skipped by milestone
        if is_milestone_skipped(tc_milestone, args.milestone):
            print(f"[SKIP] [Tier {tc_tier}] [{tc_milestone}] [{tc_feature}] {tc_id}: {tc_name} (Milestone filter skipped)")
            results.append({
                "test_id": tc_id,
                "name": tc_name,
                "tier": tc_tier,
                "feature": tc_feature,
                "milestone": tc_milestone,
                "status": "skipped",
                "duration_seconds": 0.0,
                "error_message": f"Milestone filter skipped"
            })
            continue
            
        # Execute test case
        mock_server = None
        mock_port = None
        
        # Dynamic unique output directory resolution
        out_dir = tc["input"]["args"].get("--output-dir")
        abs_out_dir = None
        if out_dir:
            # Resolve to absolute path relative to project root if it is relative
            if not os.path.isabs(out_dir):
                base_abs_out_dir = os.path.join(PROJECT_ROOT, out_dir)
            else:
                base_abs_out_dir = out_dir
            base_abs_out_dir = os.path.normpath(base_abs_out_dir)
            
            # Append unique suffix containing timestamp and process ID to prevent OS-level cleanup collisions
            unique_suffix = f"_{int(time.time() * 1000)}_{os.getpid()}"
            abs_out_dir = base_abs_out_dir + unique_suffix
            abs_out_dir = os.path.normpath(abs_out_dir)
            tc["input"]["args"]["--output-dir"] = abs_out_dir
            
            # Map the assertion output paths to target the unique output directory
            for out_el in tc["assertions"].get("outputs", []):
                fpath = out_el["file_path"]
                if not os.path.isabs(fpath):
                    abs_fpath = os.path.join(PROJECT_ROOT, fpath)
                else:
                    abs_fpath = fpath
                abs_fpath = os.path.normpath(abs_fpath)
                
                if abs_fpath.startswith(base_abs_out_dir):
                    rel_path = os.path.relpath(abs_fpath, base_abs_out_dir)
                    out_el["file_path"] = os.path.normpath(os.path.join(abs_out_dir, rel_path))
                    
            os.makedirs(abs_out_dir, exist_ok=True)
            
        case_start = time.time()
        stdout = ""
        stderr = ""
        exit_code = -1
        errors = []
        cmd = []
        
        try:
            # Start mock server if requested and profile exists
            mock_profile = tc["input"].get("mock_profile")
            if args.use_mocks and mock_profile:
                mock_dir = os.path.join(PROJECT_ROOT, "tests", "mock_profiles", mock_profile)
                requested_port = int(tc["input"]["env"].get("ADMET_MOCK_PORT", "8085"))
                mock_server = MockAPIServer(mock_dir=mock_dir, port=requested_port)
                mock_port = mock_server.start()
                
            # Build execution command
            python_path = args.sci_torch_python
            if tc_feature in ["chem_screening", "admet_prediction"]:
                python_path = args.sci_chem_python
                
            cmd = [python_path, args.pipeline_runner, tc["input"]["disease"]]
            for arg_k, arg_v in tc["input"]["args"].items():
                cmd.append(arg_k)
                if arg_v is not None and arg_v != "":
                    cmd.append(str(arg_v))
                    
            # Setup environment variables
            env = os.environ.copy()
            env["SCI_TORCH_PYTHON"] = args.sci_torch_python
            env["SCI_CHEM_PYTHON"] = args.sci_chem_python
            
            for env_k, env_v in tc["input"]["env"].items():
                env[env_k] = env_v
                
            if mock_port:
                base_url = f"http://127.0.0.1:{mock_port}"
                env["OPENTARGETS_API_URL"] = f"{base_url}/graphql"
                env["ALPHAFOLD_API_URL"] = f"{base_url}/files"
                env["CHEMBL_API_URL"] = f"{base_url}/chembl/api/data"
                env["CLINICALTRIALS_API_URL"] = f"{base_url}/api/v2"
                env["OPENFDA_API_URL"] = f"{base_url}/drug"
                env["ADMET_MOCK_PORT"] = str(mock_port)
                env["ADMET_MOCK_PROFILE"] = mock_profile
                
            # Spawn process
            proc_res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=tc["assertions"]["process"].get("timeout_seconds", args.timeout)
            )
            stdout = proc_res.stdout
            stderr = proc_res.stderr
            exit_code = proc_res.returncode
            
        except subprocess.TimeoutExpired as te:
            stdout = te.stdout if isinstance(te.stdout, str) else (te.stdout or "").decode('utf-8')
            stderr = te.stderr if isinstance(te.stderr, str) else (te.stderr or "").decode('utf-8')
            exit_code = -999
            errors.append(f"Subprocess execution timed out after {args.timeout}s.")
        except Exception as ex:
            exit_code = -999
            errors.append(f"Runner internal error spawning subprocess: {ex}")
        finally:
            if mock_server:
                mock_server.stop()
                
        elapsed = time.time() - case_start
        
        # Run assertions if no spawn/timeout errors
        if not errors:
            process_errors = AssertionEngine.validate_process_result(
                stdout, stderr, exit_code, tc["assertions"]["process"]
            )
            errors.extend(process_errors)
            
            # File validation (only if process exited correctly)
            if not process_errors:
                outputs = tc["assertions"].get("outputs", [])
                for out in outputs:
                    fpath = out["file_path"]
                    # If relative path, resolve relative to project root
                    if not os.path.isabs(fpath):
                        abs_fpath = os.path.join(PROJECT_ROOT, fpath)
                    else:
                        abs_fpath = fpath
                    abs_fpath = os.path.normpath(abs_fpath)
                        
                    fmt = out["format"]
                    if fmt == "json":
                        json_errs = AssertionEngine.validate_json(abs_fpath, out.get("json_rules", {}))
                        errors.extend(json_errs)
                    elif fmt == "csv":
                        csv_errs = AssertionEngine.validate_csv(abs_fpath, out.get("csv_rules", {}))
                        errors.extend(csv_errs)
                        
        case_passed = len(errors) == 0
        status = "passed" if case_passed else "failed"
        
        # Cleanup output files if requested with a retry loop to prevent Windows file-lock race failures
        if not args.keep_temp_files and abs_out_dir:
            # Robust deletion with retry loop
            for attempt in range(5):
                try:
                    if os.path.exists(abs_out_dir):
                        shutil.rmtree(abs_out_dir)
                    break
                except Exception:
                    time.sleep(0.2)
                
        if case_passed:
            print(f"[PASS] [Tier {tc_tier}] [{tc_milestone}] [{tc_feature}] {tc_id}: {tc_name} (Took {elapsed:.1f}s)")
        else:
            print(f"[FAIL] [Tier {tc_tier}] [{tc_milestone}] [{tc_feature}] {tc_id}: {tc_name} (Took {elapsed:.1f}s)")
            error_summary = errors[0] if errors else "Unknown failure"
            print(f"   >> Error: {error_summary}")
            print(f"   >> Command: {' '.join(cmd)}")
            
            # Save failing logs to reports/logs/
            log_dir = os.path.join(args.report_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            stdout_log = os.path.join(log_dir, f"{tc_id}_stdout.log")
            stderr_log = os.path.join(log_dir, f"{tc_id}_stderr.log")
            with open(stdout_log, "w", encoding="utf-8") as f:
                f.write(stdout)
            with open(stderr_log, "w", encoding="utf-8") as f:
                f.write(stderr)
                
            print("   >> Log files saved to:")
            print(f"      - reports/logs/{tc_id}_stdout.log")
            print(f"      - reports/logs/{tc_id}_stderr.log")
            
            if args.verbose:
                print("--- STDOUT ---")
                print(stdout)
                print("--- STDERR ---")
                print(stderr)
                
        results.append({
            "test_id": tc_id,
            "name": tc_name,
            "tier": tc_tier,
            "feature": tc_feature,
            "milestone": tc_milestone,
            "status": status,
            "duration_seconds": elapsed,
            "error_message": "; ".join(errors) if errors else "",
            "errors_list": errors,
            "command": " ".join(cmd),
            "stdout": stdout,
            "stderr": stderr
        })
        
        if not case_passed and args.fail_fast:
            print("\nFail-fast active. Stopping execution.")
            break
            
    total_duration = time.time() - start_time
    
    # Calculate counts
    total_count = len(results)
    passed_count = sum(1 for r in results if r["status"] == "passed")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    
    print("----------------------------------------------------------------------")
    print("Test Execution Finished.")
    print("======================================================================")
    print("                              E2E TEST SUMMARY")
    print("======================================================================")
    print(f"Total Executed:  {total_count - skipped_count}")
    print(f"Passed:          {passed_count}")
    print(f"Failed:          {failed_count}")
    print(f"Skipped:         {skipped_count}")
    print(f"Total Duration:  {total_duration:.1f}s")
    print("\nSummary by Feature:")
    
    features_present = set(tc["feature"] for tc in all_cases)
    for f in sorted(features_present):
        f_pass = sum(1 for r in results if r["feature"] == f and r["status"] == "passed")
        f_fail = sum(1 for r in results if r["feature"] == f and r["status"] == "failed")
        f_skip = sum(1 for r in results if r["feature"] == f and r["status"] == "skipped")
        summary_str = f"- {f}:"
        parts = []
        if f_pass > 0 or f_fail > 0:
            parts.append(f"{f_pass} Passed")
            parts.append(f"{f_fail} Failed")
        if f_skip > 0:
            parts.append(f"{f_skip} Skipped")
        print(f"{summary_str:<25} {', '.join(parts)}")
        
    print(f"\nExit Code: {1 if failed_count > 0 else 0}")
    print("======================================================================")
    
    # Save reports
    if args.format in ["json", "both"]:
        os.makedirs(args.report_dir, exist_ok=True)
        report_path = os.path.join(args.report_dir, "e2e_report.json")
        json_out = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "command_line": " ".join(sys.argv),
            "environment": {
                "sci_torch_python": args.sci_torch_python,
                "sci_chem_python": args.sci_chem_python,
                "use_mocks": args.use_mocks
            },
            "summary": {
                "total": total_count,
                "passed": passed_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "duration_seconds": total_duration
            },
            "results": [
                {
                    "test_id": r["test_id"],
                    "name": r["name"],
                    "tier": r["tier"],
                    "feature": r["feature"],
                    "milestone": r["milestone"],
                    "status": r["status"],
                    "duration_seconds": r["duration_seconds"],
                    "error_message": r.get("error_message", ""),
                    "command": r.get("command", ""),
                    "stdout": r.get("stdout", "") if r["status"] == "failed" else "",
                    "stderr": r.get("stderr", "") if r["status"] == "failed" else ""
                }
                for r in results
            ]
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(json_out, f, indent=2)
            
    if args.format in ["xml", "both"]:
        os.makedirs(args.report_dir, exist_ok=True)
        xml_path = os.path.join(args.report_dir, "junit_report.xml")
        xml_content = generate_junit_xml(results, total_duration)
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
            
    sys.exit(1 if failed_count > 0 else 0)

if __name__ == "__main__":
    main()
