import { createContext, useContext, useEffect, useState } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [operator, setOperator] = useState(() => {
        try {
            const raw = localStorage.getItem("operator");
            return raw ? JSON.parse(raw) : null;
        } catch {
            return null;
        }
    });

    useEffect(() => {
        if (operator) localStorage.setItem("operator", JSON.stringify(operator));
        else localStorage.removeItem("operator");
    }, [operator]);

    const login = (op, token) => {
        localStorage.setItem("operator_code", token);
        setOperator(op);
    };
    const logout = () => {
        localStorage.removeItem("operator_code");
        setOperator(null);
    };

    return <AuthContext.Provider value={{ operator, login, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
