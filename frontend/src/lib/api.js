import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
    baseURL: API_BASE,
    timeout: 60000,
});

api.interceptors.request.use((config) => {
    const code = localStorage.getItem("operator_code");
    if (code) config.headers["X-Operator-Code"] = code;
    return config;
});

export default api;

export const authApi = {
    login: (code) => api.post("/auth/login", { code }).then((r) => r.data),
};

export const ordersApi = {
    list: (q) => api.get("/orders", { params: q ? { q } : {} }).then((r) => r.data),
    get: (id) => api.get(`/orders/${id}`).then((r) => r.data),
    remove: (id) => api.delete(`/orders/${id}`).then((r) => r.data),
    create: (formData, onProgress) =>
        api
            .post("/orders", formData, {
                headers: { "Content-Type": "multipart/form-data" },
                onUploadProgress: onProgress,
            })
            .then((r) => r.data),
    increment: (orderId, lineId, delta = 1) =>
        api.post(`/orders/${orderId}/lines/${lineId}/increment`, { delta }).then((r) => r.data),
    resetLine: (orderId, lineId) => api.post(`/orders/${orderId}/lines/${lineId}/reset`).then((r) => r.data),
    pdfUrl: (id) => `${API_BASE}/orders/${id}/pdf`,
    labelUrl: (id, cropped = true) => `${API_BASE}/orders/${id}/label?cropped=${cropped ? "true" : "false"}`,
};
