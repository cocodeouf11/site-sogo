import { useState } from "react";
import { useNavigate } from "react-router-dom";
import UploadZone from "../components/UploadZone";
import { ordersApi } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft, FileText, Tag, Upload as UploadIcon } from "lucide-react";

export default function UploadPage() {
    const nav = useNavigate();
    const [delivery, setDelivery] = useState(null);
    const [label, setLabel] = useState(null);
    const [progress, setProgress] = useState(0);
    const [uploading, setUploading] = useState(false);

    const submit = async () => {
        if (!delivery) {
            toast.error("Sélectionnez un bon de livraison");
            return;
        }
        setUploading(true);
        setProgress(0);
        try {
            const fd = new FormData();
            fd.append("delivery", delivery);
            if (label) fd.append("label", label);
            const res = await ordersApi.create(fd, (evt) => {
                if (evt.total) setProgress(Math.round((evt.loaded / evt.total) * 100));
            });
            toast.success(`Commande ${res.order_number} créée (${res.total_lines} lignes)`);
            nav(`/orders/${res.id}`);
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Échec de l'import");
            setUploading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[var(--bg-base)]">
            <header className="sticky top-0 z-40 bg-white border-b-4 border-black px-4 py-4 flex items-center gap-3">
                <button
                    onClick={() => nav(-1)}
                    className="h-12 w-12 border-2 border-black bg-white rounded-md active:bg-black active:text-white flex items-center justify-center"
                    data-testid="upload-back"
                    aria-label="Retour"
                >
                    <ArrowLeft size={22} />
                </button>
                <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-zinc-500">Nouvelle commande</div>
                    <div className="text-xl font-black">Importer les PDF</div>
                </div>
            </header>

            <div className="p-4 space-y-6 max-w-2xl mx-auto">
                <UploadZone
                    label="Bon de livraison"
                    testId="upload-delivery"
                    onFile={setDelivery}
                    file={delivery}
                    icon={<FileText size={56} strokeWidth={2} />}
                />

                <UploadZone
                    label="Étiquette Chronopost (optionnelle)"
                    testId="upload-label"
                    onFile={setLabel}
                    file={label}
                    icon={<Tag size={56} strokeWidth={2} />}
                />

                {uploading && (
                    <div className="nb-border bg-white p-4 space-y-2" data-testid="upload-progress">
                        <div className="flex justify-between text-sm font-bold uppercase">
                            <span>Analyse en cours</span>
                            <span className="tabular-nums">{progress}%</span>
                        </div>
                        <div className="h-4 bg-zinc-200 border border-black">
                            <div className="h-full bg-black" style={{ width: `${progress}%` }} />
                        </div>
                    </div>
                )}

                <button
                    onClick={submit}
                    disabled={!delivery || uploading}
                    className="btn-lg w-full"
                    data-testid="upload-submit"
                >
                    <UploadIcon size={24} strokeWidth={3} />
                    {uploading ? "Traitement..." : "Créer la commande"}
                </button>
            </div>
        </div>
    );
}
