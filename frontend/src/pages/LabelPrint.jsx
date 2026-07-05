import { useNavigate, useParams } from "react-router-dom";
import { ordersApi } from "../lib/api";
import { ArrowLeft, Printer } from "lucide-react";

export default function LabelPrint() {
    const { id } = useParams();
    const nav = useNavigate();
    const url = ordersApi.labelUrl(id, true);

    return (
        <div className="min-h-screen bg-[var(--bg-pdf)]">
            <header className="sticky top-0 z-40 bg-white border-b-4 border-black px-4 py-3 flex items-center gap-3 no-print" data-testid="label-header">
                <button
                    onClick={() => nav(-1)}
                    className="h-12 w-12 border-2 border-black bg-white rounded-md active:bg-black active:text-white flex items-center justify-center"
                    data-testid="label-back"
                    aria-label="Retour"
                >
                    <ArrowLeft size={22} />
                </button>
                <div className="flex-1">
                    <div className="text-xs font-bold uppercase tracking-widest text-zinc-500">Étiquette</div>
                    <div className="text-xl font-black">Chronopost (recadrée)</div>
                </div>
                <button
                    onClick={() => window.print()}
                    className="btn-lg"
                    data-testid="label-print-btn"
                >
                    <Printer size={22} /> Imprimer
                </button>
            </header>

            <div className="p-3">
                <div className="bg-white nb-border overflow-hidden">
                    <object
                        data={url}
                        type="application/pdf"
                        className="w-full print-full"
                        style={{ height: "80vh" }}
                        data-testid="label-pdf-object"
                    >
                        <embed src={url} type="application/pdf" />
                    </object>
                </div>
            </div>
        </div>
    );
}
