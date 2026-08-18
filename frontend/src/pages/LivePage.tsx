import { ClassificationCard, GasSensorChartStack, Metric, Panel, SensorStrip, StatusPill } from "../components";
import type { PageProps } from "../App";

export function LivePage({ state, samples }: PageProps) {
  const latest = samples.at(-1) || state.hardware.latestSensorSample;
  const detection = state.lastDetection || state.vision.latestDetection;
  return <div className="page">
    <div className="page-title"><div><div className="eyebrow"><span className="live-dot" /> LIVE MONITORING</div><h1>See what the system sees.</h1><p>Camera detections, sensor response and screening evidence stay synchronized to the active fruit.</p></div><StatusPill tone={state.vision.ready ? "good" : "danger"}>{state.vision.ready ? "Vision ready" : "Vision offline"}</StatusPill></div>
    <div className="live-grid">
      <Panel title="Chamber camera" kicker="YOLO26 OBJECT DETECTION" className="camera-panel" action={<span className="fps">{detection?.latencyMs ? `${detection.latencyMs} ms` : "— ms"}</span>}>
        <div className="camera-frame"><img src="/api/v1/camera/stream" alt="Live chamber feed with YOLO bounding boxes"/><div className="camera-corners"/><div className="camera-overlay"><span>ROI ACTIVE</span><strong>{detection?.selected?.fruitClass || detection?.detections?.[0]?.fruitClass || "Waiting for fruit"}</strong><small>{detection?.selected?.confidence ? `${(detection.selected.confidence * 100).toFixed(1)}% confidence` : "Stable detection required"}</small></div></div>
        <div className="camera-stats"><Metric label="Objects" value={detection?.count ?? 0}/><Metric label="Frame" value={detection?.frameSequence ?? "—"}/><Metric label="Model" value="YOLO26s"/><Metric label="Stable target" value={detection?.selected ? "YES" : "NO"} tone={detection?.selected ? "green" : ""}/></div>
      </Panel>
      <Panel title="Current result" kicker="DECISION EVIDENCE"><ClassificationCard result={state.lastClassification}/></Panel>
    </div>
    <Panel title="Live sensor acquisition" kicker={`${samples.length} VALUES IN VIEW`} action={<StatusPill tone={state.state === "ACQUIRING" ? "good" : "neutral"}>{state.state === "ACQUIRING" ? "Sampling" : "Standby"}</StatusPill>}>
      <SensorStrip sample={state.hardware.latestSensorSample}/>
      <div className="chart gas-chart-shell"><GasSensorChartStack samples={samples} latest={latest}/></div>
    </Panel>
  </div>;
}
