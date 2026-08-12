import { ClassificationCard, Metric, Panel, SensorStrip, StatusPill } from "../components";
import type { PageProps } from "../App";

function line(values: number[], width = 620, height = 160) {
  if (values.length < 2) return "";
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  return values.map((value, index) => `${index ? "L" : "M"} ${(index / (values.length - 1)) * width} ${height - ((value - min) / range) * (height - 12) - 6}`).join(" ");
}

function numeric(sample: any, key: string): number {
  const raw = sample?.[key]; return typeof raw === "object" ? Number(raw.value || 0) : Number(raw || 0);
}

export function LivePage({ state, samples }: PageProps) {
  const mq3 = samples.map((item) => numeric(item, "mq3"));
  const mq136 = samples.map((item) => numeric(item, "mq136"));
  const ch2o = samples.map((item) => numeric(item, "ch2o"));
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
      <div className="chart"><svg viewBox="0 0 620 160" preserveAspectRatio="none" role="img" aria-label="Live sensor chart"><path className="gridline" d="M0 40H620M0 80H620M0 120H620"/><path className="line mq3" d={line(mq3)}/><path className="line mq136" d={line(mq136)}/><path className="line ch2o" d={line(ch2o)}/></svg><div className="chart-legend"><span className="mq3">MQ-3</span><span className="mq136">MQ-136</span><span className="ch2o">CH₂O</span></div></div>
    </Panel>
  </div>;
}

