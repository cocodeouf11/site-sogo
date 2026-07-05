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
    const currentPdfRef = useRef(null); // holds current pdf doc for cleanup
    const loadTokenRef = useRef(0); // token to abort in-flight loads
    const [pageRenderData, setPageRenderData] = useState([]); // [{ pageNum, width, height }]
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const load = useCallback(async () => {
        // Cancel any in-flight load by incrementing the token.
        const myToken = ++loadTokenRef.current;

        setLoading(true);
        setError(null);
        try {
            // Destroy previous pdf doc if any
            if (currentPdfRef.current) {
                try {
                    await currentPdfRef.current.destroy();
                } catch (_) {}
                currentPdfRef.current = null;
            }
            const loadingTask = pdfjsLib.getDocument({ url: fileUrl });
            const pdf = await loadingTask.promise;
            if (myToken !== loadTokenRef.current) {
                await pdf.destroy();
                return;
            }
            currentPdfRef.current = pdf;

            const container = containerRef.current;
            if (!container) return;

            // Clear previous pages
            container.innerHTML = "";

            const containerWidth = container.clientWidth - 16; // small padding
            const dpr = Math.min(window.devicePixelRatio || 1, 2);

            const pageInfo = [];

            for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
                if (myToken !== loadTokenRef.current) return; // aborted

                const page = await pdf.getPage(pageNum);
                const baseViewport = page.getViewport({ scale: 1 });
                const cssScale = containerWidth / baseViewport.width;
                const renderScale = cssScale * dpr;
                const renderViewport = page.getViewport({ scale: renderScale });

                if (myToken !== loadTokenRef.current) return;

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

                if (myToken !== loadTokenRef.current) return;

                pageInfo.push({
                    pageNum,
                    width: baseViewport.width * cssScale,
                    height: baseViewport.height * cssScale,
                });
            }

            if (myToken !== loadTokenRef.current) return;
            setPageRenderData(pageInfo);
            setLoading(false);
        } catch (e) {
            if (myToken !== loadTokenRef.current) return;
            console.error("PDF load error", e);
            setError(String(e?.message || e));
            setLoading(false);
        }
    }, [fileUrl]);

    useEffect(() => {
        load();
        return () => {
            // Invalidate any in-flight load on unmount / dep change
            loadTokenRef.current += 1;
            if (currentPdfRef.current) {
                try {
                    currentPdfRef.current.destroy();
                } catch (_) {}
                currentPdfRef.current = null;
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fileUrl]);

    // Re-render on resize (debounced)
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

        // Group lines by page in one pass (much cheaper than repeated queries)
        const linesByPage = new Map();
        for (const l of lines) {
            if (!linesByPage.has(l.page)) linesByPage.set(l.page, []);
            linesByPage.get(l.page).push(l);
        }

        // Iterate actual page overlays present in the DOM (there should be
        // exactly one per rendered page). If duplicates exist (React StrictMode
        // race), the load-cleanup should already have removed them.
        const overlays = container.querySelectorAll("[data-page-overlay]");
        overlays.forEach((overlay) => {
            const pageNum = Number(overlay.dataset.pageOverlay);
            const page = pageRenderData.find((p) => p.pageNum === pageNum);
            if (!page) return;

            // Clear existing zones on this overlay
            overlay.innerHTML = "";
            const pageLines = linesByPage.get(pageNum) || [];
            for (const line of pageLines) {
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
                let longFired = false;
                const handlePress = (e) => {
                    e.preventDefault();
                    if (longFired) {
                        longFired = false;
                        return;
                    }
                    if (onLineClick) onLineClick(line);
                };
                zone.addEventListener("click", handlePress);
                const onDown = () => {
                    if (!onLineLongPress) return;
                    longFired = false;
                    pressTimer = setTimeout(() => {
                        longFired = true;
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
        });
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
