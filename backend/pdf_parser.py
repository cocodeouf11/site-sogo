"""
PDF parser for delivery notes (bon de livraison) - SOGO TECH layout.

Layout of the delivery note:
Each product occupies 2 rows in the table (sometimes 3 if name wraps):
  Row A: [Product name..., quantity_int]
  Row B: [UGS :, reference, Étagère :, X |, Colonne :, Y |, Tiroir :, Z |, Bac :, W]

The "UGS :" row acts as the terminator for each product. Everything between
two UGS rows (excluding the previous product's UGS row) is the current
product's name-and-quantity rows.

We return normalized bboxes (0..1) covering the full product block
so the frontend can overlay clickable zones over the PDF.
"""
from __future__ import annotations
import re
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional


ORDER_NUMBER_RE = re.compile(r"(?:commande|order|n[°º]|bon)[^\d]{0,20}(\d{4,8})", re.IGNORECASE)


def _round(v: float, digits: int = 4) -> float:
    return round(float(v), digits)


def _rows_from_page(page) -> List[List[Dict[str, Any]]]:
    """Group all text spans of a page into rows by y-position."""
    page_dict = page.get_text("dict")
    spans: List[Dict[str, Any]] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                t = span.get("text", "").strip()
                if not t:
                    continue
                x0, y0, x1, y1 = span["bbox"]
                spans.append({"t": t, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    spans.sort(key=lambda s: (round(s["y0"], 0), s["x0"]))
    rows: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cy = None
    tol = 3.0
    for s in spans:
        if cy is None or abs(s["y0"] - cy) < tol:
            cur.append(s)
            cy = s["y0"] if cy is None else (cy + s["y0"]) / 2
        else:
            rows.append(cur)
            cur = [s]
            cy = s["y0"]
    if cur:
        rows.append(cur)
    return rows


def _parse_ugs_row(row: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Given a row list, if it looks like an UGS row, extract reference and location.
    Returns None if not an UGS row.
    """
    full_text = " ".join(s["t"] for s in row)
    if "UGS" not in full_text and "Étagère" not in full_text and "Etagère" not in full_text:
        return None

    result = {"reference": None, "etagere": None, "colonne": None, "tiroir": None, "bac": None}

    # Sort by x
    sorted_row = sorted(row, key=lambda s: s["x0"])
    texts = [s["t"] for s in sorted_row]

    # Reference: the token right after "UGS :"
    for i, t in enumerate(texts):
        if t.startswith("UGS"):
            if i + 1 < len(texts):
                nxt = texts[i + 1].strip(": ")
                if nxt and not nxt.startswith("Étag"):
                    result["reference"] = nxt
            break

    # Location fields - find the token right after each label.
    labels = [
        ("Étagère", "etagere"),
        ("Etagère", "etagere"),
        ("Colonne", "colonne"),
        ("Tiroir", "tiroir"),
        ("Bac", "bac"),
    ]
    for i, t in enumerate(texts):
        for label, key in labels:
            if t.startswith(label):
                if i + 1 < len(texts):
                    val = texts[i + 1].strip()
                    # Strip trailing " |"
                    val = val.replace("|", "").strip()
                    if val:
                        result[key] = val
                break

    if not any([result["reference"], result["etagere"], result["colonne"]]):
        return None
    return result


def parse_delivery_note(pdf_path: str) -> Dict[str, Any]:
    """
    Parse a delivery-note PDF (SOGO TECH format).
    Returns { order_number, pages, lines[] } with bbox normalized 0..1.
    """
    doc = fitz.open(pdf_path)
    pages_info: List[Dict[str, float]] = []
    all_lines: List[Dict[str, Any]] = []

    order_number: Optional[str] = None
    line_counter = 0

    # Buffer of accumulated rows for a product (before UGS row)
    for page_num, page in enumerate(doc, start=1):
        pw, ph = page.rect.width, page.rect.height
        pages_info.append({"width": pw, "height": ph})

        # Attempt to detect order number in top text on first page
        if order_number is None:
            top_txt = page.get_text("text")
            m = ORDER_NUMBER_RE.search(top_txt)
            if m:
                order_number = m.group(1)

        rows = _rows_from_page(page)
        if not rows:
            continue

        # Find header row (contains "Produits" and "Quantité") - if found we start
        # collecting after it. Otherwise we still scan the whole page in case it's
        # a continuation page.
        start_idx = 0
        for idx, r in enumerate(rows):
            joined = " ".join(s["t"] for s in r).lower()
            if "produits" in joined and ("quantit" in joined or "qte" in joined):
                start_idx = idx + 1
                break

        buffer: List[List[Dict[str, Any]]] = []
        for row in rows[start_idx:]:
            joined_row_text = " ".join(s["t"] for s in row)
            # Skip page-footer / totals
            if re.match(r"^(page \d|\d+/\d+\s*$|www\.|Tel\.|siret|tva)", joined_row_text, re.IGNORECASE):
                continue

            ugs = _parse_ugs_row(row)
            if ugs is not None:
                # Finalize product using buffer + this UGS row
                if not buffer:
                    continue

                # Extract quantity: last integer among rightmost span of buffer rows
                quantity = None
                # Prefer rightmost span of the FIRST buffer row that is an integer
                # (that's the "Quantité" column value).
                for br in buffer:
                    rightmost = max(br, key=lambda s: s["x1"])
                    if re.match(r"^\d{1,4}$", rightmost["t"]):
                        quantity = int(rightmost["t"])
                        break

                if quantity is None:
                    # Try any span that is a plain int
                    for br in buffer:
                        for s in br:
                            if re.match(r"^\d{1,4}$", s["t"]):
                                quantity = int(s["t"])
                                break
                        if quantity is not None:
                            break

                if quantity is None:
                    buffer = []
                    continue

                # Build product name: all spans in buffer that aren't the quantity int.
                name_parts: List[str] = []
                for br in buffer:
                    # sort by x0
                    for s in sorted(br, key=lambda x: x["x0"]):
                        if re.match(r"^\d{1,4}$", s["t"]):
                            # Skip the quantity column integer only when it's the rightmost span
                            rightmost = max(br, key=lambda x: x["x1"])
                            if s is rightmost:
                                continue
                        name_parts.append(s["t"])
                product_name = " ".join(name_parts).strip()

                # Compute bbox: union of all buffer rows + UGS row
                all_spans = [s for br in buffer for s in br] + row
                y0 = min(s["y0"] for s in all_spans)
                y1 = max(s["y1"] for s in all_spans)
                # Widen for easier tap
                bx0 = 0.02 * pw
                bx1 = 0.98 * pw
                by0 = max(0.0, y0 - 2.0)
                by1 = min(ph, y1 + 2.0)

                line_counter += 1
                all_lines.append({
                    "line_index": line_counter,
                    "page": page_num,
                    "product_name": product_name,
                    "reference": ugs["reference"],
                    "etagere": ugs["etagere"],
                    "colonne": ugs["colonne"],
                    "tiroir": ugs["tiroir"],
                    "bac": ugs["bac"],
                    "quantity": quantity,
                    "bbox": [
                        _round(bx0 / pw),
                        _round(by0 / ph),
                        _round((bx1 - bx0) / pw),
                        _round((by1 - by0) / ph),
                    ],
                })
                buffer = []
            else:
                # Skip pure noise
                if not row:
                    continue
                buffer.append(row)

    doc.close()

    return {
        "order_number": order_number,
        "pages": pages_info,
        "lines": all_lines,
    }
