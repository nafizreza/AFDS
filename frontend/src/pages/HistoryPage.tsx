import { useEffect, useState } from "react";
import { api } from "../api";
import { Metric, Panel } from "../components";
import type { PageProps } from "../App";

export function HistoryPage(_: PageProps) {
  const [history, setHistory] = useState<any>({ sessions: [], cycles: [], events: [] });
  const [filter, setFilter] = useState("");
  const refresh = () => api.history().then(setHistory).catch(() => undefined);
  useEffect(() => { refresh(); }, []);
  const cycles = history.cycles.filter((item: any) => JSON.stringify(item).toLowerCase().includes(filter.toLowerCase()));
  return <div className="page">
    <div className="page-title"><div><div className="eyebrow">HISTORY & DIAGNOSTICS</div><h1>Evidence for every decision.</h1><p>Review fruit cycles, classifications, routes, interventions and device events.</p></div><button onClick={refresh}>Refresh history</button></div>
    <div className="metrics-row"><Metric label="Sessions" value={history.sessions.length}/><Metric label="Fruit cycles" value={history.cycles.length}/><Metric label="Events loaded" value={history.events.length}/><Metric label="Completed" value={history.cycles.filter((item: any) => item.status === "COMPLETED").length} tone="green"/></div>
    <Panel title="Fruit results" kicker="TRACEABLE CYCLE RECORDS" action={<input className="search" placeholder="Filter fruit, class or route" value={filter} onChange={(e) => setFilter(e.target.value)}/>}>
      <div className="table-wrap"><table><thead><tr><th>Fruit</th><th>Session</th><th>Species</th><th>Condition</th><th>Route</th><th>Status</th><th>Started</th></tr></thead><tbody>{cycles.map((item: any) => <tr key={item.id}><td className="mono">{item.id}</td><td className="mono">{item.sessionId}</td><td>{item.fruitType || "—"}</td><td>{item.condition?.replaceAll("_", " ") || "—"}</td><td><span className={`route ${item.route?.toLowerCase()}`}>{item.route || "—"}</span></td><td>{item.status}</td><td>{new Date(item.startedAt).toLocaleString()}</td></tr>)}{!cycles.length && <tr><td colSpan={7} className="empty-cell">No fruit records yet.</td></tr>}</tbody></table></div>
    </Panel>
    <div className="history-grid"><Panel title="Sessions" kicker="BATCH SUMMARY"><div className="compact-list">{history.sessions.map((item: any) => <div key={item.id}><span><strong>{item.id}</strong><small>{item.operator}</small></span><b>{item.status}</b></div>)}{!history.sessions.length && <p className="muted">No sessions yet.</p>}</div></Panel><Panel title="Audit timeline" kicker="LATEST EVENTS"><div className="audit-list">{history.events.slice(0, 30).map((item: any) => <div key={item.id}><time>{new Date(item.timestamp).toLocaleString()}</time><span className={`severity ${item.severity.toLowerCase()}`}>{item.severity}</span><strong>{item.topic.replaceAll("_", " ")}</strong><small>{item.actor}</small></div>)}{!history.events.length && <p className="muted">No audit events yet.</p>}</div></Panel></div>
  </div>;
}

