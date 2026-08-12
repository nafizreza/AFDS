import { api } from "../api";
import { ClassificationCard, Mechanism, Metric, Panel, SensorStrip, StatusPill, Workflow } from "../components";
import type { PageProps } from "../App";

export function HomePage({ state, events, operator, run }: PageProps) {
  const control = state.controls || {};
  return <div className="page overview-page">
    <section className="hero">
      <div>
        <div className="eyebrow"><span className="live-dot" /> HARDWARE WORKFLOW</div>
        <h1>Every fruit. Every signal.<br/><em>One clear decision.</em></h1>
        <p>Watch the complete inspection mechanism move from feed to detection, threshold screening, sorting and chamber recovery.</p>
      </div>
      <div className="hero-status">
        <span>Current operation</span>
        <strong>{state.state.replaceAll("_", " ")}</strong>
        <small>{state.sessionId ? `${state.sessionId} · fruit ${state.cycleNumber}` : "No active inspection session"}</small>
      </div>
    </section>

    <section className="command-deck">
      <button className="primary" disabled={!control.initialize} onClick={() => run(() => api.initialize(operator, state.stateVersion))}><span>01</span>Initialize hardware</button>
      <button className="success" disabled={!control.startAutomatic} onClick={() => run(() => api.start(operator, state.stateVersion))}><span>02</span>Start automatic cycle</button>
      <button disabled={!control.pause} onClick={() => run(() => api.action("pause", state.stateVersion))}>Pause</button>
      <button disabled={!control.resume} onClick={() => run(() => api.action("resume", state.stateVersion))}>Resume</button>
      <button className="warning" disabled={!control.stopAfterCurrent} onClick={() => run(() => api.action("stop-after-current", state.stateVersion))}>Stop after current</button>
      {control.retryFeed && <button className="warning pulse" onClick={() => run(() => api.retry(operator, state.stateVersion))}>Inspected — retry feed</button>}
    </section>

    {state.state === "ATTENTION_REQUIRED" && <div className="attention"><div><b>!</b></div><section><strong>Manual inspection required</strong><p>No fruit was detected within the configured window. Check whether fruit is stuck in the reservoir or feeder. Retry only after the chamber and feed path are visibly safe.</p></section></div>}

    <div className="overview-grid">
      <Panel title="Live mechanism" kicker="DIGITAL PROCESS VIEW" className="mechanism-panel" action={<StatusPill tone={state.owner === "AUTOMATION" ? "good" : "neutral"}>{state.owner}</StatusPill>}>
        <Mechanism state={state} />
        <div className="mechanism-legend"><span><i className="legend-idle" /> Ready</span><span><i className="legend-active" /> Active</span><span><i className="legend-safe" /> Safe route</span><span><i className="legend-unsafe" /> Unsafe route</span></div>
      </Panel>
      <Panel title="Cycle sequence" kicker="AUTHORITATIVE STATE" className="workflow-panel"><Workflow state={state} /></Panel>
    </div>

    <div className="metrics-row">
      <Metric label="Attempted" value={state.summary.attempted || 0} hint="This session" />
      <Metric label="Safe" value={state.summary.fresh || 0} tone="green" hint="Fresh fruit" />
      <Metric label="Unsafe" value={state.summary.unsafe || 0} tone="red" hint="Rejected fruit" />
      <Metric label="Review" value={state.summary.inconclusive || 0} tone="amber" hint="Fail-safe route" />
    </div>

    <div className="detail-grid">
      <Panel title="Latest sensor signal" kicker="LIVE TELEMETRY"><SensorStrip sample={state.hardware.latestSensorSample} /></Panel>
      <Panel title="Latest decision" kicker="THRESHOLD SCREENING"><ClassificationCard result={state.lastClassification} /></Panel>
      <Panel title="Recent activity" kicker="EVENT STREAM" className="event-panel">
        <div className="event-list">{events.slice(0, 8).map((event) => <div key={`${event.sequence}-${event.topic}`}><time>{event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "now"}</time><i /><span>{event.topic.replaceAll("_", " ")}</span></div>)}{!events.length && <p className="muted">Events will appear when the backend connects.</p>}</div>
      </Panel>
    </div>
  </div>;
}

