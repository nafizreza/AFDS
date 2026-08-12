import { useEffect, useState } from "react";
import { api } from "../api";
import { Panel, StatusPill } from "../components";
import type { PageProps } from "../App";
import type { ConfigurationPayload } from "../types";

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

export function MaintenancePage({ state, operator, run }: PageProps) {
  const [configuration, setConfiguration] = useState<ConfigurationPayload | null>(null);
  const [draft, setDraft] = useState<Record<string, any> | null>(null);
  const [saved, setSaved] = useState("");
  const [testResult, setTestResult] = useState("No component test run in this maintenance session.");
  const owned = state.state === "MAINTENANCE";
  const load = async () => { const value = await api.configuration(); setConfiguration(value); setDraft(clone(value.active)); };
  useEffect(() => { load().catch(() => undefined); }, []);
  const set = (path: string, value: number) => setDraft((current) => { if (!current) return current; const next = clone(current); const keys = path.split("."); let target = next; keys.slice(0, -1).forEach((key) => target = target[key]); target[keys.at(-1)!] = value; return next; });
  const field = (label: string, path: string, min: number, max: number, step = 1) => {
    const value = path.split(".").reduce((item, key) => item?.[key], draft as any);
    return <label className="config-field"><span>{label}</span><input type="number" value={value ?? ""} min={min} max={max} step={step} onChange={(e) => set(path, Number(e.target.value))}/><small>{min}–{max}</small></label>;
  };
  const save = async () => { if (!draft) return; const result = await run(() => api.saveConfiguration(operator, state.stateVersion, draft)); setConfiguration(result); setDraft(clone(result.active)); setSaved("Configuration saved as a new active version."); };
  const reset = async (source: string) => { if (!confirm(`Reset the active configuration from ${source}?`)) return; const result = await run(() => api.resetConfiguration(operator, state.stateVersion, source)); setConfiguration(result); setDraft(clone(result.active)); setSaved(`Configuration reset from ${source}.`); };
  const test = async (command: string, parameters: Record<string, unknown> = {}) => {
    setTestResult(`Running ${command.replaceAll("_", " ")}…`);
    await run(() => api.command("maintenance", operator, state.stateVersion, command, parameters));
    setTestResult(`${command.replaceAll("_", " ")} completed and was recorded in the audit log.`);
  };
  return <div className="page">
    <div className="page-title"><div><div className="eyebrow">MAINTENANCE & CALIBRATION</div><h1>Change values with a paper trail.</h1><p>Validate commissioning parameters, test each component and restore the approved JSON baseline.</p></div><StatusPill tone={owned ? "good" : "neutral"}>{owned ? "Maintenance lock active" : "Maintenance lock inactive"}</StatusPill></div>
    <div className="mode-banner"><div><strong>Exclusive maintenance lock</strong><p>An active inspection session blocks entry. Physical commands require a connected ESP32; configuration remains reviewable offline.</p></div><div>{!owned ? <button className="primary" disabled={!state.controls.enterMaintenance} onClick={() => run(() => api.enter("maintenance", operator, state.stateVersion))}>Enter maintenance</button> : <button className="warning" onClick={() => run(() => api.exit(state.stateVersion))}>Safe state & exit</button>}</div></div>
    {!draft ? <div className="loading">Loading configuration…</div> : <>
      <div className="config-toolbar"><div><strong>{draft.configurationVersion}</strong><span>Threshold profile: {configuration?.thresholds.profileVersion}</span></div><div><button onClick={() => setDraft(clone(configuration!.active))}>Discard changes</button><button className="warning" disabled={!owned} onClick={() => reset("reset_values")}>Reset to saved JSON</button><button className="danger-outline" disabled={!owned} onClick={() => reset("factory")}>Factory defaults</button><button className="success" disabled={!owned} onClick={save}>Save active version</button></div></div>
      {saved && <div className="success-note">{saved}</div>}
      <div className="config-grid">
        <Panel title="Vision and presence" kicker="CAMERA / YOLO26"><div className="fields">{field("Confidence threshold", "vision.confidenceThreshold", .05, .99, .01)}{field("Stable frames", "vision.stableFrames", 1, 60)}{field("Presence timeout (s)", "vision.presenceTimeoutSeconds", 2, 300)}{field("Stream FPS", "vision.streamFps", 1, 30)}{field("Minimum box area", "vision.minimumBoxAreaFraction", .001, .9, .001)}</div></Panel>
        <Panel title="Inlet valve" kicker="SG90 · GPIO 32"><div className="fields">{field("Open angle", "servos.inletValve.openAngle", 0, 180)}{field("Closed angle", "servos.inletValve.closedAngle", 0, 180)}{field("Settle time (ms)", "servos.inletValve.settleMs", 100, 10000)}</div></Panel>
        <Panel title="Feeder" kicker="NEMA 17 / DRV8825"><div className="fields">{field("Forward steps", "feeder.stepsForward", 1, 50000)}{field("Reverse steps", "feeder.stepsReverse", 1, 50000)}{field("Step rate", "feeder.stepRate", 10, 5000)}{field("Settle time (ms)", "feeder.settleMs", 0, 10000)}{field("Timeout (s)", "feeder.completionTimeoutSeconds", 1, 120)}</div></Panel>
        <Panel title="Sorting flaps" kicker="MG996R SERVOS"><div className="split-fields"><div><h4>Safe flap</h4>{field("Home angle", "servos.safeFlap.homeAngle", 0, 180)}{field("Drop angle", "servos.safeFlap.dropAngle", 0, 180)}{field("Hold (ms)", "servos.safeFlap.holdMs", 0, 10000)}</div><div><h4>Unsafe flap</h4>{field("Home angle", "servos.unsafeFlap.homeAngle", 0, 180)}{field("Drop angle", "servos.unsafeFlap.dropAngle", 0, 180)}{field("Hold (ms)", "servos.unsafeFlap.holdMs", 0, 10000)}</div></div></Panel>
        <Panel title="Sensor acquisition" kicker="STREAM CONTRACT"><div className="fields">{field("Duration (s)", "sampling.durationSeconds", 5, 900)}{field("Target rate (Hz)", "sampling.targetRateHz", .2, 20, .1)}{field("Maximum gap (s)", "sampling.maximumGapSeconds", .1, 30, .1)}{field("Minimum sample fraction", "sampling.minimumSampleFraction", .1, 1, .01)}</div></Panel>
        <Panel title="Chamber purge" kicker="VACUUM PUMP"><div className="fields">{field("Purge duration (s)", "purge.durationSeconds", 5, 600)}{field("Maximum duration (s)", "purge.maximumSeconds", 10, 900)}</div></Panel>
      </div>
      <Panel title="Component verification bench" kicker="GUARDED MANUAL TESTS" action={<StatusPill tone={owned ? "good" : "neutral"}>{owned ? "Controls enabled" : "Lock required"}</StatusPill>}>
        <p className="bench-intro">Use short, bounded motions while observing the physical mechanism. Each button sends a real hardware command; no simulated response is available.</p>
        <div className="test-bench">
          <button disabled={!owned} onClick={() => test("VALVE_OPEN")}>Open inlet</button>
          <button disabled={!owned} onClick={() => test("VALVE_CLOSE")}>Close inlet</button>
          <button disabled={!owned} onClick={() => test("STEPPER_MOVE", { direction: "FORWARD", steps: 100, stepRate: 300 })}>Jog feeder 100</button>
          <button disabled={!owned} onClick={() => test("SAFE_FLAP_TEST", { angle: draft.servos.safeFlap.dropAngle, holdMs: 900, homeAngle: draft.servos.safeFlap.homeAngle })}>Test safe flap</button>
          <button disabled={!owned} onClick={() => test("UNSAFE_FLAP_TEST", { angle: draft.servos.unsafeFlap.dropAngle, holdMs: 900, homeAngle: draft.servos.unsafeFlap.homeAngle })}>Test unsafe flap</button>
          <button disabled={!owned} onClick={() => test("PURGE_TIMED", { durationSeconds: 5, maximumSeconds: 10 })}>Pump 5 seconds</button>
          <button disabled={!owned} onClick={() => test("SENSOR_SNAPSHOT")}>Sensor snapshot</button>
          <button disabled={!owned || !state.vision.ready} onClick={() => test("CAMERA_DETECT")}>YOLO capture</button>
          <button className="danger-outline" disabled={!owned} onClick={() => test("SET_SAFE_STATE", { closeValve: true, homeFlaps: true })}>Apply safe state</button>
        </div>
        <div className="bench-result">{testResult}</div>
      </Panel>
      <Panel title="GPIO and commissioning status" kicker="HARDWARE MAP"><div className="pin-grid">{Object.entries(configuration?.pins || {}).filter(([key]) => key !== "schemaVersion").map(([key, value]) => <div key={key}><span>{key}</span><strong>{String(value)}</strong></div>)}</div><div className="notice warning-notice">Home and far limit pins are unset. Automatic lead-screw homing stays blocked.</div></Panel>
    </>}
  </div>;
}
