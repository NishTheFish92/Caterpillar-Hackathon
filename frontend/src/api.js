const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON; fall back to statusText
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  base: API_BASE,
  health: () => request("/health"),

  // Dashboard
  getTasks: (operatorId, forDate) =>
    request(`/dashboard/${operatorId}/tasks${forDate ? `?for_date=${forDate}` : ""}`),

  // Safety
  getSeatbelt: (machineId) => request(`/safety/seatbelt/${machineId}`),
  getProximity: (machineId) => request(`/safety/proximity/${machineId}`),
  getAllProximityAlerts: () => request("/safety/proximity"),
  getHazardPrediction: (machineId) => request(`/safety/hazard-prediction/${machineId}`),
  logIncident: (payload) =>
    request("/safety/incidents", { method: "POST", body: JSON.stringify(payload) }),
  getIncidents: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/safety/incidents${qs ? `?${qs}` : ""}`);
  },

  // Training
  getArticles: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/training/articles${qs ? `?${qs}` : ""}`);
  },
  getArticle: (articleId) => request(`/training/articles/${articleId}`),
  bookSession: (payload) =>
    request("/training/book", { method: "POST", body: JSON.stringify(payload) }),
  getBookings: (operatorId) => request(`/training/bookings/${operatorId}`),

  // Behavior
  getAnomalies: (operatorId, days = 7) =>
    request(`/behavior/${operatorId}/anomalies?days=${days}`),

  // Estimation
  estimateTaskTime: (payload) =>
    request("/estimation/task-time", { method: "POST", body: JSON.stringify(payload) }),
};
