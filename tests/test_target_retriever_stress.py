import os
import sys
import unittest
import json
import shutil
import tempfile
import math
import requests
from unittest.mock import patch, MagicMock

# Add project root and src/ to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

import src.target_retriever as target_retriever

class MockResponse:
    def __init__(self, json_data, status_code=200, content=b"", text=""):
        self.json_data = json_data
        self.status_code = status_code
        self.content = content
        self.text = text if text else (content.decode("utf-8") if isinstance(content, bytes) else str(content))

    def json(self):
        return self.json_data

class TestTargetRetrieverStress(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.temp_dir, "targets.json")
        self.structure_dir = os.path.join(self.temp_dir, "structures")
        self.log_file = os.path.join(self.temp_dir, "retriever_stress.log")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("requests.post")
    def test_empty_or_invalid_inputs(self, mock_post):
        """
        1. Test boundaries: Empty/very long/invalid disease names and EFO IDs.
        """
        # Scenario A: Disease not found in database (invalid/unknown disease)
        mock_post.return_value = MockResponse({"data": {"disease": None}}, status_code=200)
        
        # Test CLI execution exits with code 1 and logs error
        test_args = [
            "target_retriever.py",
            "--disease", "NonExistentDisease123",
            "--output", self.output_file,
            "--structure-dir", self.structure_dir,
            "--log-file", self.log_file,
            "--verbose"
        ]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 1)
        
        # Check log contains error message
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, "r", encoding="utf-8") as lf:
            log_content = lf.read()
            self.assertIn("Disease/EFO ID not found in OpenTargets database", log_content)

        # Scenario B: Extremely long disease name
        long_disease = "A" * 5000
        mock_post.reset_mock()
        mock_post.return_value = MockResponse({"data": {"disease": None}}, status_code=200)
        
        test_args_long = [
            "target_retriever.py",
            "--disease", long_disease,
            "--output", self.output_file,
            "--structure-dir", self.structure_dir,
            "--log-file", self.log_file
        ]
        with patch.object(sys, "argv", test_args_long):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 1)
        
        # Verify that requests.post was called with the extremely long disease name
        mock_post.assert_called_once()
        called_json = mock_post.call_args[1]["json"]
        self.assertEqual(called_json["variables"]["disease"], long_disease)

        # Scenario C: Empty disease parameter and EFO ID parameters directly to query function
        with self.assertRaises(ValueError):
            target_retriever.query_opentargets(disease=None, efo_id=None)

    @patch("requests.post")
    @patch("requests.get")
    def test_extremely_large_mock_query_responses(self, mock_get, mock_post):
        """
        2. Test boundaries: Extremely large mock query responses (e.g. thousands of targets, verifying sort and limit flags).
        """
        # Generate 1500 targets mock response
        rows = []
        for i in range(1500):
            rows.append({
                "target": {
                    "id": f"ENSG{i:011d}",
                    "approvedSymbol": f"GENE_{i}",
                    "proteinIds": [{"id": f"P{i:05d}", "source": "uniprot_swissprot"}],
                    "uniprotIds": [f"P{i:05d}"]
                },
                # Score ranges from 0.1 to 0.99
                "score": 0.1 + (i % 90) / 100.0
            })
            
        mock_post.return_value = MockResponse({
            "data": {
                "disease": {
                    "name": "Large Scale Disease",
                    "associatedTargets": {"rows": rows}
                }
            }
        }, status_code=200)
        
        # ClinVar count returns 10 for even indices, 500 for odd indices
        def clinvar_side_effect(*args, **kwargs):
            term = kwargs.get("params", {}).get("term", "")
            # Extract index from gene symbol in term
            import re
            match = re.search(r'GENE_(\d+)', term)
            if match:
                idx = int(match.group(1))
                return MockResponse({"esearchresult": {"count": str(10 + (idx % 300) * 10)}}, status_code=200)
            return MockResponse({"esearchresult": {"count": "0"}}, status_code=200)
            
        # Structure download mock response
        def struct_side_effect(url, *args, **kwargs):
            if "alphafold.ebi.ac.uk" in url:
                # Metadata request
                uniprot_id = url.split("/")[-1]
                return MockResponse([{"uniprotId": uniprot_id, "pdbUrl": f"https://mock.af/{uniprot_id}.pdb"}], status_code=200)
            elif "mock.af" in url:
                # PDB download request
                return MockResponse({}, status_code=200, content=b"HEADER    MOCK LARGE PDB")
            return MockResponse({}, status_code=404)

        mock_get.side_effect = lambda url, *args, **kwargs: clinvar_side_effect(*args, **kwargs) if "eutils.ncbi" in url else struct_side_effect(url, *args, **kwargs)

        # Execute target retriever with limit=12 and min_score=0.4
        test_args = [
            "target_retriever.py",
            "--disease", "Large Scale Disease",
            "--output", self.output_file,
            "--structure-dir", self.structure_dir,
            "--log-file", self.log_file,
            "--limit", "12",
            "--min-score", "0.4",
            "--verbose"
        ]
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 0)
            
        # Verify the output format and constraints
        self.assertTrue(os.path.exists(self.output_file))
        with open(self.output_file, "r") as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 12)
        
        # Verify that output is sorted by association_score descending
        scores = [item["association_score"] for item in data]
        sorted_scores = sorted(scores, reverse=True)
        self.assertEqual(scores, sorted_scores)
        
        # Verify all scores are >= 0.4
        for item in data:
            self.assertGreaterEqual(item["association_score"], 0.4)
            self.assertTrue(os.path.exists(item["structure_path"]))
            
        # Verify that the structure downloads were limited only to the top 12 targets
        # We check the structure directory contains exactly the top 12 UniProt structures
        struct_files = os.listdir(self.structure_dir)
        self.assertEqual(len(struct_files), 12)

    @patch("requests.post")
    @patch("requests.get")
    def test_mock_api_timeouts_connection_errors_and_rate_limits(self, mock_get, mock_post):
        """
        3. Test boundaries: Mock API timeouts, connection errors, and rate limits.
        Check that script handles them gracefully and logs correctly.
        """
        # Case 3.1: OpenTargets Connection Error (network down)
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused by mock")
        test_args = [
            "target_retriever.py",
            "--disease", "Cystic Fibrosis",
            "--output", self.output_file,
            "--log-file", self.log_file
        ]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 1)
        
        with open(self.log_file, "r", encoding="utf-8") as lf:
            self.assertIn("Failed to connect to OpenTargets API", lf.read())

        # Case 3.2: OpenTargets API returns HTTP 429 Rate Limit
        mock_post.side_effect = None
        mock_post.return_value = MockResponse({}, status_code=429)
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 1)
            
        with open(self.log_file, "r", encoding="utf-8") as lf:
            self.assertIn("OpenTargets API returned HTTP status 429", lf.read())

        # Case 3.3: ClinVar returns HTTP 429 Rate Limit (the script should NOT crash, but default count to 0 and continue)
        mock_post.return_value = MockResponse({
            "data": {
                "disease": {
                    "name": "Cystic Fibrosis",
                    "associatedTargets": {
                        "rows": [{
                            "target": {
                                "id": "ENSG00000001626",
                                "approvedSymbol": "CFTR",
                                "proteinIds": [{"id": "P13569", "source": "uniprot_swissprot"}],
                                "uniprotIds": ["P13569"]
                            },
                            "score": 0.95
                        }]
                    }
                }
            }
        }, status_code=200)
        
        # Mock get: ClinVar returns 429, AlphaFold DB metadata returns 200, AF structure download returns 200
        def mock_get_behavior(url, *args, **kwargs):
            if "ncbi.nlm.nih.gov" in url:
                return MockResponse({}, status_code=429)
            elif "alphafold.ebi.ac.uk" in url:
                return MockResponse([{"pdbUrl": "https://mock.af/P13569.pdb"}], status_code=200)
            elif "mock.af" in url:
                return MockResponse({}, status_code=200, content=b"HEADER    MOCK PDB")
            return MockResponse({}, status_code=404)
            
        mock_get.side_effect = mock_get_behavior
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 0)
            
        # Verify ClinVar failure is logged and the count defaulted to 0
        with open(self.log_file, "r", encoding="utf-8") as lf:
            log_data = lf.read()
            self.assertIn("ClinVar API returned status code 429", log_data)
            
        # Verify final output exists and has score corresponding to ClinVar=0 (0.7 * 0.95 + 0 = 0.665)
        with open(self.output_file, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertAlmostEqual(data[0]["association_score"], 0.665, places=4)

        # Case 3.4: Ensembl REST fallback returns 429/timeout (script should default to UNKNOWN UniProt ID and continue)
        mock_post.return_value = MockResponse({
            "data": {
                "disease": {
                    "name": "Cystic Fibrosis",
                    "associatedTargets": {
                        "rows": [{
                            "target": {
                                "id": "ENSG00000001626",
                                "approvedSymbol": "CFTR",
                                "proteinIds": [], # No UniProt IDs in target row, forces Ensembl fallback
                                "uniprotIds": []
                            },
                            "score": 0.8
                        }]
                    }
                }
            }
        }, status_code=200)
        
        def mock_get_ensembl_error(url, *args, **kwargs):
            if "rest.ensembl.org" in url:
                return MockResponse({}, status_code=429)
            elif "ncbi.nlm.nih.gov" in url:
                return MockResponse({"esearchresult": {"count": "100"}}, status_code=200)
            return MockResponse({}, status_code=404)
            
        mock_get.side_effect = mock_get_ensembl_error
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 0)
            
        with open(self.output_file, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["uniprot_id"], "UNKNOWN")
        self.assertIsNone(data[0]["structure_path"])

    @patch("requests.post")
    @patch("requests.get")
    @patch("esm.pretrained.esmfold_v1")
    def test_local_esmfold_prediction_fallback(self, mock_esmfold, mock_get, mock_post):
        """
        4. Test boundaries: Local ESMFold prediction fallback checks (model caching works/fails).
        """
        # OpenTargets returns 1 target without reviewed proteinIds list, but with uniprotIds
        mock_post.return_value = MockResponse({
            "data": {
                "disease": {
                    "name": "Cystic Fibrosis",
                    "associatedTargets": {
                        "rows": [{
                            "target": {
                                "id": "ENSG00000001626",
                                "approvedSymbol": "CFTR",
                                "proteinIds": [],
                                "uniprotIds": ["P13569"]
                            },
                            "score": 0.90
                        }]
                    }
                }
            }
        }, status_code=200)
        
        # Test Case 4.1: Fallback enabled, model caching works
        # Setup mocks:
        # - ClinVar returns count 200
        # - AlphaFold DB metadata returns 404 (to trigger fallback)
        # - UniProt FASTA returns sequence
        def mock_get_fallback_success(url, *args, **kwargs):
            if "ncbi.nlm.nih.gov" in url:
                return MockResponse({"esearchresult": {"count": "200"}}, status_code=200)
            elif "alphafold.ebi.ac.uk" in url:
                return MockResponse({}, status_code=404)
            elif "rest.uniprot.org" in url:
                return MockResponse({}, status_code=200, content=b">sp|P13569\nMQRSPLEKASVVSKL")
            return MockResponse({}, status_code=404)
            
        mock_get.side_effect = mock_get_fallback_success
        
        # Mock ESM model prediction
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        mock_model.cuda.return_value = mock_model
        mock_model.infer_pdb.return_value = "HEADER    MOCK ESMFOLD PDB DATA"
        mock_esmfold.return_value = mock_model
        
        test_args_fallback = [
            "target_retriever.py",
            "--disease", "Cystic Fibrosis",
            "--output", self.output_file,
            "--structure-dir", self.structure_dir,
            "--log-file", self.log_file,
            "--esmfold-fallback",
            "--verbose"
        ]
        
        with patch.object(sys, "argv", test_args_fallback):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 0)
            
        # Verify structure file was written with the mock ESMFold output
        struct_path = os.path.join(self.structure_dir, "P13569.pdb")
        self.assertTrue(os.path.exists(struct_path))
        with open(struct_path, "r", encoding="utf-8") as sf:
            self.assertEqual(sf.read(), "HEADER    MOCK ESMFOLD PDB DATA")
            
        # Check logs show ESMFold execution
        with open(self.log_file, "r", encoding="utf-8") as lf:
            log_data = lf.read()
            self.assertIn("Attempting ESMFold fallback for P13569", log_data)
            self.assertIn("Successfully predicted and saved ESMFold structure", log_data)

        # Test Case 4.2: Fallback enabled, model caching fails (model weights fail to load/download throws exception)
        # We clean the directory and log file first
        shutil.rmtree(self.structure_dir, ignore_errors=True)
        os.makedirs(self.structure_dir, exist_ok=True)
        open(self.log_file, "w").close()
        
        # Make model loading raise RuntimeError (simulating missing cache / network download failure)
        mock_esmfold.side_effect = RuntimeError("Could not download/cache model weights")
        
        with patch.object(sys, "argv", test_args_fallback):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 0) # Script should NOT crash, just log and write structure_path: null
            
        # Verify output exists but structure_path is None
        with open(self.output_file, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertIsNone(data[0]["structure_path"])
        
        # Verify failure is logged
        with open(self.log_file, "r", encoding="utf-8") as lf:
            self.assertIn("Local ESMFold prediction failed for P13569: Could not download/cache model weights", lf.read())

if __name__ == "__main__":
    unittest.main()
