import { api } from "../api";
import { Metric, Panel, StatusPill } from "../components";
import type { PageProps } from "../App";
import type { Classification, SensorSample } from "../types";

const MAIN_STAGES = [
  { key: "feed", number: "01", label: "Feed fruit", caption: "Load and seal" },
  { key: "vision", number: "02", label: "Vision", caption: "YOLO26 detection" },
  { key: "sense", number: "03", label: "Analyze", caption: "Live gas response" },
  { key: "result", number: "04", label: "Decision", caption: "Classify and route" },
  { key: "recover", number: "05", label: "Recover", caption: "Purge chamber" },
] as const;

const FEED_STATES = ["OPENING_VALVE", "FEEDING", "CLOSING_VALVE"];

function mainStage(state: string) {
  if (FEED_STATES.includes(state)) return "feed";
  if (state === "WAITING_FOR_FRUIT" || state === "ATTENTION_REQUIRED") return "vision";
  if (state === "ACQUIRING") return "sense";
  if (["CLASSIFYING", "SORTING_SAFE", "SORTING_UNSAFE", "CYCLE_COMPLETE"].includes(state)) return "result";
  if (state === "PURGING") return "recover";
  return "idle";
}

function numeric(sample: SensorSample | null | undefined, key: keyof SensorSample): number | null {
  const raw = sample?.[key];
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (raw && typeof raw === "object" && "value" in raw) return Number(raw.value);
  return null;
}

function signalPath(samples: SensorSample[], key: keyof SensorSample, width = 720, height = 210) {
  const values = samples.map((sample) => numeric(sample, key)).filter((value): value is number => value !== null);
  if (values.length < 2) return "";
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  return values.map((value, index) => `${index ? "L" : "M"} ${(index / (values.length - 1)) * width} ${height - 10 - ((value - min) / range) * (height - 20)}`).join(" ");
}

function TelemetryDeck({ sample, streaming }: { sample?: SensorSample | null; streaming: boolean }) {
  const sensors: Array<[keyof SensorSample, string, string, string]> = [
    ["mq3", "MQ-3", "ADC", "Alcohol / carbide response"],
    ["mq136", "MQ-136", "ADC", "Sulfur / spoilage response"],
    ["ch2o", "CH₂O", "ppm", "Formaldehyde channel"],
    ["temperature", "Temperature", "°C", "Chamber environment"],
    ["humidity", "Humidity", "%RH", "Chamber environment"],
  ];
  return <section className="telemetry-deck" aria-label="Live sensor telemetry">
    <div className="telemetry-title">
      <div><span className={`telemetry-pulse ${streaming ? "on" : ""}`} /><strong>Live chamber telemetry</strong></div>
      <small>{streaming ? "Streaming continuously" : "Starts after hardware initialization"}</small>
    </div>
    <div className="telemetry-cards">{sensors.map(([key, label, unit, hint]) => {
      const reading = numeric(sample, key);
      const precision = key === "ch2o" ? 3 : key === "temperature" || key === "humidity" ? 1 : 0;
      return <article className={`telemetry-card sensor-${String(key)}`} key={String(key)}>
        <div className="telemetry-card-top"><span>{label}</span><i /></div>
        <div className="telemetry-value"><strong>{reading === null ? "—" : reading.toFixed(precision)}</strong><em>{unit}</em></div>
        <small>{hint}</small>
        <div className="signal-bars"><b /><b /><b /><b /><b /></div>
      </article>;
    })}</div>
  </section>;
}

function CycleRail({ stage }: { stage: string }) {
  const activeIndex = MAIN_STAGES.findIndex((item) => item.key === stage);
  return <div className="cycle-rail">{MAIN_STAGES.map((item, index) => <div className={`cycle-rail-step ${index === activeIndex ? "active" : ""} ${activeIndex > index ? "done" : ""}`} key={item.key}>
    <span>{activeIndex > index ? "✓" : item.number}</span>
    <div><strong>{item.label}</strong><small>{item.caption}</small></div>
  </div>)}</div>;
}

function FeedExperience({ state }: { state: string }) {
  const active = Math.max(0, FEED_STATES.indexOf(state));
  const steps = [
    ["Open inlet", "Valve moves to the configured loading angle"],
    ["Advance one fruit", "Feeder completes a bounded forward and return motion"],
    ["Seal chamber", "Inlet closes before camera inspection begins"],
  ];
  return <div className={`feed-experience feed-position-${active}`}>
    <div className="feed-visual">
      <div className="feed-reservoir"><span>RESERVOIR</span><i /><i /><i /></div>
      <div className="feed-track"><div className="feed-runner" /><div className="feed-fruit-orb" /></div>
      <div className={`feed-gate ${active === 0 ? "open" : ""}`}><i /></div>
      <div className={`feed-chamber ${active === 2 ? "sealed" : ""}`}><span>TEST CHAMBER</span><b /></div>
    </div>
    <div className="feed-substeps">{steps.map(([title, detail], index) => <div className={`${index === active ? "active" : ""} ${index < active ? "done" : ""}`} key={title}><span>{index < active ? "✓" : `0${index + 1}`}</span><section><strong>{title}</strong><p>{detail}</p></section></div>)}</div>
  </div>;
}

function VisionExperience({ state, detection }: { state: string; detection: any }) {
  const target = detection?.selected || detection?.detections?.[0];
  return <div className="vision-experience">
    <div className="cycle-camera">
      <img src="/api/v1/camera/stream" alt="Live chamber camera with YOLO26 bounding boxes" />
      <div className="camera-scan" />
      <div className="camera-readout"><span>{state === "ATTENTION_REQUIRED" ? "NO STABLE TARGET" : "LIVE DETECTION"}</span><strong>{target?.fruitClass || "Searching chamber…"}</strong><small>{target?.confidence ? `${(target.confidence * 100).toFixed(1)}% confidence` : "YOLO26 is evaluating every frame"}</small></div>
      <div className="camera-frame-data"><span>OBJECTS {detection?.count ?? 0}</span><span>{detection?.latencyMs ? `${detection.latencyMs} MS` : "LIVE"}</span></div>
    </div>
    {state === "ATTENTION_REQUIRED" && <div className="inline-attention"><b>Feed path check required</b><span>No fruit was confirmed in time. Inspect the reservoir and feeder before retrying.</span></div>}
  </div>;
}

function SignalGraph({ samples }: { samples: SensorSample[] }) {
  const view = samples.slice(-60);
  const channels: Array<[keyof SensorSample, string]> = [["mq3", "MQ-3"], ["mq136", "MQ-136"], ["ch2o", "CH₂O"], ["temperature", "TEMP"], ["humidity", "HUMIDITY"]];
  return <div className="analysis-experience">
    <div className="analysis-copy"><span className="acquiring-orb" /><div><strong>Building the fruit signature</strong><p>Live responses are being captured as a clean timed evidence window for threshold screening.</p></div><b>{view.length}<small> samples in view</small></b></div>
    <div className="signal-chart">
      <div className="chart-grid" />
      <svg viewBox="0 0 720 210" preserveAspectRatio="none" role="img" aria-label="Live normalized sensor response graph">{channels.map(([key]) => <path key={String(key)} className={`signal-line line-${String(key)}`} d={signalPath(view, key)} />)}</svg>
      <div className="signal-chart-footer"><div>{channels.map(([key, label]) => <span className={`legend-${String(key)}`} key={String(key)}>{label}</span>)}</div><small>RELATIVE TREND · LIVE</small></div>
    </div>
  </div>;
}

function DecisionExperience({ state, result }: { state: string; result?: Classification | null }) {
  if (state === "CLASSIFYING" || !result) return <div className="classifying-experience"><div className="decision-rings"><i /><i /><i /></div><span>COMPARING THRESHOLDS</span><h2>Turning sensor evidence into one clear route.</h2><p><code>rfalter.py</code> is validating sample quality and evaluating the commissioned threshold profile.</p></div>;
  const safe = result.route === "SAFE";
  return <div className={`decision-experience ${safe ? "safe" : "unsafe"}`}>
    <div className="decision-mark"><span>{safe ? "✓" : "!"}</span></div>
    <div className="decision-copy"><span>FINAL SCREENING DECISION</span><h2>{result.condition.replaceAll("_", " ")}</h2><p>{safe ? "Fruit cleared for the safe collection chamber." : "Fruit diverted to the unsafe collection chamber."}</p><div className="decision-route">{safe ? "SAFE TO EAT ROUTE" : "UNSAFE ROUTE"}</div></div>
    <div className="decision-evidence">{Object.entries(result.evidence || {}).map(([key, evidence]) => <div key={key}><span>{key}</span><strong>{evidence.threshold_index_percent.toFixed(0)}%</strong><i><b style={{ width: `${evidence.threshold_index_percent}%` }} /></i></div>)}</div>
  </div>;
}

function RecoveryExperience({ result }: { result?: Classification | null }) {
  return <div className="recovery-experience"><div className="purge-turbine"><i /><i /><i /></div><div><span>CHAMBER RECOVERY</span><h2>Clearing residual gases for the next fruit.</h2><p>The vacuum pump is running for the configured purge window. The next cycle starts automatically when recovery completes.</p>{result && <b className={result.route === "SAFE" ? "safe" : "unsafe"}>Previous fruit · {result.condition.replaceAll("_", " ")}</b>}</div></div>;
}

function IdleExperience({ state }: { state: string }) {
  const error = state === "ERROR" || state === "E_STOPPED" || state === "DISCONNECTED";
  return <div className={`idle-experience ${error ? "error" : ""}`}><div className="idle-core"><i /><span /></div><div><span>{error ? "SYSTEM CHECK" : "SYSTEM READY"}</span><h2>{state === "READY" ? "Ready for the next inspection." : state.replaceAll("_", " ")}</h2><p>{state === "READY" ? "Live telemetry is running. Start automatic operation when the reservoir and collection chambers are ready." : "Initialize hardware to verify the ESP32, camera, model and safe actuator positions."}</p></div></div>;
}

export function HomePage({ state, events, samples, operator, run }: PageProps) {
  const control = state.controls || {};
  const stage = mainStage(state.state);
  const latestSample = samples.at(-1) || state.hardware.latestSensorSample;
  const detection = state.lastDetection || state.vision.latestDetection;
  const resultState = ["SORTING_SAFE", "SORTING_UNSAFE", "CYCLE_COMPLETE"].includes(state.state);
  const resultTone = resultState && state.lastClassification?.route === "SAFE" ? "result-safe" : resultState && state.lastClassification ? "result-unsafe" : "";
  const stageName = MAIN_STAGES.find((item) => item.key === stage)?.label || "Standby";

  return <div className={`page overview-page immersive-overview ${state.state === "ACQUIRING" ? "sensor-active" : ""} ${resultTone}`}>
    <section className="overview-heading">
      <div><div className="eyebrow"><span className="live-dot" /> AUTOMATIC INSPECTION</div><h1>Fruit inspection, made visible.</h1><p>One live view of the chamber, signals and decision—without the engineering clutter.</p></div>
      <div className="overview-current"><span>NOW</span><strong>{stageName}</strong><small>{state.sessionId ? `Fruit ${state.cycleNumber} · automatic session` : "Awaiting an inspection session"}</small></div>
    </section>

    <TelemetryDeck sample={latestSample} streaming={Boolean(state.hardware.sensorStreaming)} />

    <section className="overview-controls">
      <div className="control-primary"><button className="primary" disabled={!control.initialize} onClick={() => run(() => api.initialize(operator, state.stateVersion))}>Initialize hardware</button><button className="success" disabled={!control.startAutomatic} onClick={() => run(() => api.start(operator, state.stateVersion))}>Start automatic cycle</button></div>
      <div className="control-session"><button disabled={!control.pause} onClick={() => run(() => api.action("pause", state.stateVersion))}>Pause</button><button disabled={!control.resume} onClick={() => run(() => api.action("resume", state.stateVersion))}>Resume</button><button className="warning" disabled={!control.stopAfterCurrent} onClick={() => run(() => api.action("stop-after-current", state.stateVersion))}>Stop after current</button>{control.retryFeed && <button className="warning pulse" onClick={() => run(() => api.retry(operator, state.stateVersion))}>Path clear · retry feed</button>}</div>
      <StatusPill tone={state.owner === "AUTOMATION" ? "good" : "neutral"}>{state.owner}</StatusPill>
    </section>

    <CycleRail stage={stage} />

    <section className={`cycle-stage stage-${stage}`}>
      <div className="cycle-stage-head"><div><span>{MAIN_STAGES.find((item) => item.key === stage)?.number || "—"}</span><section><small>ACTIVE CYCLE STAGE</small><strong>{stageName}</strong></section></div><div><b>{state.state.replaceAll("_", " ")}</b><small>{state.cycleId || "No fruit active"}</small></div></div>
      <div className="cycle-stage-body">
        {stage === "feed" && <FeedExperience state={state.state} />}
        {stage === "vision" && <VisionExperience state={state.state} detection={detection} />}
        {stage === "sense" && <SignalGraph samples={samples} />}
        {stage === "result" && <DecisionExperience state={state.state} result={state.lastClassification} />}
        {stage === "recover" && <RecoveryExperience result={state.lastClassification} />}
        {stage === "idle" && <IdleExperience state={state.state} />}
      </div>
    </section>

    <div className="overview-footer-grid">
      <div className="metrics-row overview-metrics"><Metric label="Attempted" value={state.summary.attempted || 0} hint="This session"/><Metric label="Safe" value={state.summary.fresh || 0} tone="green"/><Metric label="Unsafe" value={state.summary.unsafe || 0} tone="red"/><Metric label="Review" value={state.summary.inconclusive || 0} tone="amber"/></div>
      <Panel title="Latest system activity" kicker="LIVE EVENT STREAM" className="compact-events"><div className="event-list">{events.slice(0, 5).map((event) => <div key={`${event.sequence}-${event.topic}`}><time>{event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "now"}</time><i/><span>{event.topic.replaceAll("_", " ")}</span></div>)}{!events.length && <p className="muted">Activity will appear after the backend connects.</p>}</div></Panel>
    </div>
  </div>;
}
