import type { ConfigurationPayload, State } from "./types";

const API = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || "Request failed");
  return payload as T;
}

async function sensorCaptureCsv(operator: string, version: number, durationSeconds: number, targetRateHz: number) {
  const response = await fetch(`${API}/maintenance/sensor-capture.csv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator, expectedStateVersion: version, durationSeconds, targetRateHz }),
  });
  if (!response.ok) {
    let message = "Sensor capture failed";
    try {
      const payload = await response.json();
      message = payload?.error?.message || payload?.detail || message;
    } catch { /* The backend returned a non-JSON error. */ }
    throw new Error(message);
  }
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || "afds_sensor_capture.csv";
  return {
    blob: await response.blob(),
    filename,
    sampleCount: Number(response.headers.get("X-AFDS-Sample-Count") || 0),
  };
}

export const api = {
  state: () => request<State>("/state"),
  initialize: (operator: string, version: number) => request<State>("/system/initialize", { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version }) }),
  start: (operator: string, version: number) => request<State>("/automatic/start", { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version }) }),
  action: (name: string, version: number) => request<State>(`/control/${name}`, { method: "POST", body: JSON.stringify({ expectedStateVersion: version }) }),
  retry: (operator: string, version: number) => request<State>("/control/retry-feed", { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version }) }),
  estop: (operator: string) => request<State>("/control/estop", { method: "POST", body: JSON.stringify({ operator }) }),
  enter: (mode: "manual" | "maintenance", operator: string, version: number) => request<State>(`/${mode}/enter`, { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version }) }),
  exit: (version: number) => request<State>("/control/exit", { method: "POST", body: JSON.stringify({ expectedStateVersion: version }) }),
  command: (scope: "manual" | "maintenance", operator: string, version: number, command: string, parameters: Record<string, unknown> = {}) => request<any>(`/${scope}/command`, { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version, command, parameters }) }),
  sensorCaptureCsv,
  configuration: () => request<ConfigurationPayload>("/configuration"),
  saveConfiguration: (operator: string, version: number, values: Record<string, any>) => request<ConfigurationPayload>("/configuration/save", { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version, description: "Dashboard configuration update", values }) }),
  resetConfiguration: (operator: string, version: number, source = "reset_values") => request<ConfigurationPayload>("/configuration/reset", { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version, source }) }),
  history: () => request<any>("/history?limit=100"),
};
