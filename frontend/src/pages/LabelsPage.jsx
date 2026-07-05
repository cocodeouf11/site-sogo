import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { labelsApi } from "../lib/api";
import { ArrowLeft, Tag, Upload as UploadIcon, Trash2, Printer, Download, FileText } from "lucide-react";
import { toast } from "sonner";
import UploadZone from "../components/UploadZone";

export default function LabelsPage() {
    const nav = useNavigate();
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [labels, setLabels] = useState([]);
    const [previewId, setPreviewId] = useState(null);

    const refresh = async () => {
        try {
            const data = await labelsApi.list();
            setLabels(data);
        } catch {
            toast.error("Erreur de chargement");
        }
    };

    useEffect(() => {
        refresh();
    }, []);

    const submit = async () => {
        if (!file) {
            toast.error("Sélectionnez un PDF d'étiquette");
            return;
        }
        setUploading(true);
        setProgress(0);
        try {
            const res = await labelsApi.resize(file, (e) => {
                if (e.total) setProgress(Math.round((e.loaded / e.total) * 100));
            });
            toast.success(`Étiquette redimensionnée (${res.pages} page${res.pages > 1 ? "s" : ""})`);
            setFile(null);
            setPreviewId(res.id);
            refresh();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Échec du recadrage");
        } finally {
            setUploading(false);
        }
    };

    const remove = async (id) => {
        try {
            await labelsApi.remove(id);
            setLabels((ls) => ls.filter((l) => l.id !== id));
            if (previewId === id) setPreviewId(null);
            toast.success("Étiquette supprimée");
        } catch {
            toast.error("Suppression impossible");
        }
    };

    const printLabel = (id) => {
        const url = labelsApi.downloadUrl(id);
        // Open in new tab and trigger print
        const w = window.open(url, "_blank");
        if (w) setTimeout(() => w.print(), 800);
    };

    return (
        <div className="min-h-screen bg-[var(--bg-base)]">
            <header className="sticky top-0 z-40 bg-white border-b-4 border-black px-4 py-3 flex items-center gap-3" data-testid="labels-header">
                <button
                    onClick={() => nav("/orders")}
                    className="h-12 w-12 border-2 border-black bg-white rounded-md active:bg-black active:text-white flex items-center justify-center"
                    data-testid="labels-back"
                    aria-label="Retour"
                >
                    <ArrowLeft size={22} />
                </button>
                <div className="flex-1">
                    <div className="text-xs font-bold uppercase tracking-widest text-zinc-500">Outil</div>
                    <div className="text-xl font-black">Recadrer une étiquette</div>
                </div>
            </header>

            <div className="p-4 space-y-6 max-w-2xl mx-auto">
                <div className="nb-border bg-white p-4 space-y-4">
                    <div className="text-sm font-bold uppercase tracking-widest text-zinc-500">Nouveau recadrage</div>
                    <UploadZone
                        label="Étiquette à recadrer"
                        testId="labels-upload"
                        onFile={setFile}
                        file={file}
                        icon={<Tag size={56} strokeWidth={2} />}
                    />

                    {uploading && (
                        <div data-testid="labels-progress" className="space-y-2">
                            <div className="flex justify-between text-sm font-bold uppercase">
                                <span>Recadrage en cours</span>
                                <span className="tabular-nums">{progress}%</span>
                            </div>
                            <div className="h-4 bg-zinc-200 border border-black">
                                <div className="h-full bg-black" style={{ width: `${progress}%` }} />
                            </div>
                        </div>
                    )}

                    <button
                        onClick={submit}
                        disabled={!file || uploading}
                        className="btn-lg w-full"
                        data-testid="labels-submit"
                    >
                        <UploadIcon size={22} strokeWidth={3} />
                        {uploading ? "Traitement..." : "Recadrer"}
                    </button>
                </div>

                {previewId && (
                    <div className="nb-border bg-white p-3 space-y-3" data-testid="labels-preview">
                        <div className="flex items-center justify-between">
                            <div className="font-black uppercase">Aperçu</div>
                            <div className="flex gap-2">
                                <a
                                    href={labelsApi.downloadUrl(previewId)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    download
                                    className="h-12 px-4 border-2 border-black bg-white font-black uppercase rounded-md active:bg-black active:text-white flex items-center gap-2"
                                    data-testid="labels-download"
                                >
                                    <Download size={18} /> Télécharger
                                </a>
                                <button
                                    onClick={() => printLabel(previewId)}
                                    className="btn-lg h-12 px-4 min-h-0 text-sm"
                                    data-testid="labels-print"
                                >
                                    <Printer size={18} /> Imprimer
                                </button>
                            </div>
                        </div>
                        <object
                            data={labelsApi.downloadUrl(previewId)}
                            type="application/pdf"
                            className="w-full"
                            style={{ height: "60vh" }}
                        >
                            <embed src={labelsApi.downloadUrl(previewId)} type="application/pdf" />
                        </object>
                    </div>
                )}

                {labels.length > 0 && (
                    <div className="space-y-2">
                        <div className="text-sm font-bold uppercase tracking-widest text-zinc-500 px-1">Historique</div>
                        {labels.map((l) => (
                            <div
                                key={l.id}
                                className="nb-border bg-white p-3 flex items-center gap-3"
                                data-testid={`label-card-${l.id}`}
                            >
                                <FileText size={22} className="shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <div className="font-black truncate" data-testid={`label-filename-${l.id}`}>
                                        {l.filename || "étiquette.pdf"}
                                    </div>
                                    <div className="text-xs text-zinc-500 tabular-nums">
                                        {l.pages} page{l.pages > 1 ? "s" : ""} · {new Date(l.created_at).toLocaleString("fr-FR")}
                                    </div>
                                </div>
                                <button
                                    onClick={() => setPreviewId(l.id)}
                                    className="h-10 px-3 border-2 border-black bg-white font-bold rounded-md active:bg-black active:text-white text-sm"
                                    data-testid={`label-view-${l.id}`}
                                >
                                    Voir
                                </button>
                                <button
                                    onClick={() => printLabel(l.id)}
                                    className="h-10 w-10 border-2 border-black bg-white rounded-md active:bg-black active:text-white flex items-center justify-center"
                                    data-testid={`label-print-${l.id}`}
                                    aria-label="Imprimer"
                                >
                                    <Printer size={16} />
                                </button>
                                <button
                                    onClick={() => remove(l.id)}
                                    className="h-10 w-10 border-2 border-black bg-white rounded-md active:bg-red-600 active:text-white flex items-center justify-center"
                                    data-testid={`label-delete-${l.id}`}
                                    aria-label="Supprimer"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
