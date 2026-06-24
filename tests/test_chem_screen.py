import os
import sys
import unittest
import json
import csv
import shutil
import tempfile
from unittest.mock import patch, MagicMock

# Add project root and src/ to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

import src.chem_screen as chem_screen

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

class TestChemScreen(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.target_json = os.path.join(self.temp_dir, "targets.json")
        self.output_csv = os.path.join(self.temp_dir, "compounds.csv")
        
        # Write default target JSON
        self.default_targets = [
            {
                "gene_symbol": "CFTR",
                "ensembl_id": "ENSG00000001626",
                "uniprot_id": "P13569",
                "association_score": 0.8847,
                "structure_path": "dummy.pdb"
            }
        ]
        with open(self.target_json, "w", encoding="utf-8") as f:
            json.dump(self.default_targets, f, indent=2)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("requests.get")
    def test_mock_mode_success(self, mock_get):
        # Setup mock responses
        status_res = MockResponse({"status": "UP"})
        activity_res = MockResponse({
            "activities": [
                {
                    "molecule_chembl_id": "CHEMBL1082",
                    "canonical_smiles": "CCN(CC)CCO",
                    "standard_relation": "=",
                    "standard_value": "4.2",
                    "standard_units": "nM"
                }
            ]
        })
        mock_get.side_effect = [status_res, activity_res]

        test_args = [
            "chem_screen.py",
            "--target-json", self.target_json,
            "--output-csv", self.output_csv,
            "--mock", "true"
        ]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                chem_screen.main()
            self.assertEqual(cm.exception.code, 0)

        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gene_symbol"], "CFTR")
        self.assertEqual(rows[0]["uniprot_id"], "P13569")
        self.assertEqual(rows[0]["compound_id"], "CHEMBL1082")
        self.assertEqual(rows[0]["smiles"], "CCN(CC)CCO")
        self.assertEqual(rows[0]["relation"], "=")
        self.assertEqual(float(rows[0]["value"]), 4.2)
        self.assertEqual(rows[0]["units"], "nM")

    @patch("requests.get")
    def test_mock_mode_invalid_smiles_filtered(self, mock_get):
        status_res = MockResponse({"status": "UP"})
        # One valid compound and one invalid
        activity_res = MockResponse({
            "activities": [
                {
                    "molecule_chembl_id": "CHEMBL1082",
                    "canonical_smiles": "CCN(CC)CCO",
                    "standard_relation": "=",
                    "standard_value": "4.2",
                    "standard_units": "nM"
                },
                {
                    "molecule_chembl_id": "CHEMBL_BAD",
                    "canonical_smiles": "INVALID_SMILES_STRING",
                    "standard_relation": "=",
                    "standard_value": "100.0",
                    "standard_units": "nM"
                }
            ]
        })
        mock_get.side_effect = [status_res, activity_res]

        test_args = [
            "chem_screen.py",
            "--target-json", self.target_json,
            "--output-csv", self.output_csv,
            "--mock", "true"
        ]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                chem_screen.main()
            self.assertEqual(cm.exception.code, 0)

        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["compound_id"], "CHEMBL1082")

    @patch("chembl_webresource_client.new_client.new_client")
    def test_real_mode_success(self, mock_new_client):
        # Setup real mode mocks
        mock_target = MagicMock()
        mock_target.filter.return_value = [{"target_chembl_id": "CHEMBL4051"}]
        
        mock_activity = MagicMock()
        mock_activity.filter.return_value = [
            {
                "molecule_chembl_id": "CHEMBL403296",
                "canonical_smiles": "CCN(CC)CCO",
                "standard_relation": "=",
                "standard_value": "160000.0",
                "standard_units": "nM",
                "target_chembl_id": "CHEMBL4051"
            }
        ]
        
        mock_molecule = MagicMock()
        mock_molecule.filter.return_value = [
            {
                "molecule_chembl_id": "CHEMBL403296",
                "max_phase": 0,
                "molecule_properties": {
                    "full_mwt": "365.47",
                    "alogp": "5.18"
                }
            }
        ]
        
        # Configure mock_new_client properties
        mock_new_client.target = mock_target
        mock_new_client.activity = mock_activity
        mock_new_client.molecule = mock_molecule

        test_args = [
            "chem_screen.py",
            "--target-json", self.target_json,
            "--output-csv", self.output_csv,
            "--mock", "false"
        ]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                chem_screen.main()
            self.assertEqual(cm.exception.code, 0)

        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gene_symbol"], "CFTR")
        self.assertEqual(rows[0]["uniprot_id"], "P13569")
        self.assertEqual(rows[0]["compound_id"], "CHEMBL403296")
        self.assertEqual(rows[0]["smiles"], "CCN(CC)CCO")
        self.assertEqual(float(rows[0]["value"]), 160000.0)

    @patch("chembl_webresource_client.new_client.new_client")
    def test_real_mode_max_phase_and_smiles_filtering(self, mock_new_client):
        mock_target = MagicMock()
        mock_target.filter.return_value = [{"target_chembl_id": "CHEMBL4051"}]

        # Two activities
        mock_activity = MagicMock()
        mock_activity.filter.return_value = [
            {
                "molecule_chembl_id": "CHEMBL_GOOD",
                "canonical_smiles": "CCN(CC)CCO",
                "standard_relation": "=",
                "standard_value": "160000.0",
                "standard_units": "nM",
                "target_chembl_id": "CHEMBL4051"
            },
            {
                "molecule_chembl_id": "CHEMBL_BAD_PHASE",
                "canonical_smiles": "CCN(CC)CCO",
                "standard_relation": "=",
                "standard_value": "100.0",
                "standard_units": "nM",
                "target_chembl_id": "CHEMBL4051"
            },
            {
                "molecule_chembl_id": "CHEMBL_MISSING_PHASE",
                "canonical_smiles": "CCN(CC)CCO",
                "standard_relation": "=",
                "standard_value": "200.0",
                "standard_units": "nM",
                "target_chembl_id": "CHEMBL4051"
            },
            {
                "molecule_chembl_id": "CHEMBL_BAD_SMILES",
                "canonical_smiles": "INVALID_SMILES",
                "standard_relation": "=",
                "standard_value": "300.0",
                "standard_units": "nM",
                "target_chembl_id": "CHEMBL4051"
            }
        ]

        # Molecule details
        mock_molecule = MagicMock()
        mock_molecule.filter.return_value = [
            {
                "molecule_chembl_id": "CHEMBL_GOOD",
                "max_phase": 0,
                "molecule_properties": {"full_mwt": "365.47", "alogp": "5.18"}
            },
            {
                "molecule_chembl_id": "CHEMBL_BAD_PHASE",
                "max_phase": -1,
                "molecule_properties": {"full_mwt": "365.47", "alogp": "5.18"}
            },
            {
                "molecule_chembl_id": "CHEMBL_MISSING_PHASE",
                "max_phase": None,
                "molecule_properties": {"full_mwt": "365.47", "alogp": "5.18"}
            },
            {
                "molecule_chembl_id": "CHEMBL_BAD_SMILES",
                "max_phase": 2,
                "molecule_properties": {"full_mwt": "365.47", "alogp": "5.18"}
            }
        ]

        mock_new_client.target = mock_target
        mock_new_client.activity = mock_activity
        mock_new_client.molecule = mock_molecule

        test_args = [
            "chem_screen.py",
            "--target-json", self.target_json,
            "--output-csv", self.output_csv,
            "--mock", "false"
        ]

        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                chem_screen.main()
            self.assertEqual(cm.exception.code, 0)

        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Only CHEMBL_GOOD should pass all filters!
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["compound_id"], "CHEMBL_GOOD")

if __name__ == "__main__":
    unittest.main()
