import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ordersApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Plus, Search, LogOut, Trash2, Package, CheckCircle2, Clock } from "lucide-react";
import { toast } from "sonner";

export default function Orders() {
    const nav = useNavigate();
    const { operator, logout } = useAuth();
    const [orders, setOrders] = useState([]);
    const [q, setQ] = useState("");
    const [loading, setLoading] = useState(true);
    const [deleteId, setDeleteId] = useState(null);

    const fetchOrders = async (search = "") => {
        setLoading(true);
        try {
            const data = await ordersApi.list(search);
            setOrders(data);
        } catch (e) {
            toast.error("Erreur de chargement");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchOrders();
    }, []);

    useEffect(() => {
        const t = setTimeout(() => fetchOrders(q), 300);
        return () => clearTimeout(t);
    }, [q]);

    const handleDelete = async (id) => {
        try {
            await ordersApi.remove(id);
            setOrders((os) => os.filter((o) => o.id !== id));
            toast.success("Commande supprimée");
        } catch (e) {
            toast.error("Suppression impossible");
        } finally {
            setDeleteId(null);
        }
    };

    return (
        <div className="min-h-screen">
            {/* Header */}
            <header className="sticky top-0 z-40 bg-white border-b-4 border-black px-4 py-4 flex items-center justify-between gap-4">
                <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-zinc-500">Commandes</div>
                    <div className="text-xl font-black tabular-nums" data-testid="orders-count">
                        {orders.length} commande{orders.length > 1 ? "s" : ""}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <div className="text-right hidden sm:block">
                        <div className="text-xs font-bold uppercase text-zinc-500">Opérateur</div>
                        <div className="font-black">{operator?.name}</div>
                    </div>
                    <button
                        onClick={() => {
                            logout();
                            nav("/");
                        }}
                        className="h-12 w-12 border-2 border-black bg-white rounded-md active:bg-black active:text-white flex items-center justify-center"
                        data-testid="logout-btn"
                        aria-label="Déconnexion"
                    >
                        <LogOut size={20} />
                    </button>
                </div>
            </header>

            <div className="p-4 space-y-4 max-w-3xl mx-auto">
                {/* Search + new order */}
                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex-1 relative">
                        <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400" />
                        <input
                            type="search"
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder="Rechercher n° commande..."
                            className="w-full h-16 pl-12 pr-4 border-2 border-black bg-white text-lg font-medium rounded-md outline-none focus:ring-4 focus:ring-black/10"
                            data-testid="orders-search"
                        />
                    </div>
                    <button
                        onClick={() => nav("/upload")}
                        className="btn-lg"
                        data-testid="new-order-btn"
                    >
                        <Plus size={24} strokeWidth={3} />
                        Nouvelle commande
                    </button>
                </div>

                {/* Orders list */}
                {loading ? (
                    <div className="p-12 text-center font-bold text-zinc-500">Chargement...</div>
                ) : orders.length === 0 ? (
                    <div className="p-12 text-center nb-border bg-white" data-testid="orders-empty">
                        <Package size={64} className="mx-auto mb-3 text-zinc-300" strokeWidth={1.5} />
                        <div className="text-xl font-black uppercase">Aucune commande</div>
                        <div className="text-zinc-500 mt-2">Importez votre premier bon de livraison</div>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {orders.map((o) => {
                            const pct = o.total_qty > 0 ? Math.round((o.picked_qty / o.total_qty) * 100) : 0;
                            const done = o.status === "done";
                            return (
                                <div
                                    key={o.id}
                                    className={`relative nb-border bg-white p-5 active:scale-[0.995] transition-transform ${done ? "bg-green-50" : ""}`}
                                    data-testid={`order-card-${o.id}`}
                                >
                                    <div
                                        className="cursor-pointer"
                                        onClick={() => nav(`/orders/${o.id}`)}
                                    >
                                        <div className="flex items-start justify-between gap-3">
                                            <div>
                                                <div className="text-xs font-bold uppercase tracking-widest text-zinc-500">
                                                    Commande
                                                </div>
                                                <div className="text-3xl font-black tabular-nums" data-testid={`order-number-${o.id}`}>
                                                    {o.order_number}
                                                </div>
                                            </div>
                                            <div className="flex flex-col items-end">
                                                {done ? (
                                                    <div className="flex items-center gap-1 text-green-700 font-black uppercase text-sm">
                                                        <CheckCircle2 size={18} /> Terminée
                                                    </div>
                                                ) : (
                                                    <div className="flex items-center gap-1 text-orange-700 font-black uppercase text-sm">
                                                        <Clock size={18} /> En cours
                                                    </div>
                                                )}
                                                <div className="text-3xl font-black tabular-nums mt-1">
                                                    {pct}%
                                                </div>
                                            </div>
                                        </div>

                                        <div className="mt-3 flex items-baseline justify-between">
                                            <div className="font-bold tabular-nums">
                                                {o.picked_qty} / {o.total_qty}{" "}
                                                <span className="text-zinc-500 font-medium">produits</span>
                                            </div>
                                            <div className="text-sm text-zinc-500 font-medium">
                                                {o.done_lines}/{o.total_lines} lignes
                                            </div>
                                        </div>

                                        <div className="mt-3 h-3 bg-zinc-200 border border-black rounded-none overflow-hidden">
                                            <div
                                                className={`h-full ${done ? "bg-green-500" : "bg-orange-500"}`}
                                                style={{ width: `${pct}%` }}
                                            />
                                        </div>
                                    </div>

                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setDeleteId(o.id);
                                        }}
                                        className="absolute top-3 right-3 h-10 w-10 border-2 border-black bg-white rounded-md active:bg-red-600 active:text-white flex items-center justify-center"
                                        data-testid={`delete-order-${o.id}`}
                                        aria-label="Supprimer"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Delete confirm modal */}
            {deleteId && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4" data-testid="delete-modal">
                    <div className="w-full max-w-md bg-white nb-border-thick p-6 space-y-4">
                        <h3 className="text-2xl font-black uppercase">Supprimer la commande ?</h3>
                        <p className="text-zinc-600">Cette action est irréversible. Les fichiers PDF seront supprimés.</p>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setDeleteId(null)}
                                className="btn-lg btn-lg-outline flex-1"
                                data-testid="delete-cancel"
                            >
                                Annuler
                            </button>
                            <button
                                onClick={() => handleDelete(deleteId)}
                                className="btn-lg flex-1"
                                style={{ background: "var(--err)", borderColor: "var(--err)" }}
                                data-testid="delete-confirm"
                            >
                                Supprimer
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
