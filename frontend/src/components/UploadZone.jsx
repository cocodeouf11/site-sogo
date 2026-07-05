import { useRef, useState } from "react";
import { Upload, FileText, Tag, X } from "lucide-react";

export default function UploadZone({ label, testId, onFile, file, accept = ".pdf,application/pdf", icon }) {
    const inputRef = useRef(null);
    const [dragOver, setDragOver] = useState(false);

    const handleChange = (e) => {
        const f = e.target.files?.[0];
        if (f) onFile(f);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
    };

    return (
        <div
            data-testid={testId}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`w-full min-h-[180px] border-4 border-dashed ${dragOver ? "border-orange-500 bg-orange-50" : "border-black bg-zinc-50"} rounded-md flex flex-col items-center justify-center gap-3 cursor-pointer active:bg-zinc-100 p-6 transition-colors`}
        >
            <input
                ref={inputRef}
                type="file"
                accept={accept}
                onChange={handleChange}
                className="hidden"
                data-testid={`${testId}-input`}
            />
            {icon || <Upload size={56} strokeWidth={2.5} />}
            {file ? (
                <div className="flex items-center gap-3 max-w-full">
                    <FileText size={22} />
                    <span className="font-bold truncate max-w-[220px]" data-testid={`${testId}-filename`}>
                        {file.name}
                    </span>
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            onFile(null);
                        }}
                        className="ml-1 p-1 rounded-full bg-black text-white"
                        data-testid={`${testId}-clear`}
                        aria-label="Retirer"
                    >
                        <X size={16} />
                    </button>
                </div>
            ) : (
                <div className="text-center">
                    <div className="text-xl font-black uppercase tracking-wider">{label}</div>
                    <div className="text-sm text-zinc-500 mt-1">PDF · max 25 Mo</div>
                </div>
            )}
        </div>
    );
}
