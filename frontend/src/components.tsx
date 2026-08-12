import type { ReactNode } from "react";
import type { Classification, SensorSample, State } from "./types";

export function StatusPill({ tone = "neutral", children }: { tone?: string; children: ReactNode }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function Panel({ title, kicker, action, children, className = "" }: { title: string; kicker?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>
    <div className="panel-head"><div>{kicker && <div className="eyebrow">{kicker}</div>}<h2>{title}</h2></div>{action}</div>
    {children}
  </section>;
}

export function Metric({ label, value, hint, tone = "" }: { label: string; value: ReactNode; hint?: string; tone?: string }) {
  return <div className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong>{hint && <small>{hint}</small>}</div>;
}

export const WORKFLOW = [
  ["OPENING_VALVE", "01", "Open valve", "SG90 moves to the configured inlet angle"],
  ["FEEDING", "02", "Feed fruit", "Lead screw pushes one fruit, returns, then disables"],
  ["CLOSING_VALVE", "03", "Seal chamber", "Inlet valve returns to its closed angle"],
  ["WAITING_FOR_FRUIT", "04", "Detect fruit", "YOLO26 confirms one stable fruit with a box"],
  ["ACQUIRING", "05", "Read sensors", "Timed MQ-3, MQ-136, CH2O, temperature and humidity stream"],
  ["CLASSIFYING", "06", "Classify", "rfalter.py validates data and applies fruit thresholds"],
  ["SORTING_SAFE", "07", "Route safe", "Fresh fruit opens the safe flap"],
  ["SORTING_UNSAFE", "07", "Route unsafe", "Other and inconclusive results open the reject flap"],
  ["PURGING", "08", "Purge chamber", "Vacuum pump clears residual gases"],
  ["CYCLE_COMPLETE", "09", "Cycle complete", "Evidence is saved and the next cycle can begin"],
];

const terminalIndex: Record<string, number> = {
  READY: -1, OPENING_VALVE: 0, FEEDING: 1, CLOSING_VALVE: 2, WAITING_FOR_FRUIT: 3,
  ACQUIRING: 4, CLASSIFYING: 5, SORTING_SAFE: 6, SORTING_UNSAFE: 7, PURGING: 8, CYCLE_COMPLETE: 9,
};

export function Workflow({ state }: { state: State }) {
  const current = terminalIndex[state.state] ?? -1;
  return <div className="workflow">
    {WORKFLOW.map(([key, number, title, detail], index) => {
      const active = key === state.state;
      const complete = current > index || (state.state === "SORTING_SAFE" && index === 7) || (state.state === "SORTING_UNSAFE" && index === 6);
      return <div className={`workflow-step ${active ? "active" : ""} ${complete ? "complete" : ""}`} key={key}>
        <div className="step-marker"><span>{complete ? "✓" : number}</span></div>
        <div><strong>{title}</strong><p>{detail}</p></div>
        {active && <span className="active-tag">ACTIVE</span>}
      </div>;
    })}
  </div>;
}

function value(sample: SensorSample | null | undefined, key: keyof SensorSample): number | null {
  const raw = sample?.[key];
  if (typeof raw === "number") return raw;
  if (raw && typeof raw === "object" && "value" in raw) return Number(raw.value);
  return null;
}

export function SensorStrip({ sample }: { sample?: SensorSample | null }) {
  const sensors: Array<[keyof SensorSample, string, string]> = [
    ["mq3", "MQ-3", "ADC"], ["mq136", "MQ-136", "ADC"], ["ch2o", "CH₂O", "sensor unit"],
    ["temperature", "Temperature", "°C"], ["humidity", "Humidity", "%RH"],
  ];
  return <div className="sensor-strip">{sensors.map(([key, label, unit]) => {
    const reading = value(sample, key);
    return <div className="sensor-tile" key={key}><span>{label}</span><strong>{reading === null ? "—" : reading.toFixed(key === "ch2o" ? 3 : 1)}</strong><small>{unit}</small><i style={{ width: `${reading === null ? 0 : Math.min(100, Math.abs(reading) / (key === "ch2o" ? .0025 : key === "temperature" ? .5 : 12))}%` }} /></div>;
  })}</div>;
}

export function ClassificationCard({ result }: { result?: Classification | null }) {
  if (!result) return <div className="empty-state"><span>◇</span><strong>Awaiting classification</strong><p>Sensor evidence and threshold indices will appear here.</p></div>;
  const safe = result.route === "SAFE";
  return <div className={`classification ${safe ? "safe" : "unsafe"}`}>
    <div className="classification-title"><div><span>Final screening result</span><h3>{result.condition.replaceAll("_", " ")}</h3></div><b>{result.route} ROUTE</b></div>
    <div className="risk-grid">{Object.entries(result.evidence || {}).map(([key, evidence]) => <div className="risk" key={key}><span>{key}</span><strong>{evidence.threshold_index_percent.toFixed(0)}%</strong><div><i style={{ width: `${evidence.threshold_index_percent}%` }} /></div><small>{evidence.adjusted_mean} / {evidence.threshold}</small></div>)}</div>
    <p className="notice">{result.disclaimer}</p>
  </div>;
}

export function Mechanism({ state }: { state: State }) {
  const active = state.state;
  const fruitMoving = ["OPENING_VALVE", "FEEDING", "CLOSING_VALVE"].includes(active);
  return <div className="mechanism" aria-label="Animated fruit inspection mechanism">
    <div className="reservoir"><span>RESERVOIR</span><i className={fruitMoving ? "fruit moving" : "fruit"} /></div>
    <div className={`valve ${active === "OPENING_VALVE" ? "on" : ""}`}><i /> <span>INLET</span></div>
    <div className={`feeder ${active === "FEEDING" ? "on" : ""}`}><i /><span>FEEDER</span></div>
    <div className={`chamber ${["WAITING_FOR_FRUIT", "ACQUIRING", "CLASSIFYING"].includes(active) ? "on" : ""}`}>
      <div className="camera-eye" /><span>TEST CHAMBER</span><div className="scan-line" />
      <div className="gas gas-one" /><div className="gas gas-two" /><div className="gas gas-three" />
    </div>
    <div className={`flap safe-flap ${active === "SORTING_SAFE" ? "on" : ""}`}><span>SAFE</span></div>
    <div className={`flap unsafe-flap ${active === "SORTING_UNSAFE" ? "on" : ""}`}><span>UNSAFE</span></div>
    <div className={`pump ${active === "PURGING" ? "on" : ""}`}><i /><span>PURGE</span></div>
  </div>;
}

