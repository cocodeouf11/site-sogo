import { useState } from "react";
import { Delete } from "lucide-react";

export default function Numpad({ onSubmit, maxLength = 6, disabled }) {
    const [code, setCode] = useState("");

    const push = (n) => {
        if (disabled) return;
        setCode((c) => (c.length >= maxLength ? c : c + String(n)));
    };
    const del = () => {
        if (disabled) return;
        setCode((c) => c.slice(0, -1));
    };
    const submit = () => {
        if (disabled || code.length === 0) return;
        onSubmit(code);
    };

    const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

    return (
        <div className="w-full max-w-md mx-auto flex flex-col gap-6">
            <div
                data-testid="numpad-display"
                className="nb-border-thick bg-white h-24 flex items-center justify-center text-5xl font-black tabular-nums tracking-[0.4em] pl-[0.4em]"
                aria-label="Code opérateur"
            >
                {code.length === 0 ? (
                    <span className="text-zinc-300">— — — —</span>
                ) : (
                    <span>{"•".repeat(code.length)}</span>
                )}
            </div>

            <div className="grid grid-cols-3 gap-4">
                {keys.map((k) => (
                    <button
                        key={k}
                        type="button"
                        data-testid={`numpad-key-${k}`}
                        onClick={() => push(k)}
                        className="h-24 sm:h-28 border-2 border-black bg-white text-4xl font-black tabular-nums rounded-md active:bg-black active:text-white transition-colors duration-75"
                    >
                        {k}
                    </button>
                ))}
                <button
                    type="button"
                    data-testid="numpad-key-clear"
                    onClick={del}
                    className="h-24 sm:h-28 border-2 border-black bg-white text-2xl font-bold rounded-md active:bg-black active:text-white transition-colors duration-75 flex items-center justify-center"
                    aria-label="Effacer"
                >
                    <Delete size={28} />
                </button>
                <button
                    type="button"
                    data-testid="numpad-key-0"
                    onClick={() => push("0")}
                    className="h-24 sm:h-28 border-2 border-black bg-white text-4xl font-black tabular-nums rounded-md active:bg-black active:text-white transition-colors duration-75"
                >
                    0
                </button>
                <button
                    type="button"
                    data-testid="numpad-key-submit"
                    onClick={submit}
                    className="h-24 sm:h-28 border-2 border-black bg-black text-white text-2xl font-black rounded-md active:scale-95 transition-transform duration-75"
                >
                    OK
                </button>
            </div>
        </div>
    );
}
