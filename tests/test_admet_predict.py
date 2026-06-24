import os
import sys
import unittest
import csv
import tempfile
import shutil
import numpy as np
from unittest.mock import patch, MagicMock

# Add project root and src/ to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

import src.admet_predict as admet_predict

class TestAdmetPredict(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.input_csv = os.path.join(self.temp_dir, "input.csv")
        self.output_csv = os.path.join(self.temp_dir, "output.csv")
        
        # Write a sample input CSV
        self.sample_rows = [
            {"gene_symbol": "CFTR", "uniprot_id": "P13569", "compound_id": "CHEMBL1", "smiles": "CC(=O)Oc1ccccc1C(=O)O", "relation": "=", "value": "10.0", "units": "nM"},
            {"gene_symbol": "CFTR", "uniprot_id": "P13569", "compound_id": "CHEMBL2", "smiles": "CCO", "relation": "=", "value": "5.0", "units": "nM"}
        ]
        with open(self.input_csv, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.sample_rows[0].keys())
            writer.writeheader()
            writer.writerows(self.sample_rows)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculate_descriptors_valid(self):
        # Aspirin
        smiles = "CC(=O)Oc1ccccc1C(=O)O"
        desc = admet_predict.calculate_descriptors(smiles)
        self.assertIsNotNone(desc)
        self.assertIn("logp", desc)
        self.assertIn("qed", desc)
        self.assertIn("hcl_solubility", desc)
        self.assertIn("violations", desc)
        self.assertTrue(0.0 <= desc["qed"] <= 1.0)
        self.assertTrue(desc["mw"] > 0)
        
    def test_calculate_descriptors_invalid(self):
        smiles = "INVALID_SMILES"
        desc = admet_predict.calculate_descriptors(smiles)
        self.assertIsNone(desc)

    def test_predict_row_mock(self):
        smiles = "CC(=O)Oc1ccccc1C(=O)O"
        pred = admet_predict.predict_row_mock(smiles)
        self.assertIsNotNone(pred)
        for key in ["hcl_solubility", "caco2_permeability", "logp", "qed", "toxicity_score", "admet_score"]:
            self.assertIn(key, pred)
        self.assertTrue(0.0 <= pred["qed"] <= 1.0)
        self.assertTrue(0.0 <= pred["admet_score"] <= 1.0)
        self.assertTrue(0.0 <= pred["toxicity_score"] <= 1.0)

    def test_get_toxicity_score_shapes(self):
        # Shape (T, N, C) - SklearnModel
        # 2 tasks, 3 samples, 2 classes
        preds_sklearn = np.array([
            [[0.9, 0.1], [0.8, 0.2], [0.7, 0.3]], # task 0
            [[0.4, 0.6], [0.5, 0.5], [0.3, 0.7]]  # task 1 (CT_TOX)
        ])
        score = admet_predict.get_toxicity_score(preds_sklearn, 0)
        self.assertEqual(score, 0.6)
        score_1 = admet_predict.get_toxicity_score(preds_sklearn, 1)
        self.assertEqual(score_1, 0.5)

        # Shape (N, T, C) - AttentiveFPModel
        preds_torch = np.array([
            [[0.9, 0.1], [0.4, 0.6]], # sample 0 (task 0, task 1)
            [[0.8, 0.2], [0.5, 0.5]], # sample 1
            [[0.7, 0.3], [0.3, 0.7]]  # sample 2
        ])
        score = admet_predict.get_toxicity_score(preds_torch, 0)
        self.assertEqual(score, 0.6)
        
        # 2D shape (N, C)
        preds_2d = np.array([
            [0.4, 0.6],
            [0.5, 0.5]
        ])
        score = admet_predict.get_toxicity_score(preds_2d, 0)
        self.assertEqual(score, 0.6)

    def test_get_bbbp_prob_shapes(self):
        # Shape (T, N, C) - SklearnModel (T=1)
        preds_sklearn = np.array([
            [[0.3, 0.7], [0.2, 0.8]]
        ])
        prob = admet_predict.get_bbbp_prob(preds_sklearn, 0)
        self.assertEqual(prob, 0.7)

        # Shape (N, T, C) - AttentiveFPModel (T=1)
        preds_torch = np.array([
            [[0.3, 0.7]],
            [[0.2, 0.8]]
        ])
        prob = admet_predict.get_bbbp_prob(preds_torch, 0)
        self.assertEqual(prob, 0.7)

        # 2D shape (N, C)
        preds_2d = np.array([
            [0.3, 0.7],
            [0.2, 0.8]
        ])
        prob = admet_predict.get_bbbp_prob(preds_2d, 0)
        self.assertEqual(prob, 0.7)

    def test_empty_input_file(self):
        empty_csv = os.path.join(self.temp_dir, "empty.csv")
        with open(empty_csv, mode="w", encoding="utf-8", newline="") as f:
            # only headers
            writer = csv.writer(f)
            writer.writerow(["gene_symbol", "compound_id", "smiles"])
            
        test_args = [
            "admet_predict.py",
            "--input-csv", empty_csv,
            "--output-csv", self.output_csv,
            "--mock", "true"
        ]
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                admet_predict.main()
            self.assertEqual(cm.exception.code, 0)
            
        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 1) # only headers
        self.assertEqual(rows[0][0], "gene_symbol")
        self.assertEqual(rows[0][-1], "admet_score")

    @patch("src.admet_predict.predict_row_mock")
    def test_cli_mock_mode(self, mock_predict_row):
        mock_predict_row.return_value = {
            "hcl_solubility": -2.5,
            "caco2_permeability": 2.1,
            "logp": 1.5,
            "qed": 0.8,
            "toxicity_score": 0.15,
            "admet_score": 0.75
        }
        
        test_args = [
            "admet_predict.py",
            "--input-csv", self.input_csv,
            "--output-csv", self.output_csv,
            "--mock", "true"
        ]
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                admet_predict.main()
            self.assertEqual(cm.exception.code, 0)
            
        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["gene_symbol"], "CFTR")
        self.assertEqual(rows[0]["compound_id"], "CHEMBL1")
        self.assertEqual(float(rows[0]["admet_score"]), 0.75)
        self.assertEqual(float(rows[0]["qed"]), 0.8)

    @patch("src.admet_predict.load_or_train_clintox")
    @patch("src.admet_predict.load_or_train_bbbp")
    @patch("src.admet_predict.predict_row_live")
    def test_cli_live_mode_mocked(self, mock_predict_live, mock_load_bbbp, mock_load_clintox):
        mock_load_clintox.return_value = (MagicMock(), "MorganRF")
        mock_load_bbbp.return_value = (MagicMock(), "MorganRF")
        mock_predict_live.return_value = {
            "hcl_solubility": -1.2,
            "caco2_permeability": 1.8,
            "logp": 2.1,
            "qed": 0.72,
            "toxicity_score": 0.22,
            "admet_score": 0.65
        }
        
        test_args = [
            "admet_predict.py",
            "--input-csv", self.input_csv,
            "--output-csv", self.output_csv,
            "--mock", "false"
        ]
        
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                admet_predict.main()
            self.assertEqual(cm.exception.code, 0)
            
        self.assertTrue(os.path.exists(self.output_csv))
        with open(self.output_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(len(rows), 2)
        self.assertEqual(float(rows[0]["admet_score"]), 0.65)
        self.assertEqual(float(rows[0]["caco2_permeability"]), 1.8)

    def test_live_models_load_or_train_fallback(self):
        """Test load_or_train fallback structure for ClinTox and BBBP."""
        # Use a temporary directory for models to prevent overwriting existing trained ones
        temp_model_dir_clintox = os.path.join(self.temp_dir, "models_clintox")
        temp_model_dir_bbbp = os.path.join(self.temp_dir, "models_bbbp")
        
        # Test loading or training ClinTox Random Forest model
        # Using a patch to force RandomForest fallback even if DGL is active (to test the code path)
        with patch("src.admet_predict.DGL_AVAILABLE", False):
            model, model_type = admet_predict.load_or_train_clintox(temp_model_dir_clintox)
            self.assertEqual(model_type, "MorganRF")
            self.assertTrue(os.path.exists(os.path.join(temp_model_dir_clintox, "model.joblib")))
            
            # Predict using the reloaded model path
            model_reloaded, model_type_reloaded = admet_predict.load_or_train_clintox(temp_model_dir_clintox)
            self.assertEqual(model_type_reloaded, "MorganRF")

if __name__ == "__main__":
    unittest.main()
