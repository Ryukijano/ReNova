import os
import re
import json
import csv
from typing import Dict, Any, List

class AssertionEngine:
    @staticmethod
    def validate_smiles(smiles: str) -> bool:
        """
        Performs a basic structural check on a SMILES string.
        A valid SMILES should not have spaces and should contain common organic atoms/characters.
        """
        if not smiles or not isinstance(smiles, str):
            return False
        if " " in smiles or "\t" in smiles or "\n" in smiles:
            return False
        # Basic character whitelist for SMILES
        allowed_pattern = re.compile(r'^[A-Za-z0-9#\(\)\+-\.=:;@\[\]\\\/$%]+$')
        return bool(allowed_pattern.match(smiles))

    @staticmethod
    def check_file_exists_and_not_empty(filepath: str) -> bool:
        return os.path.exists(filepath) and os.path.getsize(filepath) > 0

    @classmethod
    def validate_csv(cls, filepath: str, rules: Dict[str, Any]) -> List[str]:
        errors = []
        if not cls.check_file_exists_and_not_empty(filepath):
            return [f"File {filepath} does not exist or is empty."]

        required_columns = rules.get("required_columns", [])
        exact_row_count = rules.get("exact_row_count")
        min_row_count = rules.get("min_row_count")
        max_row_count = rules.get("max_row_count")
        column_validators = rules.get("column_validators", {})

        try:
            with open(filepath, mode="r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames if reader.fieldnames else []
                
                # Check required columns
                for col in required_columns:
                    if col not in headers:
                        errors.append(f"CSV {filepath} missing required column: '{col}'")

                rows = list(reader)
                row_count = len(rows)

                # Check row count limits
                if exact_row_count is not None and row_count != exact_row_count:
                    errors.append(f"CSV {filepath} has {row_count} rows, expected exactly {exact_row_count}.")
                if min_row_count is not None and row_count < min_row_count:
                    errors.append(f"CSV {filepath} has {row_count} rows, expected at least {min_row_count}.")
                if max_row_count is not None and row_count > max_row_count:
                    errors.append(f"CSV {filepath} has {row_count} rows, expected at most {max_row_count}.")

                # Validate each row
                for idx, row in enumerate(rows, start=1):
                    for col, val_rules in column_validators.items():
                        if col not in row:
                            continue  # Already caught by missing column error if required
                        
                        val = row[col]
                        col_type = val_rules.get("type")
                        if val is None or val == "":
                            # Check if column is required to have a value, otherwise skip
                            continue
                        
                        # Validate types and ranges
                        parsed_val = None
                        if col_type == "int":
                            try:
                                parsed_val = int(val)
                            except ValueError:
                                errors.append(f"Row {idx}: column '{col}' value '{val}' is not an integer.")
                        elif col_type == "float":
                            try:
                                parsed_val = float(val)
                            except ValueError:
                                errors.append(f"Row {idx}: column '{col}' value '{val}' is not a float.")
                        elif col_type == "smiles":
                            if not cls.validate_smiles(val):
                                errors.append(f"Row {idx}: column '{col}' value '{val}' is not a valid SMILES string.")
                        elif col_type == "string":
                            parsed_val = val
                            if not isinstance(val, str):
                                errors.append(f"Row {idx}: column '{col}' value is not a valid string.")

                        # Range checks for numeric values
                        if parsed_val is not None and (col_type in ["int", "float"]):
                            val_min = val_rules.get("min")
                            val_max = val_rules.get("max")
                            if val_min is not None and parsed_val < val_min:
                                errors.append(f"Row {idx}: column '{col}' value {parsed_val} < min limit {val_min}.")
                            if val_max is not None and parsed_val > val_max:
                                errors.append(f"Row {idx}: column '{col}' value {parsed_val} > max limit {val_max}.")

                        # Regex check
                        regex_pattern = val_rules.get("regex")
                        if regex_pattern and val:
                            if not re.match(regex_pattern, val):
                                errors.append(f"Row {idx}: column '{col}' value '{val}' does not match regex '{regex_pattern}'.")

                        # Allowed values check
                        allowed_vals = val_rules.get("allowed_values")
                        if allowed_vals and val not in allowed_vals:
                            errors.append(f"Row {idx}: column '{col}' value '{val}' not in allowed list {allowed_vals}.")

        except Exception as e:
            errors.append(f"Failed to parse CSV file {filepath}: {str(e)}")

        return errors

    @classmethod
    def validate_json(cls, filepath: str, rules: Dict[str, Any]) -> List[str]:
        errors = []
        if not cls.check_file_exists_and_not_empty(filepath):
            return [f"File {filepath} does not exist or is empty."]

        try:
            with open(filepath, mode="r", encoding="utf-8") as f:
                data = json.load(f)

            min_items = rules.get("min_items")
            max_items = rules.get("max_items")
            check_file_paths_exist = rules.get("check_file_paths_exist")

            if isinstance(data, list):
                item_count = len(data)
                if min_items is not None and item_count < min_items:
                    errors.append(f"JSON {filepath} has {item_count} items, expected at least {min_items}.")
                if max_items is not None and item_count > max_items:
                    errors.append(f"JSON {filepath} has {item_count} items, expected at most {max_items}.")

                # JSONPath check (simplistic implementation for [*].field)
                if check_file_paths_exist:
                    # e.g., "$[*].structure_path" or "[*].structure_path" or "$.list[*].structure_path"
                    match = re.search(r'\.(\w+)$', check_file_paths_exist)
                    if match:
                        field_name = match.group(1)
                        for idx, item in enumerate(data):
                            if isinstance(item, dict) and field_name in item:
                                path_val = item[field_name]
                                # Paths in output are usually relative to workspace root
                                if not os.path.exists(path_val):
                                    errors.append(f"JSON item {idx}: structure path '{path_val}' does not exist on disk.")
                                elif os.path.getsize(path_val) == 0:
                                    errors.append(f"JSON item {idx}: structure path '{path_val}' is empty.")
                    else:
                        errors.append(f"Unsupported path expression in check_file_paths_exist: {check_file_paths_exist}")
            else:
                # If it's a dict, we can validate basic properties
                if min_items is not None or max_items is not None:
                    errors.append(f"JSON {filepath} is an object, but item count limits were specified.")

        except json.JSONDecodeError as e:
            errors.append(f"Failed to parse JSON file {filepath}: {str(e)}")
        except Exception as e:
            errors.append(f"Error during JSON validation of {filepath}: {str(e)}")

        return errors

    @classmethod
    def validate_process_result(cls, stdout: str, stderr: str, exit_code: int, rules: Dict[str, Any]) -> List[str]:
        errors = []
        expected_exit_code = rules.get("expected_exit_code", 0)
        stdout_contains = rules.get("stdout_contains", [])
        stderr_excludes = rules.get("stderr_excludes", [])

        if exit_code != expected_exit_code:
            errors.append(f"Process exit code was {exit_code}, expected {expected_exit_code}.")

        for pattern in stdout_contains:
            if not re.search(pattern, stdout):
                errors.append(f"Stdout missing required pattern: '{pattern}'")

        for pattern in stderr_excludes:
            if re.search(pattern, stderr):
                errors.append(f"Stderr contains forbidden pattern: '{pattern}'")

        return errors
