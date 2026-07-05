import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Numpad from "../components/Numpad";
import { authApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Boxes } from "lucide-react";

export default function Login() {
    const nav = useNavigate();
    const { login } = useAuth();
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const handle = async (code) => {
        setLoading(true);
        setError(null);
        try {
            const res = await authApi.login(code);
            login(res.operator, res.token);
            nav("/orders");
        } catch (e) {
            setError(e?.response?.data?.detail || "Code invalide");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-6 gap-8 bg-[var(--bg-base)]">
            <div className="text-center">
                <div className="flex items-center justify-center gap-3 mb-3">
                    <div className="nb-border-thick bg-black text-white h-14 w-14 flex items-center justify-center">
                        <Boxes size={32} strokeWidth={2.5} />
                    </div>
                </div>
                <h1 className="text-4xl sm:text-5xl font-black tracking-tight uppercase" data-testid="login-title">
                    PICKING
                </h1>
                <p className="text-lg font-medium text-zinc-500 mt-2">
                    Entrez votre code opérateur
                </p>
            </div>

            <Numpad onSubmit={handle} disabled={loading} />

            {error && (
                <div
                    data-testid="login-error"
                    className="nb-border bg-red-100 text-red-800 font-bold p-4 max-w-md w-full text-center uppercase"
                >
                    {error}
                </div>
            )}

            <div className="text-xs text-zinc-400 uppercase tracking-widest text-center">
                Codes test : 1234 · 5678 · 0000
            </div>
        </div>
    );
}
