function buildUrl(baseUrl, path) {
  return baseUrl ? `${baseUrl.replace(/\/+$/, "")}${path}` : path;
}

async function request(baseUrl, path, { method = "GET", body } = {}) {
  const response = await fetch(buildUrl(baseUrl, path), {
    method,
    credentials: "include",
    headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });


  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch (e) {
      void e;
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export const frictionApi = {
  startAnalysis: (base, payload) => request(base, "/api/v1/friction/analyses", { method: "POST", body: payload }),
  listAnalyses: (base) => request(base, "/api/v1/friction/analyses?limit=20"),
  getAnalysisStatus: (base, runId) => request(base, `/api/v1/friction/analyses/${runId}`),
  getReport: (base, runId) => request(base, `/api/v1/friction/analyses/${runId}/report`),
  getEvidence: (base, indicatorId) => request(base, `/api/v1/friction/indicators/${indicatorId}/evidence`),
  listRepositories: (base) => request(base, "/api/v1/friction/repositories"),
};
