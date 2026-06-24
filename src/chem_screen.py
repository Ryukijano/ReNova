#!/usr/bin/env python3
import os
import sys
import argparse
import json
import csv
import requests

def log_message(msg):
    print(f"[chem_screen] {msg}", file=sys.stderr)

def is_valid_smiles(smiles):
    if not smiles or not isinstance(smiles, str):
        return False
    if len(smiles.strip()) == 0:
        return False
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        return mol is not None
    except ImportError:
        return True
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description="Candidate Compound Screening from ChEMBL")
    parser.add_argument("--target-json", required=True, help="Input targets JSON file")
    parser.add_argument("--output-csv", required=True, help="Output CSV file")
    parser.add_argument("--mock", nargs='?', const='true', default='false', help="Run in mock mode")
    
    args = parser.parse_args()
    
    # Check if mock mode is enabled via argument or environment variable
    is_mock = (args.mock.lower() == "true") or ("ADMET_MOCK_PORT" in os.environ)
    
    log_message(f"Starting chemical screening. Mock mode: {is_mock}")
    
    # Read targets JSON
    if not os.path.exists(args.target_json):
        log_message(f"Error: Target JSON file '{args.target_json}' not found.")
        sys.exit(1)
        
    with open(args.target_json, "r", encoding="utf-8") as f:
        try:
            targets = json.load(f)
        except Exception as e:
            log_message(f"Error parsing Target JSON: {e}")
            sys.exit(1)
            
    if not isinstance(targets, list):
        log_message("Error: Target JSON must be a list of target objects.")
        sys.exit(1)
        
    compounds = []
    
    if is_mock:
        # Mock mode
        mock_port = os.getenv("ADMET_MOCK_PORT", "8085")
        chembl_api_url = os.getenv("CHEMBL_API_URL", f"http://localhost:{mock_port}/chembl/api/data")
        
        log_message(f"Querying mock ChEMBL API status at {chembl_api_url}/status")
        try:
            status_res = requests.get(f"{chembl_api_url.rstrip('/')}/status", timeout=15)
            if status_res.status_code != 200:
                log_message(f"Warning: Mock ChEMBL status returned code {status_res.status_code}")
        except Exception as e:
            log_message(f"Warning: Failed to connect to mock ChEMBL status: {e}")
            
        log_message(f"Querying mock ChEMBL API activities at {chembl_api_url}/activity")
        try:
            activity_res = requests.get(f"{chembl_api_url.rstrip('/')}/activity", timeout=15)
            if activity_res.status_code != 200:
                log_message(f"Error: Mock ChEMBL activity returned code {activity_res.status_code}")
                sys.exit(1)
            activity_data = activity_res.json()
        except Exception as e:
            log_message(f"Error connecting to mock ChEMBL activity: {e}")
            sys.exit(1)
            
        raw_activities = activity_data.get("activities", [])
        log_message(f"Retrieved {len(raw_activities)} activities from mock ChEMBL API.")
        
        for target in targets:
            gene_symbol = target.get("gene_symbol", "UNKNOWN")
            uniprot_id = target.get("uniprot_id", "UNKNOWN")
            for act in raw_activities:
                smiles = act.get("canonical_smiles")
                if not is_valid_smiles(smiles):
                    continue
                    
                val_str = act.get("standard_value") or act.get("value")
                try:
                    val_float = float(val_str) if val_str is not None else 0.0
                except (ValueError, TypeError):
                    val_float = 0.0
                    
                compounds.append({
                    "gene_symbol": gene_symbol,
                    "uniprot_id": uniprot_id,
                    "compound_id": act.get("molecule_chembl_id"),
                    "smiles": smiles,
                    "relation": act.get("standard_relation") or act.get("relation") or "=",
                    "value": val_float,
                    "units": act.get("standard_units") or act.get("units") or "nM"
                })
    else:
        # Real mode
        try:
            from chembl_webresource_client.new_client import new_client
        except ImportError:
            log_message("Error: chembl_webresource_client is not installed in the current environment.")
            sys.exit(1)
            
        target_chembl_id_to_targets = {}
        for target in targets:
            uniprot_id = target.get("uniprot_id")
            if not uniprot_id or uniprot_id == "UNKNOWN":
                log_message(f"Skipping target {target.get('gene_symbol')} - no valid UniProt ID.")
                continue
                
            log_message(f"Resolving ChEMBL Target IDs for UniProt ID: {uniprot_id}...")
            try:
                res = new_client.target.filter(target_components__accession=uniprot_id)
                tids = [r.get("target_chembl_id") for r in res if r.get("target_chembl_id")]
                if not tids:
                    log_message(f"Warning: No ChEMBL Target ID resolved for {uniprot_id}.")
                for tid in tids:
                    target_chembl_id_to_targets.setdefault(tid, []).append(target)
            except Exception as e:
                log_message(f"Error querying ChEMBL target for {uniprot_id}: {e}")
                
        all_target_chembl_ids = list(target_chembl_id_to_targets.keys())
        if not all_target_chembl_ids:
            log_message("No resolved ChEMBL target IDs found. Exiting with empty compounds.")
        else:
            log_message(f"Querying activities for ChEMBL Targets: {all_target_chembl_ids}...")
            try:
                activity_query = new_client.activity.filter(
                    target_chembl_id__in=all_target_chembl_ids,
                    assay_type='B',
                    standard_type__in=['IC50', 'Ki']
                )
                raw_activities = list(activity_query)
                log_message(f"Retrieved {len(raw_activities)} raw activities.")
            except Exception as e:
                log_message(f"Error retrieving ChEMBL activities: {e}")
                raw_activities = []
                
            # Collect unique molecule IDs to query their properties in batch
            molecule_ids = set()
            for act in raw_activities:
                mol_id = act.get("molecule_chembl_id")
                if mol_id:
                    molecule_ids.add(mol_id)
                    
            log_message(f"Querying molecule properties in batch for {len(molecule_ids)} unique compounds...")
            molecules_info = {}
            # Chunk query to avoid large request payload or URL length limits
            molecule_ids_list = list(molecule_ids)
            for i in range(0, len(molecule_ids_list), 100):
                chunk = molecule_ids_list[i:i+100]
                try:
                    mols = new_client.molecule.filter(molecule_chembl_id__in=chunk)
                    for m in mols:
                        m_id = m.get("molecule_chembl_id")
                        if m_id:
                            molecules_info[m_id] = m
                except Exception as e:
                    log_message(f"Error querying molecule chunk starting at {i}: {e}")
                    
            # Process activities and filter
            for act in raw_activities:
                mol_id = act.get("molecule_chembl_id")
                smiles = act.get("canonical_smiles")
                
                # Filter SMILES validity
                if not is_valid_smiles(smiles):
                    continue
                    
                # Get molecule info
                mol_info = molecules_info.get(mol_id, {})
                max_phase = mol_info.get("max_phase")
                
                # Explicitly fetch requested properties (even if not in CSV schema)
                full_mwt = mol_info.get("molecule_properties", {}).get("full_mwt")
                alogp = mol_info.get("molecule_properties", {}).get("alogp")
                
                # Filter max_phase
                if max_phase is None:
                    continue
                try:
                    max_phase_num = float(max_phase)
                except (ValueError, TypeError):
                    continue
                if max_phase_num < 0:
                    continue
                    
                # Extract value
                val_str = act.get("standard_value")
                if val_str is None:
                    continue
                try:
                    val_float = float(val_str)
                except (ValueError, TypeError):
                    continue
                    
                tid = act.get("target_chembl_id")
                matching_targets = target_chembl_id_to_targets.get(tid, [])
                for target in matching_targets:
                    compounds.append({
                        "gene_symbol": target.get("gene_symbol"),
                        "uniprot_id": target.get("uniprot_id"),
                        "compound_id": mol_id,
                        "smiles": smiles,
                        "relation": act.get("standard_relation") or act.get("relation") or "=",
                        "value": val_float,
                        "units": act.get("standard_units") or act.get("units") or "nM"
                    })
                    
    # Write output to CSV
    log_message(f"Writing {len(compounds)} compounds to {args.output_csv}...")
    output_abs_path = os.path.abspath(args.output_csv)
    os.makedirs(os.path.dirname(output_abs_path), exist_ok=True)
    
    with open(output_abs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["gene_symbol", "uniprot_id", "compound_id", "smiles", "relation", "value", "units"])
        writer.writeheader()
        writer.writerows(compounds)
        
    log_message("Screening completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
