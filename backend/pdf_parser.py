"""
PDF parser for delivery notes (bon de livraison).

Two-row product layout used by SOGO TECH (and similar):
  Row A: [Product name..., quantity_int]  (product name may wrap on multiple rows)
  Row B: [UGS :, reference, Étagère :, X |, Colonne :, Y |, Tiroir :, Z |, Bac :, W]
         (sometimes without UGS - just starts with Étagère :)
         (sometimes with empty values : `Étagère : |`)

Robust detection strategy:
1. Extract text spans with positional info.
2. Group spans into rows by y-position (small tolerance).
3. For each row, decide if it's a "location row" by looking for the presence
   of at least two of the location labels (Étagère, Colonne, Tiroir, Bac)
   OR the presence of "UGS :" and any location label.
4. Everything between two location rows is buffer content (name + quantity).
5. The quantity is the LAST integer of the last buffer row (before location).

Returns bbox in normalized [0..1] coordinates.
"""
from __future__ import annotations
import re
import unicodedata
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional


ORDER_NUMBER_RE = re.compile(r"(?:commande|order|n[°º]|bon)[^\d]{0,20}(\d{4,8})", re.IGNORECASE)


def _round(v: float, digits: int = 4) -> float:
    return round(float(v), digits)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


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


LOCATION_LABELS = ("etagere", "colonne", "tiroir", "bac")


def _is_location_row(row: List[Dict[str, Any]]) -> bool:
    """A location row must contain at least 2 different location labels
    (Étagère/Colonne/Tiroir/Bac) OR 'UGS :' + at least 1 location label.
    """
    lowered = [_strip_accents(s["t"].lower()) for s in row]
    joined = " ".join(lowered)
    has_ugs = "ugs" in joined
    label_hits = sum(1 for lab in LOCATION_LABELS if lab in joined)
    return label_hits >= 2 or (has_ugs and label_hits >= 1)


def _parse_location_row(row: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract reference (if UGS present) and etagere/colonne/tiroir/bac values."""
    result = {"reference": None, "etagere": None, "colonne": None, "tiroir": None, "bac": None}
    sorted_row = sorted(row, key=lambda s: s["x0"])
    texts = [s["t"] for s in sorted_row]
    lowered = [_strip_accents(t.lower()) for t in texts]

    # Reference right after "UGS :"
    for i, t in enumerate(lowered):
        if t.startswith("ugs"):
            if i + 1 < len(texts):
                nxt = texts[i + 1].strip(": ").strip()
                if nxt and not _strip_accents(nxt.lower()).startswith("etag"):
                    result["reference"] = nxt
            break

    # Location fields
    label_map = [
        ("etagere", "etagere"),
        ("colonne", "colonne"),
        ("tiroir", "tiroir"),
        ("bac", "bac"),
    ]
    for i, t in enumerate(lowered):
        for prefix, key in label_map:
            if t.startswith(prefix):
                if i + 1 < len(texts):
                    val = texts[i + 1].strip()
                    val = val.replace("|", "").strip()
                    if val:
                        result[key] = val
                break
    return result


def _extract_quantity_from_buffer(buffer: List[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """
    From the "product+quantity" rows preceding a location row, find the
    quantity. Convention: quantity is the rightmost integer of one of the rows.
    Prefer the row whose rightmost integer is right-aligned near the page
    right (i.e., in the Quantité column).
    """
    candidates = []
    for br in buffer:
        rightmost = max(br, key=lambda s: s["x1"])
        if re.match(r"^\d{1,4}$", rightmost["t"]):
            candidates.append((rightmost["x1"], int(rightmost["t"]), rightmost, br))
    if not candidates:
        # fallback: any integer anywhere in the buffer
        for br in buffer:
            for s in br:
                if re.match(r"^\d{1,4}$", s["t"]):
                    return {"quantity": int(s["t"]), "span": s, "row": br}
        return None
    # Prefer the rightmost x (Quantité column is on the right)
    candidates.sort(key=lambda c: -c[0])
    x1, q, span, br = candidates[0]
    return {"quantity": q, "span": span, "row": br}


def parse_delivery_note(pdf_path: str) -> Dict[str, Any]:
    """
    Parse a delivery-note PDF (SOGO TECH format, robust to sub-formats).
    Returns { order_number, pages, lines[] } with bbox normalized 0..1.
    """
    doc = fitz.open(pdf_path)
    pages_info: List[Dict[str, float]] = []
    all_lines: List[Dict[str, Any]] = []

    order_number: Optional[str] = None
    line_counter = 0

    for page_num, page in enumerate(doc, start=1):
        pw, ph = page.rect.width, page.rect.height
        pages_info.append({"width": pw, "height": ph})

        if order_number is None:
            top_txt = page.get_text("text")
            m = ORDER_NUMBER_RE.search(top_txt)
            if m:
                order_number = m.group(1)

        rows = _rows_from_page(page)
        if not rows:
            continue

        # Find header row on this page (may not exist on continuation pages)
        start_idx = 0
        for idx, r in enumerate(rows):
            joined = _strip_accents(" ".join(s["t"] for s in r).lower())
            if "produits" in joined and ("quantit" in joined or "qte" in joined):
                start_idx = idx + 1
                break

        buffer: List[List[Dict[str, Any]]] = []
        for row in rows[start_idx:]:
            joined_row_text = " ".join(s["t"] for s in row)
            # Skip footer/totals
            if re.match(r"^(page \d|\d+/\d+\s*$|www\.|Tel\.|siret|tva)", joined_row_text, re.IGNORECASE):
                continue

            if _is_location_row(row):
                if not buffer:
                    continue
                loc = _parse_location_row(row)
                qty_info = _extract_quantity_from_buffer(buffer)
                if qty_info is None:
                    buffer = []
                    continue
                qty = qty_info["quantity"]
                qty_span = qty_info["span"]

                # Build product name: all spans in buffer except the quantity integer,
                # and skip any spurious location tokens.
                name_parts: List[str] = []
                for br in buffer:
                    for s in sorted(br, key=lambda x: x["x0"]):
                        if s is qty_span:
                            continue
                        t = s["t"].strip()
                        if not t:
                            continue
                        # Skip stray location labels inside the buffer
                        if _strip_accents(t.lower()).rstrip(" :") in LOCATION_LABELS:
                            continue
                        name_parts.append(t)
                product_name = " ".join(name_parts).strip() or None

                # BBox: union of all spans + location row + pad
                all_spans = [s for br in buffer for s in br] + row
                y0 = min(s["y0"] for s in all_spans)
                y1 = max(s["y1"] for s in all_spans)
                bx0 = 0.02 * pw
                bx1 = 0.98 * pw
                by0 = max(0.0, y0 - 2.0)
                by1 = min(ph, y1 + 2.0)

                line_counter += 1
                all_lines.append({
                    "line_index": line_counter,
                    "page": page_num,
                    "product_name": product_name,
                    "reference": loc["reference"],
                    "etagere": loc["etagere"],
                    "colonne": loc["colonne"],
                    "tiroir": loc["tiroir"],
                    "bac": loc["bac"],
                    "quantity": qty,
                    "bbox": [
                        _round(bx0 / pw),
                        _round(by0 / ph),
                        _round((bx1 - bx0) / pw),
                        _round((by1 - by0) / ph),
                    ],
                })
                buffer = []
            else:
                if row:
                    buffer.append(row)

    doc.close()

    return {
        "order_number": order_number,
        "pages": pages_info,
        "lines": all_lines,
    }
