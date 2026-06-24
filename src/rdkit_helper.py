#!/usr/bin/env python3
import sys
import json
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski

def calculate_ro5_properties(smiles):
    """
    Calculates molecular properties for Lipinski Rule of Five (RO5) and TPSA using RDKit.
    Returns a dict with:
      - mw (float)
      - logp (float)
      - hbd (int)
      - hba (int)
      - tpsa (float)
      - violations (int)
      - ro5_pass (bool)
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
    except Exception:
        return None
    if mol is None:
        return None
        
    try:
        mw = float(Descriptors.MolWt(mol))
        logp = float(Crippen.MolLogP(mol))
        hbd = int(Lipinski.NumHDonors(mol))
        hba = int(Lipinski.NumHAcceptors(mol))
        tpsa = float(Descriptors.TPSA(mol))
        
        # Count violations (including TPSA > 140)
        violations = 0
        if mw > 500:
            violations += 1
        if logp > 5:
            violations += 1
        if hbd > 5:
            violations += 1
        if hba > 10:
            violations += 1
        if tpsa > 140:
            violations += 1
            
        ro5_pass = (violations <= 1)
        
        return {
            "mw": mw,
            "logp": logp,
            "hbd": hbd,
            "hba": hba,
            "tpsa": tpsa,
            "violations": violations,
            "ro5_pass": ro5_pass
        }
    except Exception as e:
        return None

def main():
    # Read input JSON from stdin
    try:
        input_data = json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"error": f"Failed to parse stdin JSON: {e}"}))
        sys.exit(1)
        
    results = {}
    for smiles in input_data:
        props = calculate_ro5_properties(smiles)
        if props:
            results[smiles] = props
            
    # Output results JSON to stdout
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
