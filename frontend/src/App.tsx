import { useEffect, useState } from "react";
import { api } from "./api";
import { StatusPill } from "./components";
import { HomePage } from "./pages/HomePage";
import { LivePage } from "./pages/LivePage";
import { ManualPage } from "./pages/ManualPage";
import { MaintenancePage } from "./pages/MaintenancePage";
import { HistoryPage } from "./pages/HistoryPage";
import { useAFDS } from "./useAFDS";

const routes = [
  ["/", "Overview"], ["/live", "Live monitor"], ["/manual", "Manual"], ["/maintenance", "Maintenance"], ["/history", "History"],
] as const;

export type PageProps = ReturnType<typeof useAFDS> & { operator: string };

export function App() {
  const afds = useAFDS();
  const [path, setPath] = useState(location.pathname);
  const [operator, setOperator] = useState(localStorage.getItem("afds.operator") || "operator");
  useEffect(() => { const handler = () => setPath(location.pathname); addEventListener("popstate", handler); return () => removeEventListener("popstate", handler); }, []);
  useEffect(() => localStorage.setItem("afds.operator", operator), [operator]);
  const navigate = (next: string) => { history.pushState({}, "", next); setPath(next); };
  const props = { ...afds, operator };

  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => navigate("/")}><span className="brand-mark">A</span><span><strong>AFDS</strong><small>Fruit inspection console</small></span></button>
      <nav aria-label="Primary navigation">{routes.map(([url, label]) => <button key={url} onClick={() => navigate(url)} className={path === url ? "active" : ""}>{label}</button>)}</nav>
      <div className="top-actions">
        <StatusPill tone={afds.online ? "good" : "danger"}>{afds.online ? "Backend online" : "Backend offline"}</StatusPill>
        <label className="operator"><span>Operator</span><input value={operator} onChange={(e) => setOperator(e.target.value)} /></label>
        <button className="estop-mini" onClick={() => { if (confirm("Send software safe-state commands now?")) afds.run(() => api.estop(operator)); }}>E-STOP</button>
      </div>
    </header>
    <div className="status-rail">
      <span><i className={afds.state.hardware.connected ? "ok" : "bad"} /> ESP32 {afds.state.hardware.connected ? "connected" : "disconnected"}</span>
      <span><i className={afds.state.vision.ready ? "ok" : "warn"} /> Vision {afds.state.vision.ready ? "ready" : "not ready"}</span>
      <span>State <b>{afds.state.state.replaceAll("_", " ")}</b></span>
      <span>Owner <b>{afds.state.owner}</b></span>
      <span>Cycle <b>{afds.state.cycleNumber || "—"}</b></span>
      <span className="rail-spacer" />
      <span>Config <b>{afds.state.configuration.version || "—"}</b></span>
    </div>
    {afds.error && <div className="error-banner" role="alert"><strong>Action blocked</strong><span>{afds.error}</span><button onClick={() => afds.setError(null)}>Dismiss</button></div>}
    <main>
      {path === "/" && <HomePage {...props} />}
      {path === "/live" && <LivePage {...props} />}
      {path === "/manual" && <ManualPage {...props} />}
      {path === "/maintenance" && <MaintenancePage {...props} />}
      {path === "/history" && <HistoryPage {...props} />}
      {!routes.some(([url]) => url === path) && <HomePage {...props} />}
    </main>
    <footer><span>AFDS 1.0 · Hardware runtime</span><span>Threshold screening prototype — not laboratory certification</span></footer>
  </div>;
}

