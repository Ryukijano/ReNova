import os
import sys
import json
import csv
import argparse

def main():
    parser = argparse.ArgumentParser(description="Mock Pipeline Runner for Stress Testing")
    parser.add_argument("disease", type=str, help="Disease name")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--mock", type=str, default="false")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    stress_mode = os.getenv("STRESS_MODE", "VALID")
    
    print(f"Mock Pipeline started in mode: {stress_mode}")

    # Create structures dir
    structures_dir = os.path.join(args.output_dir, "structures")
    os.makedirs(structures_dir, exist_ok=True)
    dummy_pdb_path = os.path.join(structures_dir, "P13569.pdb")
    with open(dummy_pdb_path, "w") as f:
        f.write("HEADER    DUMMY PDB FILE\nTER\nEND\n")

    # 1. Target Retriever Output (JSON)
    if stress_mode == "MISSING_JSON":
        # Do not write the target_retriever_output.json file at all
        pass
    elif stress_mode == "FEWER_JSON_ITEMS":
        # Write an empty list, but min_items is 1
        with open(os.path.join(args.output_dir, "target_retriever_output.json"), "w") as f:
            json.dump([], f, indent=2)
    else:
        # Valid JSON
        targets = [{
            "gene_symbol": "CFTR",
            "ensembl_id": "ENSG00000001626",
            "uniprot_id": "P13569",
            "association_score": 0.9,
            "structure_path": dummy_pdb_path
        }]
        with open(os.path.join(args.output_dir, "target_retriever_output.json"), "w") as f:
            json.dump(targets, f, indent=2)
    print("Target identification completed")

    # 2. Chemical Screen Output (CSV)
    chem_headers = ["gene_symbol", "uniprot_id", "compound_id", "smiles", "relation", "value", "units"]
    chem_rows = []
    if stress_mode == "WRONG_TYPE":
        # value is "abc" instead of float
        chem_rows.append({
            "gene_symbol": "CFTR", "uniprot_id": "P13569", "compound_id": "CHEMBL123",
            "smiles": "CCO", "relation": "=", "value": "abc", "units": "nM"
        })
    elif stress_mode == "INVALID_SMILES":
        # smiles has space/invalid characters
        chem_rows.append({
            "gene_symbol": "CFTR", "uniprot_id": "P13569", "compound_id": "CHEMBL123",
            "smiles": "C C?", "relation": "=", "value": "1.2", "units": "nM"
        })
    else:
        # Valid CSV
        chem_rows.append({
            "gene_symbol": "CFTR", "uniprot_id": "P13569", "compound_id": "CHEMBL123",
            "smiles": "CCO", "relation": "=", "value": "1.2", "units": "nM"
        })

    with open(os.path.join(args.output_dir, "chem_screen_output.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=chem_headers)
        writer.writeheader()
        writer.writerows(chem_rows)
    print("Chemical screening completed")

    # 3. ADMET Predict Output (CSV)
    admet_headers = ["gene_symbol", "compound_id", "smiles", "hcl_solubility", "caco2_permeability", "logp", "qed", "toxicity_score", "admet_score"]
    admet_rows = []
    
    if stress_mode == "MISSING_COL":
        # missing smiles column from admet_predict_output.csv
        admet_headers_temp = [h for h in admet_headers if h != "smiles"]
        admet_rows.append({
            "gene_symbol": "CFTR", "compound_id": "CHEMBL123",
            "hcl_solubility": "-1.5", "caco2_permeability": "2.0", "logp": "1.8",
            "qed": "0.8", "toxicity_score": "0.1", "admet_score": "0.7"
        })
        with open(os.path.join(args.output_dir, "admet_predict_output.csv"), "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=admet_headers_temp)
            writer.writeheader()
            writer.writerows(admet_rows)
    elif stress_mode == "OUT_OF_BOUNDS_QED":
        # QED is 1.5 (out of [0.0, 1.0])
        admet_rows.append({
            "gene_symbol": "CFTR", "compound_id": "CHEMBL123", "smiles": "CCO",
            "hcl_solubility": "-1.5", "caco2_permeability": "2.0", "logp": "1.8",
            "qed": "1.5", "toxicity_score": "0.1", "admet_score": "0.7"
        })
        with open(os.path.join(args.output_dir, "admet_predict_output.csv"), "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=admet_headers)
            writer.writeheader()
            writer.writerows(admet_rows)
    else:
        # Valid CSV
        admet_rows.append({
            "gene_symbol": "CFTR", "compound_id": "CHEMBL123", "smiles": "CCO",
            "hcl_solubility": "-1.5", "caco2_permeability": "2.0", "logp": "1.8",
            "qed": "0.85", "toxicity_score": "0.1", "admet_score": "0.75"
        })
        with open(os.path.join(args.output_dir, "admet_predict_output.csv"), "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=admet_headers)
            writer.writeheader()
            writer.writerows(admet_rows)
    print("ADMET prediction completed")

    # 4. Repurposing Candidate Report (CSV)
    rep_headers = ["compound_name", "compound_id", "smiles", "target_gene", "admet_score", "fda_approval_status", "clinical_trials_count", "adverse_events_count"]
    rep_rows = []
    # Make sure we have 5 rows as expected by exact_row_count: 5
    for i in range(5):
        rep_rows.append({
            "compound_name": f"Mock_CHEMBL{i}",
            "compound_id": f"CHEMBL{i}",
            "smiles": "CCO",
            "target_gene": "CFTR",
            "admet_score": "0.8",
            "fda_approval_status": "APPROVED",
            "clinical_trials_count": "2",
            "adverse_events_count": "5"
        })
    with open(os.path.join(args.output_dir, "repurposing_candidate_report.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rep_headers)
        writer.writeheader()
        writer.writerows(rep_rows)
    print("Clinical checks completed")
    print("Pipeline finished successfully")

if __name__ == "__main__":
    main()
