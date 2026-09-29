#!/usr/bin/env python3
"""
extract_params.py
-----------------
Extracts the Yaskawa GA700 parameter information (including the valid setting range)
from `params.pdf` and saves a structured JSON file `params.json` with keys:
'param', 'name', 'address', 'adddress', 'hex', 'dec', 'page', and 'range'.

Usage:
    python extract_params.py
    python extract_params.py --input params.pdf --output params.json
"""

import os
import sys
import re
import json
import copy
import argparse
from typing import List, Dict, Any

try:
    from pypdf import PdfReader
except ImportError:
    print("Error: 'pypdf' package is required.")
    print("Please install it with: pip install pypdf")
    sys.exit(1)


PARAM_CODE_REGEX = re.compile(r"^([A-Za-z][0-9]?-[0-9]{2})$")
HEX_ADDR_REGEX = re.compile(r"^\(([0-9A-Fa-f]{4})\)$")

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
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Za-z])([0-9]+)", r"\1 \2", s)
    return s


def clean_param_name(raw_lines: List[str]) -> str:
    words = []
    for line in raw_lines:
        line = line.strip()
        if not line or line == "RUN":
            continue
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
    return re.sub(r"\s+", " ", combined).strip()


def clean_range_string(s: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([0-9a-zA-Z\.\-]+)to([0-9a-zA-Z\.\-]+)", r"\1 to \2", s)
    s = re.sub(r"([0-9])([A-Za-z]+)", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_parameters_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(pdf_path):
        print(f"Error: PDF file '{pdf_path}' not found.")
        sys.exit(1)

    print("=" * 66)
    print("   YASKAWA GA700 PDF PARAMETER & RANGE EXTRACTOR")
    print("=" * 66)
    print(f"Input PDF  : {pdf_path}")
    print(f"File Size  : {os.path.getsize(pdf_path) / (1024 * 1024):.2f} MB")
    print("Extracting parameters and valid ranges from pages...")

    reader = PdfReader(pdf_path)
    parameters = []
    seen = set()

    for page_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if not text:
            continue
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        n = len(lines)

        param_positions = []
        for idx in range(n):
            m_code = PARAM_CODE_REGEX.match(lines[idx])
            if m_code and idx + 1 < n:
                m_hex = HEX_ADDR_REGEX.match(lines[idx + 1])
                if m_hex:
                    param_positions.append((idx, m_code.group(1), m_hex.group(1).upper()))

        if not param_positions:
            continue

        # Range should ONLY be extracted if the table heading explicitly contains 'range'
        # and is NOT 'MFAO Signal Level'
        header_lines = lines[:param_positions[0][0]]
        header_text = " ".join(header_lines).lower()
        has_range_column = ("range" in header_text) and ("mfao" not in header_text)

        for k in range(len(param_positions)):
            start_idx, pcode, phex = param_positions[k]
            end_idx = param_positions[k + 1][0] if k + 1 < len(param_positions) else n

            # Collect name candidates
            j = start_idx + 2
            name_candidates = []
            while j < min(end_idx, start_idx + 8) and not lines[j].startswith("("):
                if lines[j] != "RUN":
                    name_candidates.append(lines[j])
                j += 1
            name = clean_param_name(name_candidates)
            if not name:
                name = f"Parameter {pcode}"

            # Collect range from content lines ONLY if table header contains Range
            matched_range = ""
            if has_range_column:
                content_lines = lines[start_idx + 2 : end_idx]
                combined = []
                buf = ""
                in_paren = False
                for line in content_lines:
                    if "(" in line and ")" not in line:
                        buf = line
                        in_paren = True
                    elif in_paren:
                        buf += " " + line
                        if ")" in line:
                            combined.append(buf)
                            buf = ""
                            in_paren = False
                    else:
                        combined.append(line)
                if buf:
                    combined.append(buf)

                for line in reversed(combined):
                    parens = re.findall(r"\(([^)]+)\)", line)
                    for p in parens:
                        p = p.strip()
                        if re.match(r"^[0-9A-Fa-f]{4}$", p):
                            continue
                        if any(c.isdigit() for c in p) or "to" in p.lower() or "determined" in p.lower():
                            matched_range = clean_range_string(p)
                            break
                    if matched_range:
                        break

            entry_key = (pcode, phex)
            if entry_key not in seen:
                seen.add(entry_key)
                parameters.append({
                    "param": pcode,
                    "name": name,
                    "address": f"0x{phex}",
                    "adddress": f"0x{phex}",
                    "hex": phex,
                    "dec": int(phex, 16),
                    "page": page_idx,
                    "range": matched_range,
                })

    return parameters


def main():
    parser = argparse.ArgumentParser(
        description="Extract parameters and valid ranges from params.pdf to params.json."
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
        "--flat",
        action="store_true",
        help="Output flat list instead of nested Chapter 10 structure",
    )

    args = parser.parse_args()

    input_file = args.input
    if not os.path.isfile(input_file):
        alt_input = os.path.join(os.path.dirname(__file__), "params.pdf")
        if os.path.isfile(alt_input):
            input_file = alt_input

    params_list = extract_parameters_from_pdf(input_file)
    print(f"Extracted {len(params_list)} parameters successfully!")
    with_range_count = sum(1 for p in params_list if p.get("range"))
    print(f"Extracted range for {with_range_count} / {len(params_list)} parameters ({with_range_count / len(params_list) * 100:.1f}%)")

    nested_schema_path = os.path.join(os.path.dirname(__file__), "nested_params.json")
    if not args.flat and os.path.isfile(nested_schema_path):
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
    else:
        output_data = params_list

    print(f"Writing updated JSON output with 'range' key to '{args.output}'...")
    with open(args.output, "w", encoding="utf-8") as f_out:
        json.dump(output_data, f_out, indent=2, ensure_ascii=False)

    out_size_kb = os.path.getsize(args.output) / 1024
    print(f"Successfully saved {args.output} ({out_size_kb:.1f} KB)")
    print("-" * 66)
    print("Verification of Requested Key Parameters with Range:")
    test_keys = ["A1-00", "A1-01", "A1-02", "b1-01", "b1-02", "C1-01", "d1-01", "H5-01"]
    for p in params_list:
        if p["param"] in test_keys:
            print(f"  * {p['param']:7} -> Address: {p['address']:6} | Range: {p.get('range', ''):18} | Name: {p['name']}")
    print("=" * 66)


if __name__ == "__main__":
    main()
