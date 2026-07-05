import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import Login from "@/pages/Login";
import Orders from "@/pages/Orders";
import OrderView from "@/pages/OrderView";
import UploadPage from "@/pages/UploadPage";
import LabelPrint from "@/pages/LabelPrint";
import { Toaster } from "@/components/ui/sonner";

function Protected({ children }) {
    const { operator } = useAuth();
    if (!operator) return <Navigate to="/" replace />;
    return children;
}

export default function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Login />} />
                    <Route
                        path="/orders"
                        element={
                            <Protected>
                                <Orders />
                            </Protected>
                        }
                    />
                    <Route
                        path="/upload"
                        element={
                            <Protected>
                                <UploadPage />
                            </Protected>
                        }
                    />
                    <Route
                        path="/orders/:id"
                        element={
                            <Protected>
                                <OrderView />
                            </Protected>
                        }
                    />
                    <Route
                        path="/orders/:id/label"
                        element={
                            <Protected>
                                <LabelPrint />
                            </Protected>
                        }
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </BrowserRouter>
            <Toaster position="top-center" richColors />
        </AuthProvider>
    );
}
