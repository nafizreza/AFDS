import { useEffect, useState } from "react";
import { api } from "../api";
import { Panel, StatusPill } from "../components";
import type { PageProps } from "../App";
import type { ConfigurationPayload } from "../types";

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const withSortingMotionDefaults = (value: Record<string, any>) => {
  const next = clone(value);
  next.servos ||= {};
  next.servos.sortingMotion ||= {};
  next.servos.sortingMotion.offsetDegrees ??= 10;
  next.servos.sortingMotion.intervalMs ??= 90;
  next.servos.sortingMotion.cycles ??= 4;
  return next;
};

export function MaintenancePage({ state, operator, run }: PageProps) {
  const [configuration, setConfiguration] = useState<ConfigurationPayload | null>(null);
  const [draft, setDraft] = useState<Record<string, any> | null>(null);
  const [saved, setSaved] = useState("");
  const [testResult, setTestResult] = useState("No component test run in this maintenance session.");
  const [stepperTestSteps, setStepperTestSteps] = useState(100);
  const [stepperTestRate, setStepperTestRate] = useState(300);
  const owned = state.state === "MAINTENANCE";
  const stepperTestValid = Number.isFinite(stepperTestSteps) && stepperTestSteps >= 1 && stepperTestSteps <= 50000
    && Number.isFinite(stepperTestRate) && stepperTestRate >= 10 && stepperTestRate <= 5000;
  const load = async () => { const value = await api.configuration(); setConfiguration(value); setDraft(withSortingMotionDefaults(value.active)); };
  useEffect(() => { load().catch(() => undefined); }, []);
  const set = (path: string, value: number) => setDraft((current) => { if (!current) return current; const next = clone(current); const keys = path.split("."); let target = next; keys.slice(0, -1).forEach((key) => target = target[key]); target[keys.at(-1)!] = value; return next; });
  const field = (label: string, path: string, min: number, max: number, step = 1) => {
    const value = path.split(".").reduce((item, key) => item?.[key], draft as any);
    return <label className="config-field"><span>{label}</span><input type="number" value={value ?? ""} min={min} max={max} step={step} onChange={(e) => set(path, Number(e.target.value))}/><small>{min}–{max}</small></label>;
  };
  const save = async () => { if (!draft) return; const result = await run(() => api.saveConfiguration(operator, state.stateVersion, draft)); setConfiguration(result); setDraft(withSortingMotionDefaults(result.active)); setSaved("Configuration saved as a new active version."); };
  const reset = async (source: string) => { if (!confirm(`Reset the active configuration from ${source}?`)) return; const result = await run(() => api.resetConfiguration(operator, state.stateVersion, source)); setConfiguration(result); setDraft(withSortingMotionDefaults(result.active)); setSaved(`Configuration reset from ${source}.`); };
  const test = async (command: string, parameters: Record<string, unknown> = {}) => {
    setTestResult(`Running ${command.replaceAll("_", " ")}…`);
    await run(() => api.command("maintenance", operator, state.stateVersion, command, parameters));
    setTestResult(`${command.replaceAll("_", " ")} completed and was recorded in the audit log.`);
  };
  return <div className="page">
    <div className="page-title"><div><div className="eyebrow">MAINTENANCE & CALIBRATION</div><h1>Change values with a paper trail.</h1><p>Validate commissioning parameters, test each component and restore the approved JSON baseline.</p></div><StatusPill tone={owned ? "good" : "neutral"}>{owned ? "Maintenance lock active" : "Maintenance lock inactive"}</StatusPill></div>
    <div className="mode-banner"><div><strong>Exclusive maintenance lock</strong><p>An active inspection session blocks entry. Physical commands require a connected ESP32; configuration remains reviewable offline.</p></div><div>{!owned ? <button className="primary" disabled={!state.controls.enterMaintenance} onClick={() => run(() => api.enter("maintenance", operator, state.stateVersion))}>Enter maintenance</button> : <button className="warning" onClick={() => run(() => api.exit(state.stateVersion))}>Safe state & exit</button>}</div></div>
    {!draft ? <div className="loading">Loading configuration…</div> : <>
      <div className="config-toolbar"><div><strong>{draft.configurationVersion}</strong><span>Threshold profile: {configuration?.thresholds.profileVersion}</span></div><div><button onClick={() => setDraft(withSortingMotionDefaults(configuration!.active))}>Discard changes</button><button className="warning" disabled={!owned} onClick={() => reset("reset_values")}>Reset to saved JSON</button><button className="danger-outline" disabled={!owned} onClick={() => reset("factory")}>Factory defaults</button><button className="success" disabled={!owned} onClick={save}>Save active version</button></div></div>
      {saved && <div className="success-note">{saved}</div>}
      <div className="config-grid">
        <Panel title="Vision and presence" kicker="CAMERA / YOLO26"><div className="fields">{field("Confidence threshold", "vision.confidenceThreshold", .05, .99, .01)}{field("Stable frames", "vision.stableFrames", 1, 60)}{field("Presence timeout (s)", "vision.presenceTimeoutSeconds", 2, 300)}{field("Stream FPS", "vision.streamFps", 1, 30)}{field("Minimum box area", "vision.minimumBoxAreaFraction", .001, .9, .001)}</div></Panel>
        <Panel title="Inlet valve" kicker="SG90 · GPIO 32"><div className="fields">{field("Open angle", "servos.inletValve.openAngle", 0, 180)}{field("Closed angle", "servos.inletValve.closedAngle", 0, 180)}{field("Settle time (ms)", "servos.inletValve.settleMs", 100, 10000)}</div></Panel>
        <Panel title="Feeder" kicker="NEMA 17 / DRV8825"><div className="fields">{field("Forward steps", "feeder.stepsForward", 1, 50000)}{field("Reverse steps", "feeder.stepsReverse", 1, 50000)}{field("Step rate", "feeder.stepRate", 10, 5000)}{field("Settle time (ms)", "feeder.settleMs", 0, 10000)}{field("Timeout (s)", "feeder.completionTimeoutSeconds", 1, 120)}</div></Panel>
        <Panel title="Sorting flaps" kicker="MG996R SERVOS"><div className="split-fields"><div><h4>Safe flap</h4>{field("Home angle", "servos.safeFlap.homeAngle", 0, 180)}{field("Drop angle", "servos.safeFlap.dropAngle", 0, 180)}{field("Hold (ms)", "servos.safeFlap.holdMs", 0, 10000)}</div><div><h4>Unsafe flap</h4>{field("Home angle", "servos.unsafeFlap.homeAngle", 0, 180)}{field("Drop angle", "servos.unsafeFlap.dropAngle", 0, 180)}{field("Hold (ms)", "servos.unsafeFlap.holdMs", 0, 10000)}</div></div><div className="fields">{field("Oscillation angle difference (°)", "servos.sortingMotion.offsetDegrees", 1, 45)}{field("Oscillation interval (ms)", "servos.sortingMotion.intervalMs", 20, 1000)}{field("Number of oscillations", "servos.sortingMotion.cycles", 1, 10)}</div></Panel>
        <Panel title="Sensor acquisition" kicker="STREAM CONTRACT"><div className="fields">{field("Duration (s)", "sampling.durationSeconds", 5, 900)}{field("Target rate (Hz)", "sampling.targetRateHz", .2, 20, .1)}{field("Maximum gap (s)", "sampling.maximumGapSeconds", .1, 30, .1)}{field("Minimum sample fraction", "sampling.minimumSampleFraction", .1, 1, .01)}</div></Panel>
        <Panel title="Chamber purge" kicker="VACUUM PUMP"><div className="fields">{field("Purge duration (s)", "purge.durationSeconds", 5, 600)}{field("Maximum duration (s)", "purge.maximumSeconds", 10, 900)}</div></Panel>
      </div>
      <Panel title="Component verification bench" kicker="GUARDED MANUAL TESTS" action={<StatusPill tone={owned ? "good" : "neutral"}>{owned ? "Controls enabled" : "Lock required"}</StatusPill>}>
        <p className="bench-intro">Tests use the values currently displayed above. Save them first to make the same values active for automatic operation. Each button sends a real hardware command; no simulated response is available.</p>
        <section className="stepper-test-control" aria-labelledby="stepper-test-title">
          <div className="stepper-test-heading">
            <div><span>LEAD-SCREW POSITIONING</span><h3 id="stepper-test-title">Stepper motor test</h3><p>Directional moves run once and stop. The complete cycle uses the feeder configuration displayed above.</p></div>
            <StatusPill tone={owned ? "good" : "neutral"}>{state.hardware.outputs.stepper || "UNKNOWN"}</StatusPill>
          </div>
          <div className="stepper-test-settings">
            <label><span>Test steps</span><input type="number" value={stepperTestSteps} min={1} max={50000} onChange={(event) => setStepperTestSteps(Number(event.target.value))}/><small>Movement distance · 1–50,000</small></label>
            <label><span>Test speed</span><input type="number" value={stepperTestRate} min={10} max={5000} onChange={(event) => setStepperTestRate(Number(event.target.value))}/><small>Steps per second · 10–5,000</small></label>
          </div>
          <div className="stepper-test-actions">
            <button disabled={!owned || !stepperTestValid} onClick={() => test("STEPPER_MOVE", { direction: "FORWARD", steps: stepperTestSteps, stepRate: stepperTestRate })}><span>Move forward</span><small>{stepperTestSteps} steps · {stepperTestRate}/s</small></button>
            <button disabled={!owned || !stepperTestValid} onClick={() => test("STEPPER_MOVE", { direction: "REVERSE", steps: stepperTestSteps, stepRate: stepperTestRate })}><span>Move reverse</span><small>{stepperTestSteps} steps · {stepperTestRate}/s</small></button>
            <button disabled={!owned} onClick={() => test("FEED_ONE", draft.feeder)}><span>Test complete feed cycle</span><small>{draft.feeder.stepsForward} forward · {draft.feeder.stepsReverse} return</small></button>
            <button className="danger-outline" disabled={!owned} onClick={() => test("STEPPER_DISABLE")}><span>Stop / disable</span><small>Remove motor holding power</small></button>
          </div>
        </section>
        <div className="test-bench">
          <button disabled={!owned} onClick={() => test("VALVE_OPEN", { angle: draft.servos.inletValve.openAngle, settleMs: draft.servos.inletValve.settleMs })}>Open inlet · {draft.servos.inletValve.openAngle}°</button>
          <button disabled={!owned} onClick={() => test("VALVE_CLOSE", { angle: draft.servos.inletValve.closedAngle, settleMs: draft.servos.inletValve.settleMs })}>Close inlet · {draft.servos.inletValve.closedAngle}°</button>
          <button disabled={!owned} onClick={() => test("SAFE_FLAP_TEST", { angle: draft.servos.safeFlap.dropAngle, holdMs: draft.servos.safeFlap.holdMs, homeAngle: draft.servos.safeFlap.homeAngle, settleMs: draft.servos.safeFlap.settleMs })}>Test safe flap cycle · {draft.servos.safeFlap.dropAngle}° → {draft.servos.safeFlap.homeAngle}°</button>
          <button disabled={!owned} onClick={() => test("UNSAFE_FLAP_TEST", { angle: draft.servos.unsafeFlap.dropAngle, holdMs: draft.servos.unsafeFlap.holdMs, homeAngle: draft.servos.unsafeFlap.homeAngle, settleMs: draft.servos.unsafeFlap.settleMs })}>Test reject flap cycle · {draft.servos.unsafeFlap.dropAngle}° → {draft.servos.unsafeFlap.homeAngle}°</button>
          <button disabled={!owned} onClick={() => test("SORT_SAFE", { angle: draft.servos.safeFlap.dropAngle, homeAngle: draft.servos.safeFlap.homeAngle, oppositeHomeAngle: draft.servos.unsafeFlap.homeAngle, holdMs: draft.servos.safeFlap.holdMs, settleMs: draft.servos.safeFlap.settleMs, shakeOffsetDegrees: draft.servos.sortingMotion.offsetDegrees, shakeCycles: draft.servos.sortingMotion.cycles, shakeStepMs: draft.servos.sortingMotion.intervalMs })}>Sorting Safe Flap · safe fixed at {draft.servos.safeFlap.dropAngle}° + unsafe {draft.servos.unsafeFlap.homeAngle}°↔{Math.min(180, draft.servos.unsafeFlap.homeAngle + draft.servos.sortingMotion.offsetDegrees)}° · {draft.servos.sortingMotion.cycles}× / {draft.servos.sortingMotion.intervalMs} ms</button>
          <button disabled={!owned} onClick={() => test("SORT_UNSAFE", { angle: draft.servos.unsafeFlap.dropAngle, homeAngle: draft.servos.unsafeFlap.homeAngle, oppositeHomeAngle: draft.servos.safeFlap.homeAngle, holdMs: draft.servos.unsafeFlap.holdMs, settleMs: draft.servos.unsafeFlap.settleMs, shakeOffsetDegrees: draft.servos.sortingMotion.offsetDegrees, shakeCycles: draft.servos.sortingMotion.cycles, shakeStepMs: draft.servos.sortingMotion.intervalMs })}>Sorting Unsafe Flap · unsafe fixed at {draft.servos.unsafeFlap.dropAngle}° + safe {draft.servos.safeFlap.homeAngle}°↔{Math.min(180, draft.servos.safeFlap.homeAngle + draft.servos.sortingMotion.offsetDegrees)}° · {draft.servos.sortingMotion.cycles}× / {draft.servos.sortingMotion.intervalMs} ms</button>
          <button disabled={!owned} onClick={() => test("PURGE_TIMED", { durationSeconds: 5, maximumSeconds: 10 })}>Pump 5 seconds</button>
          <button disabled={!owned} onClick={() => test("SENSOR_SNAPSHOT")}>Sensor snapshot</button>
          <button disabled={!owned || !state.vision.ready} onClick={() => test("CAMERA_DETECT")}>YOLO capture</button>
          <button className="danger-outline" disabled={!owned} onClick={() => test("SET_SAFE_STATE", { closeValve: true, homeFlaps: true, valveClosedAngle: draft.servos.inletValve.closedAngle, safeHomeAngle: draft.servos.safeFlap.homeAngle, unsafeHomeAngle: draft.servos.unsafeFlap.homeAngle })}>Apply configured safe state</button>
        </div>
        <div className="bench-result">{testResult}</div>
      </Panel>
      <Panel title="GPIO and commissioning status" kicker="HARDWARE MAP"><div className="pin-grid">{Object.entries(configuration?.pins || {}).filter(([key]) => key !== "schemaVersion").map(([key, value]) => <div key={key}><span>{key}</span><strong>{String(value)}</strong></div>)}</div><div className="notice warning-notice">Home and far limit pins are unset. Automatic lead-screw homing stays blocked.</div></Panel>
    </>}
  </div>;
}
