#!/usr/bin/env python3
"""
pdf_to_json.py
--------------
Converts the Yaskawa GA700 parameter information from `params.pdf` into a JSON
file containing keys: 'param', 'name', and 'address' (plus 'adddress' alias).

Usage:
    python pdf_to_json.py
    python pdf_to_json.py --input params.pdf --output params.json
    python pdf_to_json.py --dict-mode   # Saves keyed by param code
"""

import os
import sys
import re
import json
import argparse
from typing import List, Dict, Any, Optional

try:
    from pypdf import PdfReader
except ImportError:
    print("Error: 'pypdf' package is required.")
    print("Please install it with: pip install pypdf")
    sys.exit(1)


# Regex pattern to match parameter codes like A1-01, d1-01, U1-01, H5-01, etc.
PARAM_CODE_REGEX = re.compile(r"^([A-Za-z][0-9]?-[0-9]{2})$")

# Regex pattern to match 4-digit hex addresses in parentheses, e.g., (0280), (0040)
HEX_ADDR_REGEX = re.compile(r"^\(([0-9A-Fa-f]{4})\)$")

# Common lead-in words that signify the start of the 'Description' column
DESC_STARTERS = [
    "Sets", "Selects", "Displays", "Configures", "Restricts", "The", "Shows",
    "Enables", "Disables", "Specifies", "Determines", "Increases", "Decreases",
    "Outputs", "Inputs", "Provides", "Calculates", "Automatically", "Used",
    "Uses", "Function", "Defines", "Toggles", "Adjusts", "Changes", "Monitors",
    "Stops", "Starts", "Controls", "Limits", "Protects", "Activates", "Deactivates",
    "Applies", "Cancels", "Switches", "Calibrates", "Resets", "When", "Enter",
    "Locks", "Allows", "Setsup", "Selectsthe", "Setsthe", "Displaysthe",
    "Thisparameter", "Configuresthe", "Restrictsthe", "Inputsthe", "Outputsthe"
]
DESC_REGEX = re.compile(r"(" + "|".join(DESC_STARTERS) + r")", re.IGNORECASE)


def split_camel_case(s: str) -> str:
    """Inserts spaces between CamelCase words and numbers."""
    # e.g., RunCommand -> Run Command, Selection1 -> Selection 1
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Za-z])([0-9]+)", r"\1 \2", s)
    return s


def clean_param_name(raw_lines: List[str]) -> str:
    """Cleans up and extracts the parameter name from candidate lines."""
    words = []
    for line in raw_lines:
        line = line.strip()
        if not line or line == "RUN":
            continue

        # Check if description starter appears in this line
        m = DESC_REGEX.search(line)
        if m:
            before = line[:m.start()].strip()
            if before:
                words.append(before)
            break
        else:
            words.append(line)

        if len(words) >= 3:
            break

    combined = " ".join(words)
    combined = split_camel_case(combined)
    # Normalize multiple whitespace characters
    cleaned = re.sub(r"\s+", " ", combined).strip()
    return cleaned


def extract_parameters_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Reads params.pdf and extracts all parameters into a list of dicts."""
    if not os.path.isfile(pdf_path):
        print(f"Error: PDF file '{pdf_path}' not found.")
        sys.exit(1)

    print("=" * 66)
    print("   YASKAWA GA700 PDF TO JSON PARAMETER CONVERTER")
    print("=" * 66)
    print(f"Input PDF  : {pdf_path}")
    print(f"File Size  : {os.path.getsize(pdf_path) / (1024 * 1024):.2f} MB")
    print("Reading and parsing pages...")

    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    parameters = []
    seen_params = set()

    for page_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if not text:
            continue

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        i = 0
        n = len(lines)

        while i < n:
            m_code = PARAM_CODE_REGEX.match(lines[i])
            if m_code:
                param_code = m_code.group(1)
                j = i + 1
                addr_hex = None

                # Check if next line contains (XXXX) address
                if j < n:
                    m_hex = HEX_ADDR_REGEX.match(lines[j])
                    if m_hex:
                        addr_hex = m_hex.group(1).upper()
                        j += 1

                if addr_hex:
                    # Collect name candidates
                    name_candidates = []
                    while j < n and not PARAM_CODE_REGEX.match(lines[j]) and len(name_candidates) < 4:
                        if lines[j] != "RUN":
                            name_candidates.append(lines[j])
                        j += 1

                    name = clean_param_name(name_candidates)
                    if not name:
                        name = f"Parameter {param_code}"

                    # Unique entry key check
                    entry_key = (param_code, addr_hex)
                    if entry_key not in seen_params:
                        seen_params.add(entry_key)
                        parameters.append({
                            "param": param_code,
                            "name": name,
                            "address": f"0x{addr_hex}",
                            "adddress": f"0x{addr_hex}",  # Alias for exact spelling in request
                            "hex": addr_hex,
                            "dec": int(addr_hex, 16),
                            "page": page_idx,
                        })

                    i = j - 1
            i += 1

    return parameters


def main():
    parser = argparse.ArgumentParser(
        description="Convert parameters from params.pdf to a structured JSON file."
    )
    parser.add_argument(
        "-i", "--input",
        default="params.pdf",
        help="Input PDF file path (default: params.pdf)",
    )
    parser.add_argument(
        "-o", "--output",
        default="params.json",
        help="Output JSON file path (default: params.json)",
    )
    parser.add_argument(
        "--dict-mode",
        action="store_true",
        help="Format output JSON as a dictionary keyed by parameter code (e.g. {'d1-01': {...}})",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Output as flat list instead of nested Chapter 10 structure",
    )

    args = parser.parse_args()

    # Fallback to local params.pdf if default not found directly
    input_file = args.input
    if not os.path.isfile(input_file):
        alt_input = os.path.join(os.path.dirname(__file__), "params.pdf")
        if os.path.isfile(alt_input):
            input_file = alt_input

    params_list = extract_parameters_from_pdf(input_file)
    print(f"Extracted {len(params_list)} parameters successfully!")

    # Check if nested schema exists
    nested_schema_path = os.path.join(os.path.dirname(__file__), "nested_params.json")
    if not args.flat and not args.dict_mode and os.path.isfile(nested_schema_path):
        import copy
        with open(nested_schema_path, "r", encoding="utf-8") as f_schema:
            nested_schema = json.load(f_schema)
        
        by_prefix = {}
        for p in params_list:
            pfx = p["param"].split("-")[0]
            by_prefix.setdefault(pfx, []).append(p)
        
        output_data = copy.deepcopy(nested_schema)
        for sec_id, sec_data in output_data.items():
            groups = sec_data.get("parameters", {})
            for grp_id, grp_info in groups.items():
                items = by_prefix.get(grp_id, [])
                grp_info["count"] = len(items)
                grp_info["parameters"] = items
    elif args.dict_mode:
        output_data = {item["param"]: item for item in params_list}
    else:
        output_data = params_list

    print(f"Writing JSON output to '{args.output}'...")
    with open(args.output, "w", encoding="utf-8") as f_out:
        json.dump(output_data, f_out, indent=2, ensure_ascii=False)

    out_size_kb = os.path.getsize(args.output) / 1024
    print(f"Successfully saved {args.output} ({out_size_kb:.1f} KB)")
    print("-" * 66)
    print("Verification of Requested Key Parameters:")

    # Highlight key parameters
    test_keys = ["d1-01", "U1-01", "U1-02", "U1-03", "b1-01", "b1-02", "H5-01", "H5-02"]
    for p in params_list:
        if p["param"] in test_keys:
            print(f"  * {p['param']:7} -> Name: {p['name']:32} | Address: {p['address']}")

    print("=" * 66)


if __name__ == "__main__":
    main()
