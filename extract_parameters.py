#!/usr/bin/env python3
"""
extract_parameters.py
---------------------
Extracts the Yaskawa GA700 VFD Parameter Section from the technical manual PDF
(Chapter 10: Parameter List, Pages 393 to 512).

Usage:
    python extract_parameters.py
    python extract_parameters.py --start 393 --end 512
    python extract_parameters.py --start 400 --end 512 --output parameters.pdf
    python extract_parameters.py --input manual.pdf --start 393 --end 512 --dump-text
"""

import os
import sys
import argparse
from typing import Optional

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("Error: 'pypdf' package is required.")
    print("Please install it with: pip install pypdf")
    sys.exit(1)


def find_default_pdf() -> Optional[str]:
    """Find manual.pdf in the current directory or nearby directories."""
    candidates = [
        "manual.pdf",
        os.path.join(os.path.dirname(__file__), "manual.pdf"),
        os.path.join(os.getcwd(), "manual.pdf"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


def extract_parameter_pages(
    input_pdf: str,
    output_pdf: str,
    start_page: int = 393,
    end_page: int = 512,
    dump_text: bool = False,
):
    """
    Extracts pages [start_page, end_page] (1-based, inclusive) from input_pdf
    and writes them to output_pdf. Also transfers relevant bookmarks/outline.
    """
    if not os.path.isfile(input_pdf):
        print(f"Error: Input PDF not found: {input_pdf}")
        sys.exit(1)

    print("=" * 66)
    print("   YASKAWA GA700 PDF PARAMETER SECTION EXTRACTOR")
    print("=" * 66)
    print(f"Source PDF   : {input_pdf}")
    print(f"File Size    : {os.path.getsize(input_pdf) / (1024 * 1024):.2f} MB")
    print(f"Page Range   : Page {start_page} to Page {end_page} (1-based inclusive)")
    print(f"Output PDF   : {output_pdf}")
    print("-" * 66)

    print("Opening PDF and reading structure...")
    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    print(f"Total pages in document: {total_pages}")

    # Validate range
    if start_page < 1:
        start_page = 1
    if end_page > total_pages:
        end_page = total_pages
    if start_page > end_page:
        print(f"Error: Start page ({start_page}) cannot be greater than end page ({end_page}).")
        sys.exit(1)

    # 0-indexed range
    start_idx = start_page - 1
    end_idx = end_page - 1
    num_pages_to_extract = end_idx - start_idx + 1

    writer = PdfWriter()

    print(f"Extracting {num_pages_to_extract} pages (indices {start_idx} to {end_idx})...")
    for i in range(start_idx, end_idx + 1):
        writer.add_page(reader.pages[i])

    # Transfer outline / bookmarks if available within the extracted range
    try:
        def copy_bookmarks(outline_items, parent=None):
            for item in outline_items:
                if isinstance(item, list):
                    copy_bookmarks(item, parent)
                else:
                    try:
                        orig_page = reader.get_destination_page_number(item)
                        if start_idx <= orig_page <= end_idx:
                            new_page_idx = orig_page - start_idx
                            title = getattr(item, "title", str(item))
                            writer.add_outline_item(title, new_page_idx, parent=parent)
                    except Exception:
                        pass

        if reader.outline:
            print("Transferring table of contents / bookmarks for extracted section...")
            copy_bookmarks(reader.outline)
    except Exception as e:
        print(f"Note: Could not copy outline bookmarks: {e}")

    # Write output PDF
    print(f"Writing extracted pages to '{output_pdf}'...")
    with open(output_pdf, "wb") as f_out:
        writer.write(f_out)

    out_size_mb = os.path.getsize(output_pdf) / (1024 * 1024)
    print(f"Extraction complete! Saved {num_pages_to_extract} pages ({out_size_mb:.2f} MB)")

    # Optional: Dump plain text for parameter search
    if dump_text:
        text_filename = os.path.splitext(output_pdf)[0] + ".txt"
        print(f"Extracting searchable text to '{text_filename}'...")
        extracted_text = []
        for idx, page in enumerate(writer.pages, start=start_page):
            text = page.extract_text()
            extracted_text.append(f"--- PAGE {idx} ---\n{text}\n")
        with open(text_filename, "w", encoding="utf-8") as f_txt:
            f_txt.write("\n".join(extracted_text))
        print(f"Text dump saved: {text_filename}")

    print("-" * 66)
    print("Summary of Key Parameter Sections Extracted:")
    print("  * Page 393 : Chapter 10 'Parameter List' Start")
    print("  * Page 400 : A - Initialization Parameters")
    print("  * Page 402 : b - Application (b1-01 Frequency Ref, b1-02 Run Source)")
    print("  * Page 413 : C - Tuning (Accel/Decel, S-curves)")
    print("  * Page 419 : d - Reference Settings (d1-01 Freq Ref 1 @ Reg 0x0280)")
    print("  * Page 425 : E - Motor Parameters")
    print("  * Page 446 : H - Terminal Functions (H5 Modbus Comms @ Reg H5-01..H5-07)")
    print("  * Page 468 : L - Protection Functions")
    print("  * Page 498 : U - Monitors (U1-01 Freq Ref @ Reg 0x0040, U1-03 Current)")
    print("  * Page 512 : U8 - DriveWorksEZ Monitors")
    print("=" * 66)


def main():
    parser = argparse.ArgumentParser(
        description="Extract the Yaskawa GA700 parameter section (Pages 393 to 512) from manual.pdf."
    )
    default_input = find_default_pdf() or "manual.pdf"
    parser.add_argument(
        "-i", "--input",
        default=default_input,
        help=f"Path to input technical manual PDF (default: {default_input})",
    )
    parser.add_argument(
        "-s", "--start",
        type=int,
        default=393,
        help="Starting page number (1-based, default: 393 for Chapter 10 Parameter List)",
    )
    parser.add_argument(
        "-e", "--end",
        type=int,
        default=512,
        help="Ending page number (1-based, default: 512 for U8 Monitors)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output PDF path (default: ga700_parameter_list_p<start>_to_p<end>.pdf)",
    )
    parser.add_argument(
        "-t", "--dump-text",
        action="store_true",
        help="Also export a searchable .txt file of all parameter pages",
    )

    args = parser.parse_args()

    if not args.output:
        args.output = f"ga700_parameter_list_p{args.start}_to_p{args.end}.pdf"

    extract_parameter_pages(
        input_pdf=args.input,
        output_pdf=args.output,
        start_page=args.start,
        end_page=args.end,
        dump_text=args.dump_text,
    )


if __name__ == "__main__":
    main()
