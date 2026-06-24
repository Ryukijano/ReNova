import subprocess
import time

def verify_fixed_runner():
    print("=== Verifying fixed E2E runner (5 consecutive runs) ===")
    success_count = 0
    failures = []
    
    for i in range(5):
        print(f"Run {i+1}/5:")
        start_time = time.time()
        res = subprocess.run(
            ["python", "tests/run_tests_fixed.py", "--use-mocks"],
            capture_output=True,
            text=True
        )
        duration = time.time() - start_time
        print(f"  Exit code: {res.returncode} (Took {duration:.1f}s)")
        
        if res.returncode == 0:
            success_count += 1
        else:
            print("  FAIL!")
            failures.append({
                "run": i+1,
                "stdout": res.stdout,
                "stderr": res.stderr
            })
            
    print(f"\nVerification Results: Success: {success_count}/5, Failures: {len(failures)}/5")
    if success_count == 5:
        print("[SUCCESS] All 5 runs passed successfully! The race condition is resolved.")
    else:
        print("[FAIL] The race condition or another error still occurred.")

if __name__ == "__main__":
    verify_fixed_runner()
