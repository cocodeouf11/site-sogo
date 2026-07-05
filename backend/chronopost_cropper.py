"""
Chronopost label auto-cropper.

Two entry-points:

- crop_chronopost_labels(src, dst): used during order upload — crops each
  page to the union bbox of content, preserving orientation. Suitable for
  labels that are already correctly oriented.

- resize_label_to_portrait(src, dst): standalone label resizer. Detects
  content bbox on each page, rotates 90° when the content is landscape,
  and outputs a compact portrait label PDF (matching the Chronopost target
  format ~320×416 pt).
"""
from __future__ import annotations
import fitz
from pathlib import Path


PADDING_PT = 2.0  # tiny padding so the outer border isn't clipped


def _union_bbox(rects):
    if not rects:
        return None
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return fitz.Rect(x0, y0, x1, y1)


def _content_bbox(page: fitz.Page) -> fitz.Rect:
    """Return the tightest bbox around all drawings + text on the page."""
    rects = []
    for d in page.get_drawings():
        r = d.get("rect")
        if r and r.get_area() > 5:
            rects.append(fitz.Rect(r))

    tdict = page.get_text("dict")
    for block in tdict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                bbox = span.get("bbox")
                if bbox:
                    rects.append(fitz.Rect(bbox))

    bbox = _union_bbox(rects) or page.rect
    page_rect = page.rect
    return fitz.Rect(
        max(page_rect.x0, bbox.x0 - PADDING_PT),
        max(page_rect.y0, bbox.y0 - PADDING_PT),
        min(page_rect.x1, bbox.x1 + PADDING_PT),
        min(page_rect.y1, bbox.y1 + PADDING_PT),
    )


def crop_chronopost_labels(src_pdf: str, dst_pdf: str) -> dict:
    """Crop each page to content bbox (preserves orientation)."""
    src = fitz.open(src_pdf)
    out = fitz.open()
    info = []

    for page_num, page in enumerate(src, start=1):
        bbox = _content_bbox(page)
        new_w = bbox.width
        new_h = bbox.height
        new_page = out.new_page(width=new_w, height=new_h)
        new_page.show_pdf_page(
            fitz.Rect(0, 0, new_w, new_h),
            src,
            page_num - 1,
            clip=bbox,
        )
        info.append({"page": page_num, "width_pt": round(new_w, 2), "height_pt": round(new_h, 2)})

    Path(dst_pdf).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst_pdf)
    out.close()
    src.close()
    return {"labels": info, "count": len(info)}


# Target dimensions when re-orienting a landscape label to Chronopost portrait.
# Chronopost standard = 100×150 mm ≈ 283×425 pt; the sample 2.pdf is 319.59×416.71
# so we scale the content to fit within 320×420 while preserving aspect ratio.
TARGET_MAX_W_PT = 320.0
TARGET_MAX_H_PT = 420.0


def resize_label_to_portrait(src_pdf: str, dst_pdf: str) -> dict:
    """
    Standalone label resizer:
    - Detect content bbox for each page
    - If content is landscape (width > height), rotate 90° CCW so it becomes portrait
    - Scale the result to fit within 320×420 pt while preserving aspect ratio
    - Output as a compact portrait PDF (one page per source page)
    """
    src = fitz.open(src_pdf)
    out = fitz.open()
    info = []

    for page_num, page in enumerate(src, start=1):
        bbox = _content_bbox(page)
        cw = bbox.width
        ch = bbox.height

        # Decide if we need to rotate to portrait
        rotate_90 = cw > ch  # landscape source → rotate

        # Final orientation dimensions (before scaling)
        if rotate_90:
            final_w = ch
            final_h = cw
        else:
            final_w = cw
            final_h = ch

        # Scale to fit target
        scale = min(TARGET_MAX_W_PT / final_w, TARGET_MAX_H_PT / final_h, 1.5)
        # Allow slight upscaling if source is tiny; cap at 1.5x
        new_w = final_w * scale
        new_h = final_h * scale

        new_page = out.new_page(width=new_w, height=new_h)

        # show_pdf_page supports rotate parameter (0, 90, 180, 270) applied
        # on the SOURCE content before placing it into `rect`.
        if rotate_90:
            new_page.show_pdf_page(
                fitz.Rect(0, 0, new_w, new_h),
                src,
                page_num - 1,
                clip=bbox,
                rotate=270,  # CCW to bring right side up when source is landscape
            )
        else:
            new_page.show_pdf_page(
                fitz.Rect(0, 0, new_w, new_h),
                src,
                page_num - 1,
                clip=bbox,
            )

        info.append({
            "page": page_num,
            "rotated": rotate_90,
            "width_pt": round(new_w, 2),
            "height_pt": round(new_h, 2),
        })

    Path(dst_pdf).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst_pdf)
    out.close()
    src.close()
    return {"labels": info, "count": len(info)}
