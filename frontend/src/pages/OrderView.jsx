import { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import PdfViewer from "../components/PdfViewer";
import { ordersApi } from "../lib/api";
import { ArrowLeft, Printer, RotateCcw, Tag, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function OrderView() {
    const { id } = useParams();
    const nav = useNavigate();
    const [order, setOrder] = useState(null);
    const [lines, setLines] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showActions, setShowActions] = useState(false);

    const load = useCallback(async () => {
        try {
            const data = await ordersApi.get(id);
            setOrder(data.order);
            setLines(data.lines);
        } catch (e) {
            toast.error("Impossible de charger la commande");
            nav("/orders");
        } finally {
            setLoading(false);
        }
    }, [id, nav]);

    useEffect(() => {
        load();
    }, [load]);

    const onLineClick = useCallback(
        async (line) => {
            if (line.picked >= line.quantity) return;
            // Optimistic update
            setLines((prev) =>
                prev.map((l) => (l.id === line.id ? { ...l, picked: Math.min(l.picked + 1, l.quantity) } : l))
            );
            try {
                const res = await ordersApi.increment(id, line.id, 1);
                setOrder((o) =>
                    o
                        ? {
                              ...o,
                              picked_qty: res.picked_qty,
                              done_lines: res.done_lines,
                              status: res.status,
                          }
                        : o
                );
                if (res.status === "done") {
                    toast.success("Commande terminée !", { duration: 3000 });
                }
            } catch (e) {
                toast.error("Échec de la validation");
                load();
            }
        },
        [id, load]
    );

    const onLineLongPress = useCallback(
        async (line) => {
            if (line.picked === 0) return;
            setLines((prev) => prev.map((l) => (l.id === line.id ? { ...l, picked: 0 } : l)));
            try {
                await ordersApi.resetLine(id, line.id);
                await load();
                toast.info("Ligne réinitialisée");
            } catch (e) {
                toast.error("Échec de la réinitialisation");
                load();
            }
        },
        [id, load]
    );

    if (loading) {
        return <div className="p-12 text-center font-bold" data-testid="order-loading">Chargement...</div>;
    }
    if (!order) return null;

    const totalQty = order.total_qty || 0;
    const pickedQty = order.picked_qty || 0;
    const pct = totalQty > 0 ? Math.round((pickedQty / totalQty) * 100) : 0;
    const done = order.status === "done";

    const pdfUrl = ordersApi.pdfUrl(id);

    return (
        <div className="min-h-screen bg-[var(--bg-pdf)]">
            {/* Progress header */}
            <header
                className="sticky top-0 z-40 bg-white border-b-4 border-black no-print"
                data-testid="progress-header"
            >
                <div className="relative">
                    {/* Progress fill background */}
                    <div
                        className={`absolute inset-y-0 left-0 ${done ? "bg-green-500/80" : "bg-orange-400/40"} transition-all`}
                        style={{ width: `${pct}%` }}
                    />
                    <div className="relative flex items-center gap-3 p-3">
                        <button
                            onClick={() => nav("/orders")}
                            className="h-14 w-14 border-2 border-black bg-white rounded-md active:bg-black active:text-white flex items-center justify-center shrink-0"
                            data-testid="order-back"
                            aria-label="Retour"
                        >
                            <ArrowLeft size={24} />
                        </button>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-baseline gap-3">
                                <div className="text-xs font-bold uppercase tracking-widest text-zinc-700 shrink-0">
                                    Cmd
                                </div>
                                <div
                                    className="text-2xl font-black tabular-nums truncate"
                                    data-testid="order-number-header"
                                >
                                    {order.order_number}
                                </div>
                            </div>
                            <div className="text-lg font-black tabular-nums" data-testid="progress-counter">
                                {pickedQty}/{totalQty}
                                <span className="text-zinc-600 mx-2">·</span>
                                {pct}%
                            </div>
                        </div>
                        <button
                            onClick={() => setShowActions((v) => !v)}
                            className="h-14 px-4 border-2 border-black bg-white font-black uppercase rounded-md active:bg-black active:text-white"
                            data-testid="order-actions-btn"
                        >
                            Actions
                        </button>
                    </div>
                </div>

                {showActions && (
                    <div className="border-t-2 border-black bg-zinc-50 p-3 flex flex-wrap gap-2" data-testid="order-actions">
                        {order.label_cropped_path && (
                            <Link
                                to={`/orders/${id}/label`}
                                className="btn-lg btn-lg-outline flex-1 min-w-[180px]"
                                data-testid="view-label-btn"
                            >
                                <Tag size={22} /> Étiquette
                            </Link>
                        )}
                        <button
                            onClick={() => window.print()}
                            className="btn-lg btn-lg-outline flex-1 min-w-[180px]"
                            data-testid="print-btn"
                        >
                            <Printer size={22} /> Imprimer
                        </button>
                    </div>
                )}
            </header>

            {done && (
                <div className="bg-green-500 text-white p-3 text-center font-black uppercase tracking-widest border-b-4 border-black no-print" data-testid="order-done-banner">
                    <CheckCircle2 className="inline mr-2" /> Commande terminée
                </div>
            )}

            {/* PDF viewer */}
            <div className="p-2 sm:p-3">
                <PdfViewer
                    fileUrl={pdfUrl}
                    lines={lines}
                    onLineClick={onLineClick}
                    onLineLongPress={onLineLongPress}
                />
            </div>

            <div className="p-4 text-center text-xs text-zinc-500 uppercase tracking-widest no-print">
                Appui long sur une ligne pour réinitialiser
            </div>
        </div>
    );
}
