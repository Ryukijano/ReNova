# Automated ADMET & Drug Repurposing Engine - E2E Testing Framework

This document outlines the testing architecture, validation mechanics, CLI options, mock API configurations, and environment checks for the Automated ADMET & Drug Repurposing Engine.

---

## 1. Test Suite Philosophy

The E2E testing framework is designed around the **opaque black-box principle**. Because the pipeline crosses multiple execution barriers (including multiple Conda environments, different package dependencies, and complex external integrations), direct in-memory mocking (e.g. `unittest.mock`) is insufficient. 

Instead, the framework is built on three core pillars:
1. **Subprocess Isolation**: Tests invoke the pipeline runner CLI (`run_pipeline.py`) as a subprocess, ensuring the execution environment remains clean and identical to production runs.
2. **Network Interception**: Rather than querying live databases (which triggers rate-limits, network flakes, or offline failures in `CODE_ONLY` environments), the framework boots a background local HTTP mock server. The runner routes all REST and GraphQL endpoints to this server using environment variables.
3. **Declarative Assertions**: E2E test cases are defined as static JSON files matching a schema (`tests/test_case_schema.json`). This decouples test criteria (like expected exit codes, log patterns, output file structures, column validations, and data ranges) from the execution runner.

---

## 2. Feature Inventory

The test runner handles 3 layers of validation:
- **Process Verification**: Asserts process exit codes, monitors execution times under safety thresholds, and scans standard output (`stdout`) and standard error (`stderr`) for expected success/failure signatures.
- **JSON File Assertions**: Parses intermediate JSON outputs (such as `target_retriever_output.json`), validates their structure, count limits, and verifies that nested file paths (like structure PDB files) physically exist and are non-empty on disk.
- **CSV Data Validation**: Validates final tabular reports against expected column schemas, verifies exact or minimum/maximum row bounds, and performs value-level validation (e.g. data types, numeric range constraints like $qed \in [0.0, 1.0]$, regular expression matching, and chemical SMILES format validation).

---

## 3. Test Runner CLI Usage

The test runner is located at `tests/run_tests.py` and can be executed from the project root.

```bash
# Run all discovered tests using the mock API server
python tests/run_tests.py --use-mocks

# Run tests corresponding only to Milestone 2 (filtering out future tests)
python tests/run_tests.py --milestone M2

# Run a specific test case by ID
python tests/run_tests.py --test-id tc_cystic_fibrosis_mock

# Run only Tier 2 tests (Mock E2E tests)
python tests/run_tests.py --tier 2

# Run with verbose outputs printing subprocess stdout/stderr in real-time
python tests/run_tests.py --verbose

# Prevent cleanup of generated temporary output files
python tests/run_tests.py --keep-temp-files
```

### CLI Arguments Reference

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--tier` | Choice | `all` | Filter by Tier (`1`, `2`, `3`, `4`, or `all`). |
| `--feature` | Choice | `all` | Filter by pipeline step/feature. |
| `--milestone` | Choice | `all` | Filter by capability milestone (`M2` to `M6`). Future tests are skipped. |
| `--disease` | String | `None` | Filter tests targeting a disease name. |
| `--test-id` | String | `None` | Filter by test case unique identifier. |
| `--sci-torch-python`| Path | *Standard Windows Path* | Path to `sci_torch` environment python binary. |
| `--sci-chem-python` | Path | *Standard Windows Path* | Path to `sci_chem` environment python binary. |
| `--use-mocks` | Flag | `True` | Starts the mock server and maps API endpoints to local mock profiles. |
| `--timeout` | Int | `300` | Subprocess execution timeout in seconds. |
| `--fail-fast` | Flag | `False` | Stop execution immediately on the first test failure. |
| `--verbose` | Flag | `False` | Print subprocess output logs to console. |
| `--keep-temp-files`| Flag | `False` | Retain workspace output files. |
| `--report-dir` | Path | `reports/` | Output directory for logs and test reports. |
| `--format` | Choice | `both` | Reports format (`json`, `xml`, `both`, or `none`). |

---

## 4. Mock API Mode

When running in mock mode, the test runner boots a lightweight HTTPServer thread on `localhost` before running a test case. 
The test case specifies a `"mock_profile"` (e.g. `"cystic_fibrosis"`), which is a directory containing mapping and static response files:
- `tests/mock_profiles/<profile>/mapping.json`: Contains HTTP method, path regex, and body matching rules, pointing each request to a local response file.
- `opentargets_query.json`: Mock GraphQL target identification data.
- `chembl_status.json` / `chembl_activities.json`: Mock ChEMBL status and chemical activities.
- `pubchem_compounds.json`: Mock PubChem compound annotations.
- `clinicaltrials_studies.json`: Mock ClinicalTrials.gov clinical trial search.
- `openfda_events.json`: Mock OpenFDA adverse event results.
- `dummy_structure.pdb`: A mock protein structure fallback.

The runner overrides the following environment variables to intercept calls from the pipeline subprocess:
- `OPENTARGETS_API_URL`
- `ALPHAFOLD_API_URL`
- `CHEMBL_API_URL`
- `CLINICALTRIALS_API_URL`
- `OPENFDA_API_URL`
- `ADMET_MOCK_PORT`
- `ADMET_MOCK_PROFILE`

---

## 5. Verification Details

To verify that the testing suite and environment are properly configured, execute the diagnostic verify script:
```bash
python scripts/verify_envs.py
```
This script validates:
- The existence of standard `sci_torch` and `sci_chem` Python installations.
- Success of importing critical packages (`torch`, `Bio`, `esm`, `rdkit`, `deepchem`, `pandas`, `requests`).
- GPU/CUDA acceleration availability.
- Pysam / SpliceAI compatibility warnings on Windows (suggesting WSL if missing).
