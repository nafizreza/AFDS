import { useState, type ReactNode } from "react";
import { api } from "../api";
import { Panel, StatusPill } from "../components";
import type { PageProps } from "../App";

type CommandCardProps = {
  title: string; description: string; state: string; children: ReactNode;
};
function CommandCard({ title, description, state, children }: CommandCardProps) {
  return <div className="component-card"><div className="component-head"><div><h3>{title}</h3><p>{description}</p></div><StatusPill>{state}</StatusPill></div>{children}</div>;
}

export function ManualPage({ state, operator, run }: PageProps) {
  const [steps, setSteps] = useState(200);
  const [rate, setRate] = useState(400);
  const [duration, setDuration] = useState(15);
  const owned = state.state === "MANUAL";
  const command = (name: string, parameters: Record<string, unknown> = {}) => run(() => api.command("manual", operator, state.stateVersion, name, parameters));
  return <div className="page">
    <div className="page-title"><div><div className="eyebrow">MANUAL OPERATION</div><h1>Direct control, guarded at every step.</h1><p>Operate one component at a time. The backend still enforces pump, motion and ownership interlocks.</p></div><StatusPill tone={owned ? "good" : "neutral"}>{owned ? "Manual control owned" : "Manual control inactive"}</StatusPill></div>
    <div className="mode-banner"><div><strong>{owned ? "Manual ownership is active" : "Claim manual ownership before testing components"}</strong><p>Automatic progression is disabled while manual control is held. Every action is timestamped.</p></div><div>{!owned ? <button className="primary" disabled={!state.controls.enterManual} onClick={() => run(() => api.enter("manual", operator, state.stateVersion))}>Enter manual mode</button> : <button className="warning" onClick={() => run(() => api.exit(state.stateVersion))}>Apply safe state & exit</button>}</div></div>
    <div className={`component-grid ${owned ? "" : "locked"}`}>
      <CommandCard title="Inlet valve" description="SG90 chamber gate on GPIO 32" state={state.hardware.outputs.inletValve || "UNKNOWN"}><div className="button-row"><button disabled={!owned} onClick={() => command("VALVE_OPEN")}>Open valve</button><button disabled={!owned} onClick={() => command("VALVE_CLOSE")}>Close valve</button></div></CommandCard>
      <CommandCard title="Feeder and lead screw" description="Bounded DRV8825 movement" state={state.hardware.outputs.stepper || "UNKNOWN"}><div className="field-pair"><label>Steps<input type="number" value={steps} min={1} max={20000} onChange={(e) => setSteps(Number(e.target.value))}/></label><label>Rate<input type="number" value={rate} min={10} max={2000} onChange={(e) => setRate(Number(e.target.value))}/></label></div><div className="button-row"><button disabled={!owned} onClick={() => command("STEPPER_MOVE", { direction: "FORWARD", steps, stepRate: rate })}>Jog forward</button><button disabled={!owned} onClick={() => command("STEPPER_MOVE", { direction: "REVERSE", steps, stepRate: rate })}>Jog reverse</button><button className="danger-outline" disabled={!owned} onClick={() => command("STEPPER_STOP")}>Stop</button></div></CommandCard>
      <CommandCard title="Safe sorting flap" description="Fresh-fruit collection route" state={state.hardware.outputs.safeFlap || "UNKNOWN"}><div className="button-row"><button disabled={!owned} onClick={() => command("SAFE_FLAP_TEST", { angle: 0, holdMs: 1200, settleMs: 500 })}>Test flap</button><button disabled={!owned} onClick={() => command("SAFE_FLAP_HOME", { angle: 60 })}>Return home</button></div></CommandCard>
      <CommandCard title="Unsafe sorting flap" description="Reject and fail-safe route" state={state.hardware.outputs.unsafeFlap || "UNKNOWN"}><div className="button-row"><button disabled={!owned} onClick={() => command("UNSAFE_FLAP_TEST", { angle: 0, holdMs: 1200, settleMs: 500 })}>Test flap</button><button disabled={!owned} onClick={() => command("UNSAFE_FLAP_HOME", { angle: 60 })}>Return home</button></div></CommandCard>
      <CommandCard title="Vacuum pump" description="Timed chamber gas purge" state={state.hardware.outputs.pump || "UNKNOWN"}><label>Auto-off seconds<input type="number" min={1} max={120} value={duration} onChange={(e) => setDuration(Number(e.target.value))}/></label><div className="button-row"><button disabled={!owned} onClick={() => command("PUMP_ON", { maximumSeconds: duration })}>Pump on</button><button className="danger-outline" disabled={!owned} onClick={() => command("PUMP_OFF")}>Pump off</button><button disabled={!owned} onClick={() => command("PURGE_TIMED", { durationSeconds: duration, maximumSeconds: duration + 5 })}>Timed purge</button></div></CommandCard>
      <CommandCard title="Sensors" description="Snapshot or controlled stream" state={state.state === "ACQUIRING" ? "STREAMING" : "STANDBY"}><div className="button-row"><button disabled={!owned} onClick={() => command("SENSOR_SNAPSHOT")}>Read snapshot</button><button disabled={!owned} onClick={() => command("SENSOR_STREAM_START", { intervalMs: 1000 })}>Start stream</button><button className="danger-outline" disabled={!owned} onClick={() => command("SENSOR_STREAM_STOP")}>Stop stream</button></div></CommandCard>
      <CommandCard title="Camera and YOLO26" description="Physical snapshot detection only" state={state.vision.ready ? "READY" : "OFFLINE"}><div className="button-row"><button disabled={!owned || !state.vision.ready} onClick={() => command("CAMERA_DETECT")}>Capture & detect</button></div></CommandCard>
      <CommandCard title="Whole-system safe state" description="Pump off, stepper disabled, valve closed, flaps home" state="ALWAYS AVAILABLE"><button className="danger-wide" disabled={!owned} onClick={() => { if (confirm("Apply the complete software safe state?")) command("SET_SAFE_STATE", { closeValve: true, homeFlaps: true }); }}>Apply safe state</button></CommandCard>
    </div>
    <Panel title="Important physical limits" kicker="OPERATOR AWARENESS"><div className="limit-list"><span>No stepper home switch is configured; automatic homing is blocked.</span><span>Servo and flap positions are commanded, not physically confirmed.</span><span>Software E-stop is not a mains power disconnect.</span><span>Never place hands in the mechanism while powered.</span></div></Panel>
  </div>;
}
