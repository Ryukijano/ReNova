#!/usr/bin/env python3
import os
import sys
import csv
import argparse
import math
import warnings

# Determine CUDA device usage for stdout logging
try:
    import torch
    cuda_available = torch.cuda.is_available()
except ImportError:
    cuda_available = False

device_log = "cuda" if cuda_available else "cpu"
print(f"[ADMET] Using device: {device_log}")
sys.stdout.flush()

# Check DeepChem and DGL availability
DGL_AVAILABLE = False
dgl_device = "cpu"
deepchem_imported = False

try:
    import deepchem as dc
    deepchem_imported = True
except ImportError:
    pass

if deepchem_imported:
    try:
        import dgl
        from deepchem.models.torch_models import AttentiveFPModel
        DGL_AVAILABLE = True
        
        # Determine if DGL supports CUDA
        if cuda_available:
            try:
                g = dgl.graph(([], []))
                g = g.to(torch.device("cuda"))
                dgl_device = "cuda"
            except Exception:
                dgl_device = "cpu"
    except (ImportError, OSError, AttributeError) as e:
        print(f"[WARNING] DGL is missing or incompatible in this environment ({e}). Falling back to scikit-learn Random Forest model.", file=sys.stderr)
        DGL_AVAILABLE = False

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski
from rdkit.Chem.QED import qed

def calculate_descriptors(smiles):
    """Calculate standard molecular descriptors using RDKit."""
    try:
        mol = Chem.MolFromSmiles(smiles)
    except Exception:
        return None
    if mol is None:
        return None
        
    try:
        logp = float(Crippen.MolLogP(mol))
        qed_val = float(qed(mol))
        mw = float(Descriptors.MolWt(mol))
        hbd = int(Lipinski.NumHDonors(mol))
        hba = int(Lipinski.NumHAcceptors(mol))
        tpsa = float(Descriptors.TPSA(mol))
        rot_bonds = int(Lipinski.NumRotatableBonds(mol))
        
        aromatic_atoms = sum(1 for atom in mol.GetAtoms() if atom.GetIsAromatic())
        heavy_atoms = mol.GetNumHeavyAtoms()
        aromatic_prop = float(aromatic_atoms / heavy_atoms) if heavy_atoms > 0 else 0.0
        
        # Delaney ESOL equation
        hcl_solubility = 0.16 - 0.63 * logp - 0.0062 * mw + 0.066 * rot_bonds - 0.74 * aromatic_prop
        
        # Count Lipinski / TPSA violations
        violations = 0
        if mw > 500: violations += 1
        if logp > 5: violations += 1
        if hbd > 5: violations += 1
        if hba > 10: violations += 1
        if tpsa > 140: violations += 1
        
        return {
            "logp": logp,
            "qed": qed_val,
            "mw": mw,
            "hbd": hbd,
            "hba": hba,
            "tpsa": tpsa,
            "rot_bonds": rot_bonds,
            "aromatic_prop": aromatic_prop,
            "hcl_solubility": hcl_solubility,
            "violations": violations
        }
    except Exception as e:
        print(f"[WARNING] Descriptor calculation failed for smiles '{smiles}': {e}", file=sys.stderr)
        return None

def get_toxicity_score(preds, idx):
    """Extract toxicity_score (CT_TOX task class 1 probability) from model predictions."""
    if preds.ndim == 3:
        # ClinTox has 2 tasks: FDA_APPROVED (index 0) and CT_TOX (index 1)
        # DeepChem PyTorch models typically return (N, tasks, classes) -> shape[1] == 2
        # SklearnModel returns (tasks, N, classes) -> shape[0] == 2
        if preds.shape[0] == 2:
            return float(preds[1, idx, 1])
        else:
            return float(preds[idx, 1, 1])
    elif preds.ndim == 2:
        return float(preds[idx, 1])
    else:
        return 0.0

def get_bbbp_prob(preds, idx):
    """Extract BBBP penetration probability (class 1 probability) from model predictions."""
    if preds.ndim == 3:
        # BBBP has 1 task: p_np.
        # DeepChem PyTorch shape is (N, 1, classes) or SklearnModel is (1, N, classes)
        if preds.shape[0] == 1:
            return float(preds[0, idx, 1])
        else:
            return float(preds[idx, 0, 1])
    elif preds.ndim == 2:
        return float(preds[idx, 1])
    else:
        return 0.0

# ClinTox model lifecycle
def load_or_train_clintox(model_dir):
    os.makedirs(model_dir, exist_ok=True)
    if DGL_AVAILABLE:
        try:
            model = AttentiveFPModel(
                n_tasks=2,
                mode='classification',
                device=dgl_device,
                model_dir=model_dir
            )
            has_checkpoint = any(f.endswith('.pt') for f in os.listdir(model_dir)) if os.path.exists(model_dir) else False
            if has_checkpoint:
                try:
                    model.restore()
                    return model, "AttentiveFP"
                except Exception:
                    pass
            feat = dc.feat.MolGraphConvFeaturizer(use_edges=True)
            tasks, datasets, transformers = dc.molnet.load_clintox(featurizer=feat)
            train_dataset, val_dataset, test_dataset = datasets
            model.fit(train_dataset, nb_epoch=10)
            model.save_checkpoint()
            return model, "AttentiveFP"
        except Exception as e:
            print(f"[WARNING] Failed to load/train ClinTox AttentiveFPModel ({e}). Falling back to Random Forest.", file=sys.stderr)

    # Fallback RandomForest
    from sklearn.ensemble import RandomForestClassifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    model = dc.models.SklearnModel(clf, model_dir=model_dir)
    joblib_path = os.path.join(model_dir, "model.joblib")
    if os.path.exists(joblib_path):
        try:
            model.reload()
            return model, "MorganRF"
        except Exception:
            pass
    feat = dc.feat.CircularFingerprint(size=2048)
    tasks, datasets, transformers = dc.molnet.load_clintox(featurizer=feat)
    train_dataset, val_dataset, test_dataset = datasets
    model.fit(train_dataset)
    model.save()
    return model, "MorganRF"

# BBBP model lifecycle
def load_or_train_bbbp(model_dir):
    os.makedirs(model_dir, exist_ok=True)
    if DGL_AVAILABLE:
        try:
            model = AttentiveFPModel(
                n_tasks=1,
                mode='classification',
                device=dgl_device,
                model_dir=model_dir
            )
            has_checkpoint = any(f.endswith('.pt') for f in os.listdir(model_dir)) if os.path.exists(model_dir) else False
            if has_checkpoint:
                try:
                    model.restore()
                    return model, "AttentiveFP"
                except Exception:
                    pass
            feat = dc.feat.MolGraphConvFeaturizer(use_edges=True)
            tasks, datasets, transformers = dc.molnet.load_bbbp(featurizer=feat)
            train_dataset, val_dataset, test_dataset = datasets
            model.fit(train_dataset, nb_epoch=10)
            model.save_checkpoint()
            return model, "AttentiveFP"
        except Exception as e:
            print(f"[WARNING] Failed to load/train BBBP AttentiveFPModel ({e}). Falling back to Random Forest.", file=sys.stderr)

    # Fallback RandomForest
    from sklearn.ensemble import RandomForestClassifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    model = dc.models.SklearnModel(clf, model_dir=model_dir)
    joblib_path = os.path.join(model_dir, "model.joblib")
    if os.path.exists(joblib_path):
        try:
            model.reload()
            return model, "MorganRF"
        except Exception:
            pass
    feat = dc.feat.CircularFingerprint(size=2048)
    tasks, datasets, transformers = dc.molnet.load_bbbp(featurizer=feat)
    train_dataset, val_dataset, test_dataset = datasets
    model.fit(train_dataset)
    model.save()
    return model, "MorganRF"

def predict_row_mock(smiles):
    """Predict row parameters in mock mode without using DeepChem models."""
    desc = calculate_descriptors(smiles)
    if desc is None:
        return {
            "hcl_solubility": 0.0,
            "caco2_permeability": 0.0,
            "logp": 0.0,
            "qed": 0.0,
            "toxicity_score": 0.0,
            "admet_score": 0.0
        }
        
    # Heuristics for mock mode
    toxicity_score = 0.2 + 0.1 * desc["logp"] - 0.05 * desc["qed"]
    toxicity_score = max(0.0, min(1.0, toxicity_score))
    
    # BBBP probability heuristic (moderate LogP and low TPSA)
    bbbp_prob = 0.75 if (1.0 <= desc["logp"] <= 4.0 and desc["tpsa"] < 90) else 0.2
    caco2_permeability = round(1.0 + 2.0 * bbbp_prob, 4)
    
    solubility_score = max(0.0, min(1.0, (desc["hcl_solubility"] + 10.0) / 10.0))
    permeability_score = max(0.0, min(1.0, (caco2_permeability - 1.0) / 2.0))
    
    admet_score = (desc["qed"] * 0.3 + permeability_score * 0.2 + solubility_score * 0.2 + (1.0 - toxicity_score) * 0.3) * (1.0 - 0.15 * desc["violations"])
    admet_score = max(0.0, min(1.0, admet_score))
    
    return {
        "hcl_solubility": desc["hcl_solubility"],
        "caco2_permeability": caco2_permeability,
        "logp": desc["logp"],
        "qed": desc["qed"],
        "toxicity_score": toxicity_score,
        "admet_score": admet_score
    }

def predict_row_live(smiles, clintox_model, clintox_model_type, bbbp_model, bbbp_model_type):
    """Predict row parameters in live mode using DeepChem models and RDKit descriptors."""
    desc = calculate_descriptors(smiles)
    if desc is None:
        return {
            "hcl_solubility": 0.0,
            "caco2_permeability": 0.0,
            "logp": 0.0,
            "qed": 0.0,
            "toxicity_score": 0.0,
            "admet_score": 0.0
        }
        
    # ClinTox prediction
    try:
        if clintox_model_type == "AttentiveFP":
            feat = dc.feat.MolGraphConvFeaturizer(use_edges=True)
        else:
            feat = dc.feat.CircularFingerprint(size=2048)
            
        features = feat.featurize([smiles])
        if len(features) > 0 and features[0] is not None:
            dataset = dc.data.NumpyDataset(X=features)
            preds = clintox_model.predict(dataset)
            toxicity_score = get_toxicity_score(preds, 0)
        else:
            toxicity_score = 0.5
    except Exception as e:
        print(f"[WARNING] ClinTox prediction failed for '{smiles}': {e}", file=sys.stderr)
        toxicity_score = 0.5
        
    # BBBP prediction
    try:
        if bbbp_model_type == "AttentiveFP":
            feat = dc.feat.MolGraphConvFeaturizer(use_edges=True)
        else:
            feat = dc.feat.CircularFingerprint(size=2048)
            
        features = feat.featurize([smiles])
        if len(features) > 0 and features[0] is not None:
            dataset = dc.data.NumpyDataset(X=features)
            preds = bbbp_model.predict(dataset)
            bbbp_prob = get_bbbp_prob(preds, 0)
        else:
            bbbp_prob = 0.5
    except Exception as e:
        print(f"[WARNING] BBBP prediction failed for '{smiles}': {e}", file=sys.stderr)
        bbbp_prob = 0.5
        
    caco2_permeability = round(1.0 + 2.0 * bbbp_prob, 4)
    
    solubility_score = max(0.0, min(1.0, (desc["hcl_solubility"] + 10.0) / 10.0))
    permeability_score = max(0.0, min(1.0, (caco2_permeability - 1.0) / 2.0))
    
    admet_score = (desc["qed"] * 0.3 + permeability_score * 0.2 + solubility_score * 0.2 + (1.0 - toxicity_score) * 0.3) * (1.0 - 0.15 * desc["violations"])
    admet_score = max(0.0, min(1.0, admet_score))
    
    return {
        "hcl_solubility": desc["hcl_solubility"],
        "caco2_permeability": caco2_permeability,
        "logp": desc["logp"],
        "qed": desc["qed"],
        "toxicity_score": toxicity_score,
        "admet_score": admet_score
    }

def main():
    parser = argparse.ArgumentParser(description="GPU-accelerated ADMET predictions using DeepChem & RDKit")
    parser.add_argument("--input-csv", required=True, help="Path to the input compounds CSV file")
    parser.add_argument("--output-csv", required=True, help="Path to write the scored ADMET output CSV file")
    parser.add_argument("--mock", default="false", help="Run in mock mode using RDKit and empirical formulas (true/false)")
    
    args = parser.parse_args()
    
    is_mock = (args.mock.lower() == "true") or ("ADMET_MOCK_PORT" in os.environ)
    
    # Read input CSV
    if not os.path.exists(args.input_csv):
        print(f"Error: Input file {args.input_csv} does not exist.", file=sys.stderr)
        sys.exit(1)
        
    rows = []
    with open(args.input_csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
            
    # Handle empty input files gracefully
    if not rows:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
        with open(args.output_csv, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "gene_symbol", "compound_id", "smiles", "hcl_solubility", 
                "caco2_permeability", "logp", "qed", "toxicity_score", "admet_score"
            ])
        print("Input CSV contains no rows. Written headers to output CSV and exiting.")
        sys.exit(0)
        
    # Run predictions
    results = []
    if is_mock:
        print("[ADMET] Running in mock mode.")
        for r in rows:
            gene = r.get("gene_symbol", "UNKNOWN")
            comp_id = r.get("compound_id", "UNKNOWN")
            smiles = r.get("smiles", "")
            
            pred = predict_row_mock(smiles)
            results.append({
                "gene_symbol": gene,
                "compound_id": comp_id,
                "smiles": smiles,
                **pred
            })
    else:
        print("[ADMET] Running in live mode.")
        if not deepchem_imported:
            print("Error: Live mode requires deepchem to be installed.", file=sys.stderr)
            sys.exit(1)
            
        clintox_model, clintox_type = load_or_train_clintox("models/clintox")
        bbbp_model, bbbp_type = load_or_train_bbbp("models/bbbp")
        
        for r in rows:
            gene = r.get("gene_symbol", "UNKNOWN")
            comp_id = r.get("compound_id", "UNKNOWN")
            smiles = r.get("smiles", "")
            
            pred = predict_row_live(smiles, clintox_model, clintox_type, bbbp_model, bbbp_type)
            results.append({
                "gene_symbol": gene,
                "compound_id": comp_id,
                "smiles": smiles,
                **pred
            })
            
    # Write output CSV
    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, mode='w', encoding='utf-8', newline='') as f:
        fieldnames = ["gene_symbol", "compound_id", "smiles", "hcl_solubility", "caco2_permeability", "logp", "qed", "toxicity_score", "admet_score"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        
    print(f"ADMET prediction complete. Output written to: {args.output_csv}")
    sys.exit(0)

if __name__ == "__main__":
    main()
