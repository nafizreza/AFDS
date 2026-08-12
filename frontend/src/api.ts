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
  configuration: () => request<ConfigurationPayload>("/configuration"),
  saveConfiguration: (operator: string, version: number, values: Record<string, any>) => request<ConfigurationPayload>("/configuration/save", { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version, description: "Dashboard configuration update", values }) }),
  resetConfiguration: (operator: string, version: number, source = "reset_values") => request<ConfigurationPayload>("/configuration/reset", { method: "POST", body: JSON.stringify({ operator, expectedStateVersion: version, source }) }),
  history: () => request<any>("/history?limit=100"),
};

