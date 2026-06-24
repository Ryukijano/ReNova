import os
import sys
import subprocess
import json

SCI_TORCH_PYTHON = r"C:\Users\kcwp264.DS\miniconda3\envs\sci_torch\python.exe"
SCI_CHEM_PYTHON = r"C:\Users\kcwp264.DS\miniconda3\envs\sci_chem\python.exe"

def verify_env(name, path, required_modules):
    print(f"=== Verifying {name} environment ===")
    if not os.path.exists(path):
        print(f"[FAIL] Executable not found at path: {path}")
        return False
    print(f"[OK] Found executable at: {path}")

    try:
        version = subprocess.check_output([path, "--version"], text=True, stderr=subprocess.STDOUT).strip()
        print(f"[OK] Run test succeeded: {version}")
    except Exception as e:
        print(f"[FAIL] Failed to execute python: {e}")
        return False

    check_code = f"""
libs = {required_modules}
failed = []
for lib in libs:
    try:
        __import__(lib)
    except ImportError as e:
        failed.append((lib, str(e)))
import torch
cuda_avail = torch.cuda.is_available()
device = torch.cuda.get_device_name(0) if cuda_avail else "N/A"
import json
print("__RESULT__:" + json.dumps({{"failed": failed, "cuda": cuda_avail, "device": device}}))
"""
    try:
        out = subprocess.check_output([path, "-c", check_code], text=True, stderr=subprocess.STDOUT).strip()
        res = None
        for line in out.splitlines():
            if line.startswith("__RESULT__:"):
                res = json.loads(line.split("__RESULT__:", 1)[1])
                break
        if res is None:
            raise ValueError("JSON result marker not found in output")
        if res["failed"]:
            for lib, err in res["failed"]:
                print(f"[WARNING] Missing dependency '{lib}': {err}")
        else:
            print(f"[OK] All critical libraries imported successfully.")
        print(f"[OK] CUDA Available: {res['cuda']} ({res['device']})")
        return len(res["failed"]) == 0
    except Exception as e:
        print(f"[FAIL] Subprocess check failed: {e}")
        return False

if __name__ == "__main__":
    torch_ok = verify_env("sci_torch", SCI_TORCH_PYTHON, ["torch", "pandas", "requests", "Bio", "esm"])
    chem_ok = verify_env("sci_chem", SCI_CHEM_PYTHON, ["rdkit", "deepchem", "pandas", "requests", "torch"])
    
    print("\nNote: Windows environment does not support pysam / SpliceAI. Live runs requiring local genomics must be run under WSL.")
    
    if torch_ok and chem_ok:
        print("\nAll environment checks passed (ignoring missing wrappers).")
        sys.exit(0)
    else:
        print("\nSome check failures or missing libraries detected.")
        sys.exit(1)
