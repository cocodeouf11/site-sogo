import { useEffect, useRef, useState, useCallback } from "react";
import * as pdfjsLib from "pdfjs-dist";

// Set PDF.js worker to matching version from CDN
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

/**
 * PdfViewer - renders every page of a PDF via PDF.js and overlays clickable
 * zones on top of each product line for tap-to-increment behaviour.
 *
 * Props:
 *  - fileUrl: absolute URL of the PDF (with credentials header if needed)
 *  - lines: list of order-lines (with bbox, quantity, picked, page)
 *  - onLineClick(line): called when a line zone is tapped
 *  - onLineLongPress(line): optional, called on long-press (for reset)
 */
export default function PdfViewer({ fileUrl, lines = [], onLineClick, onLineLongPress }) {
    const containerRef = useRef(null);
    const [pageRenderData, setPageRenderData] = useState([]); // [{ pageNum, width, height }]
    const [scale, setScale] = useState(1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Determine base viewport scale from container width.
    // Higher scale = sharper. We use the render scale but keep CSS width relative.
    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const loadingTask = pdfjsLib.getDocument({ url: fileUrl });
            const pdf = await loadingTask.promise;
            const container = containerRef.current;
            if (!container) return;

            // Clear previous pages
            container.innerHTML = "";

            const containerWidth = container.clientWidth - 16; // small padding
            const dpr = window.devicePixelRatio || 1;

            const pageInfo = [];

            for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
                const page = await pdf.getPage(pageNum);
                const baseViewport = page.getViewport({ scale: 1 });
                const cssScale = containerWidth / baseViewport.width;
                const renderScale = cssScale * dpr;
                const renderViewport = page.getViewport({ scale: renderScale });

                const pageWrap = document.createElement("div");
                pageWrap.className = "relative bg-white nb-border mx-auto mb-4";
                pageWrap.style.width = `${baseViewport.width * cssScale}px`;
                pageWrap.style.height = `${baseViewport.height * cssScale}px`;
                pageWrap.dataset.pageNum = String(pageNum);

                const canvas = document.createElement("canvas");
                canvas.width = renderViewport.width;
                canvas.height = renderViewport.height;
                canvas.style.width = "100%";
                canvas.style.height = "100%";
                canvas.style.display = "block";
                pageWrap.appendChild(canvas);

                const overlay = document.createElement("div");
                overlay.className = "pdf-layer";
                overlay.dataset.pageOverlay = String(pageNum);
                pageWrap.appendChild(overlay);

                container.appendChild(pageWrap);

                const ctx = canvas.getContext("2d");
                await page.render({ canvasContext: ctx, viewport: renderViewport }).promise;

                pageInfo.push({
                    pageNum,
                    width: baseViewport.width * cssScale,
                    height: baseViewport.height * cssScale,
                });
            }

            setPageRenderData(pageInfo);
            setLoading(false);
        } catch (e) {
            console.error("PDF load error", e);
            setError(String(e?.message || e));
            setLoading(false);
        }
    }, [fileUrl]);

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fileUrl]);

    // Handle re-render on resize (debounced)
    useEffect(() => {
        let t;
        const handle = () => {
            clearTimeout(t);
            t = setTimeout(load, 300);
        };
        window.addEventListener("resize", handle);
        return () => {
            window.removeEventListener("resize", handle);
            clearTimeout(t);
        };
    }, [load]);

    // Render overlays whenever lines or page dims change
    useEffect(() => {
        if (loading || pageRenderData.length === 0) return;
        const container = containerRef.current;
        if (!container) return;

        // Clear existing overlays
        container.querySelectorAll("[data-page-overlay]").forEach((ov) => {
            ov.innerHTML = "";
        });

        for (const line of lines) {
            const page = pageRenderData.find((p) => p.pageNum === line.page);
            if (!page) continue;
            const overlay = container.querySelector(`[data-page-overlay="${line.page}"]`);
            if (!overlay) continue;

            const zone = document.createElement("div");
            const done = line.picked >= line.quantity;
            const partial = line.picked > 0 && !done;
            zone.className = `pdf-zone ${done ? "pdf-zone--done" : partial ? "pdf-zone--partial" : "pdf-zone--todo"}`;
            zone.style.left = `${line.x * page.width}px`;
            zone.style.top = `${line.y * page.height}px`;
            zone.style.width = `${line.width * page.width}px`;
            zone.style.height = `${line.height * page.height}px`;
            zone.dataset.testid = `pdf-line-${line.line_index}`;
            zone.dataset.lineId = line.id;

            const badge = document.createElement("div");
            badge.className = `pdf-badge ${done ? "pdf-badge--done" : ""}`;
            badge.textContent = done ? "✓" : `${line.picked}/${line.quantity}`;
            zone.appendChild(badge);

            let pressTimer;
            const handlePress = (e) => {
                e.preventDefault();
                if (onLineClick) onLineClick(line);
            };
            zone.addEventListener("click", handlePress);
            // Long-press for reset
            const onDown = () => {
                if (!onLineLongPress) return;
                pressTimer = setTimeout(() => {
                    onLineLongPress(line);
                    pressTimer = null;
                }, 700);
            };
            const cancel = () => {
                if (pressTimer) clearTimeout(pressTimer);
                pressTimer = null;
            };
            zone.addEventListener("pointerdown", onDown);
            zone.addEventListener("pointerup", cancel);
            zone.addEventListener("pointerleave", cancel);
            zone.addEventListener("pointercancel", cancel);

            overlay.appendChild(zone);
        }
    }, [lines, pageRenderData, loading, onLineClick, onLineLongPress]);

    return (
        <div className="w-full">
            {loading && (
                <div className="p-8 text-center text-xl font-bold" data-testid="pdf-loading">
                    Chargement du PDF...
                </div>
            )}
            {error && (
                <div className="p-4 nb-border bg-red-100 text-red-800 font-bold" data-testid="pdf-error">
                    Erreur PDF: {error}
                </div>
            )}
            <div
                ref={containerRef}
                data-testid="pdf-viewer-container"
                className="pdf-scroll w-full flex flex-col items-center py-2"
                style={{ background: "var(--bg-pdf)" }}
            />
        </div>
    );
}
