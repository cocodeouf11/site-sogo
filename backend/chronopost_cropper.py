"""
Chronopost label auto-cropper.
Uses PyMuPDF: detect the drawn label box on each page (bbox of text+drawings)
and export cropped pages to a new PDF.

Strategy: for each page, compute the union bbox of all vector drawings AND
text spans. That gives the printable content area (i.e., the label). We then
apply a small padding and set the page's crop-box (mediabox) so printing
outputs only the label content.

This is more reliable than fixed coordinates because Chronopost PDFs vary
slightly by carrier/version, but always contain a black bordered rectangle
around the label — which is captured perfectly by the drawings bbox.
"""
from __future__ import annotations
import fitz
from pathlib import Path


PADDING_PT = 2.0  # tiny padding to avoid clipping the border stroke


def _union_bbox(rects):
    if not rects:
        return None
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return fitz.Rect(x0, y0, x1, y1)


def crop_chronopost_labels(src_pdf: str, dst_pdf: str) -> dict:
    """
    Read the source Chronopost label PDF and produce a new PDF where each
    page is cropped to the tightest bbox around printed content.
    Returns metadata about labels found.
    """
    src = fitz.open(src_pdf)
    out = fitz.open()

    labels_info = []

    for page_num, page in enumerate(src, start=1):
        rects = []

        # Collect drawings' bboxes (lines/rects/curves)
        drawings = page.get_drawings()
        for d in drawings:
            r = d.get("rect")
            if r and r.get_area() > 5:
                rects.append(fitz.Rect(r))

        # Collect text bboxes
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox")
                    if bbox:
                        rects.append(fitz.Rect(bbox))

        page_rect = page.rect
        bbox = _union_bbox(rects) or page_rect

        # Add padding
        bbox = fitz.Rect(
            max(page_rect.x0, bbox.x0 - PADDING_PT),
            max(page_rect.y0, bbox.y0 - PADDING_PT),
            min(page_rect.x1, bbox.x1 + PADDING_PT),
            min(page_rect.y1, bbox.y1 + PADDING_PT),
        )

        # Create a new page with the cropped dimensions
        new_w = bbox.width
        new_h = bbox.height
        new_page = out.new_page(width=new_w, height=new_h)

        # Draw source content shifted so bbox top-left is at (0,0)
        new_page.show_pdf_page(
            fitz.Rect(0, 0, new_w, new_h),
            src,
            page_num - 1,
            clip=bbox,
        )

        labels_info.append({
            "page": page_num,
            "width_pt": round(new_w, 2),
            "height_pt": round(new_h, 2),
        })

    # Ensure output directory exists
    Path(dst_pdf).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst_pdf)
    out.close()
    src.close()

    return {"labels": labels_info, "count": len(labels_info)}
