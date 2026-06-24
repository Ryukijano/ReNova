import os
import sys
import unittest
import json
import shutil
import tempfile
import math
from unittest.mock import patch, MagicMock, mock_open

# Add project root and src/ to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

import src.target_retriever as target_retriever

class MockResponse:
    def __init__(self, json_data, status_code=200, content=b""):
        self.json_data = json_data
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8") if isinstance(content, bytes) else content

    def json(self):
        return self.json_data

class TestTargetRetriever(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.temp_dir, "targets.json")
        self.structure_dir = os.path.join(self.temp_dir, "structures")
        self.log_file = os.path.join(self.temp_dir, "retriever.log")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_composite_score_calculation(self):
        # S_final = 0.7 * S_OT + 0.3 * (ln(C_CV + 1) / ln(3000 + 1))
        # Case 1: ClinVar count = 0
        score = target_retriever.compute_composite_score(0.8, 0)
        self.assertAlmostEqual(score, 0.7 * 0.8 + 0.3 * 0.0, places=4)
        
        # Case 2: ClinVar count = 3000
        score = target_retriever.compute_composite_score(1.0, 3000)
        self.assertAlmostEqual(score, 0.7 * 1.0 + 0.3 * 1.0, places=4)
        
        # Case 3: ClinVar count = 4000 (capped at 3000)
        score = target_retriever.compute_composite_score(0.5, 4000)
        self.assertAlmostEqual(score, 0.7 * 0.5 + 0.3 * 1.0, places=4)
        
        # Case 4: ClinVar count = 150
        expected = 0.7 * 0.6 + 0.3 * (math.log(150 + 1) / math.log(3000 + 1))
        score = target_retriever.compute_composite_score(0.6, 150)
        self.assertAlmostEqual(score, expected, places=4)

    def test_get_uniprot_id_priority(self):
        # Test Case 1: Swissprot in proteinIds
        target = {
            "id": "ENSG00000001626",
            "proteinIds": [
                {"id": "A0A024R2B3", "source": "uniprot_trembl"},
                {"id": "P13569", "source": "uniprot_swissprot"}
            ],
            "uniprotIds": ["Q12345"]
        }
        uid = target_retriever.get_uniprot_id(target)
        self.assertEqual(uid, "P13569")

        # Test Case 2: Only Trembl in proteinIds
        target = {
            "id": "ENSG00000001626",
            "proteinIds": [
                {"id": "A0A024R2B3", "source": "uniprot_trembl"}
            ],
            "uniprotIds": ["Q12345"]
        }
        uid = target_retriever.get_uniprot_id(target)
        self.assertEqual(uid, "A0A024R2B3")

        # Test Case 3: No proteinIds, use uniprotIds list
        target = {
            "id": "ENSG00000001626",
            "proteinIds": [],
            "uniprotIds": ["Q12345", "P13569"]
        }
        uid = target_retriever.get_uniprot_id(target)
        self.assertEqual(uid, "Q12345")

    @patch("requests.get")
    def test_get_uniprot_id_ensembl_fallback(self, mock_get):
        # Test Case 4: Fallback to Ensembl REST API
        target = {
            "id": "ENSG00000001626",
            "proteinIds": [],
            "uniprotIds": []
        }
        
        # Ensembl returns Swiss-Prot xref
        mock_get.return_value = MockResponse([
            {"dbname": "Uniprot/SPTREMBL", "primary_id": "A0A024R2B3"},
            {"dbname": "Uniprot/SWISSPROT", "primary_id": "P13569"}
        ], status_code=200)
        
        uid = target_retriever.get_uniprot_id(target, ensembl_url="https://mock.ensembl.org")
        self.assertEqual(uid, "P13569")
        mock_get.assert_called_with("https://mock.ensembl.org/xrefs/id/ENSG00000001626", headers={"Content-Type": "application/json"}, timeout=15)

    @patch("requests.get")
    def test_get_clinvar_count(self, mock_get):
        mock_get.return_value = MockResponse({
            "esearchresult": {
                "count": "245"
            }
        }, status_code=200)
        
        count = target_retriever.get_clinvar_count("CFTR", clinvar_url="https://mock.clinvar.org")
        self.assertEqual(count, 245)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://mock.clinvar.org")
        self.assertEqual(kwargs["params"]["db"], "clinvar")
        self.assertIn('"CFTR"[Gene]', kwargs["params"]["term"])
        self.assertIn('pathogenic[clinsig]', kwargs["params"]["term"])

    @patch("requests.get")
    def test_fetch_structure_alphafold_success(self, mock_get):
        # Mock AF prediction metadata
        metadata_res = MockResponse([
            {"uniprotId": "P13569", "pdbUrl": "https://mock.alphafold/AF-P13569.pdb"}
        ], status_code=200)
        
        # Mock AF PDB file content download
        pdb_content = b"HEADER    MOCK PDB DATA"
        pdb_res = MockResponse({}, status_code=200, content=pdb_content)
        
        mock_get.side_effect = [metadata_res, pdb_res]
        
        path = target_retriever.fetch_structure("P13569", self.structure_dir, alphafold_url="https://mock.af")
        
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), pdb_content)

    @patch("requests.get")
    @patch("esm.pretrained.esmfold_v1")
    def test_fetch_structure_esmfold_fallback_success(self, mock_esmfold, mock_get):
        # Mock AlphaFold metadata returns 404
        af_metadata_res = MockResponse({}, status_code=404)
        
        # Mock UniProt FASTA returns sequence
        fasta_content = b">sp|P13569\nMQRSPLEK\nASVVSKL\n"
        fasta_res = MockResponse({}, status_code=200, content=fasta_content)
        
        mock_get.side_effect = [af_metadata_res, fasta_res]
        
        # Mock ESMFold prediction
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        mock_model.cuda.return_value = mock_model
        mock_model.infer_pdb.return_value = "HEADER    MOCK ESMFOLD PDB"
        mock_esmfold.return_value = mock_model
        
        path = target_retriever.fetch_structure(
            "P13569", 
            self.structure_dir, 
            alphafold_url="https://mock.af",
            uniprot_fasta_url="https://mock.uniprot",
            esmfold_fallback=True
        )
        
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as f:
            self.assertEqual(f.read(), "HEADER    MOCK ESMFOLD PDB")
            
        mock_esmfold.assert_called_once()
        mock_model.infer_pdb.assert_called_with("MQRSPLEKASVVSKL")

    @patch("requests.get")
    def test_fetch_structure_failure(self, mock_get):
        # Mock AlphaFold metadata returns 404 and fallback not set
        mock_get.return_value = MockResponse({}, status_code=404)
        
        path = target_retriever.fetch_structure(
            "P13569", 
            self.structure_dir, 
            alphafold_url="https://mock.af",
            esmfold_fallback=False
        )
        self.assertIsNone(path)

    @patch("requests.post")
    @patch("requests.get")
    def test_cli_execution_success(self, mock_get, mock_post):
        # OpenTargets post mock
        mock_post.return_value = MockResponse({
            "data": {
                "disease": {
                    "name": "Cystic Fibrosis",
                    "associatedTargets": {
                        "rows": [
                            {
                                "target": {
                                    "id": "ENSG00000001626",
                                    "approvedSymbol": "CFTR",
                                    "proteinIds": [
                                        {"id": "P13569", "source": "uniprot_swissprot"}
                                    ],
                                    "uniprotIds": ["P13569"]
                                },
                                "score": 0.98
                            }
                        ]
                    }
                }
            }
        }, status_code=200)
        
        # ClinVar get mock -> count 200
        clinvar_res = MockResponse({"esearchresult": {"count": "200"}}, status_code=200)
        # AlphaFold DB get mock -> PDB metadata
        af_metadata_res = MockResponse([{"pdbUrl": "https://mock.af/AF-P13569.pdb"}], status_code=200)
        # AlphaFold PDB download get mock
        af_pdb_res = MockResponse({}, status_code=200, content=b"HEADER    MOCK PDB")
        
        mock_get.side_effect = [clinvar_res, af_metadata_res, af_pdb_res]
        
        test_args = [
            "target_retriever.py",
            "--disease", "Cystic Fibrosis",
            "--output", self.output_file,
            "--structure-dir", self.structure_dir,
            "--log-file", self.log_file,
            "--min-score", "0.2"
        ]
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 0)
            
        self.assertTrue(os.path.exists(self.output_file))
        with open(self.output_file, "r") as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["gene_symbol"], "CFTR")
        self.assertEqual(data[0]["ensembl_id"], "ENSG00000001626")
        self.assertEqual(data[0]["uniprot_id"], "P13569")
        # Final score calculation:
        # S_final = 0.7 * 0.98 + 0.3 * (ln(200 + 1) / ln(3000 + 1))
        # = 0.686 + 0.3 * (5.3033 / 8.0067)
        # = 0.686 + 0.3 * 0.6623 = 0.686 + 0.1987 = 0.8847
        self.assertAlmostEqual(data[0]["association_score"], 0.8847, places=4)
        self.assertTrue(data[0]["structure_path"].endswith("P13569.pdb"))

    @patch("requests.post")
    def test_cli_disease_not_found(self, mock_post):
        # Disease not found -> None
        mock_post.return_value = MockResponse({
            "data": {
                "disease": None
            }
        }, status_code=200)
        
        test_args = [
            "target_retriever.py",
            "--disease", "Unknown Disease",
            "--output", self.output_file,
            "--log-file", self.log_file
        ]
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                target_retriever.main()
            self.assertEqual(cm.exception.code, 1)

if __name__ == "__main__":
    unittest.main()
