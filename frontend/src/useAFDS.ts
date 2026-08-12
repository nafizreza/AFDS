import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { EventMessage, SensorSample, State } from "./types";

const EMPTY: State = {
  state: "CONNECTING",
  stateVersion: 0,
  owner: "NONE",
  cycleNumber: 0,
  stopAfterCurrent: false,
  hardware: { connected: false, port: "—", outputs: {} },
  vision: { ready: false, cameraReady: false, modelReady: false, modelPath: "—" },
  summary: { attempted: 0, fresh: 0, unsafe: 0, inconclusive: 0 },
  configuration: { checksum: "", thresholdsCommissioned: false },
  controls: {},
};

export function useAFDS() {
  const [state, setState] = useState<State>(EMPTY);
  const [online, setOnline] = useState(false);
  const [events, setEvents] = useState<EventMessage[]>([]);
  const [samples, setSamples] = useState<SensorSample[]>([]);
  const [error, setError] = useState<string | null>(null);
  const reconnect = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      setState(await api.state());
      setOnline(true);
      setError(null);
    } catch (reason) {
      setOnline(false);
      setError(reason instanceof Error ? reason.message : "Backend unavailable");
    }
  }, []);

  useEffect(() => {
    refresh();
    const connect = () => {
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      const host = location.port === "5173" ? `${location.hostname}:8000` : location.host;
      const socket = new WebSocket(`${protocol}://${host}/api/v1/ws`);
      socket.onopen = () => setOnline(true);
      socket.onmessage = (message) => {
        const event: EventMessage = JSON.parse(message.data);
        setEvents((previous) => [event, ...previous].slice(0, 150));
        if (event.topic === "state") setState(event.payload);
        if (event.topic === "sensor_sample") setSamples((previous) => [...previous.slice(-179), event.payload]);
      };
      socket.onclose = () => {
        void refresh();
        reconnect.current = window.setTimeout(connect, 1800);
      };
    };
    connect();
    const poll = window.setInterval(refresh, 12000);
    return () => { window.clearInterval(poll); if (reconnect.current) window.clearTimeout(reconnect.current); };
  }, [refresh]);

  const run = useCallback(async (operation: () => Promise<any>) => {
    try {
      const result = await operation();
      if (result?.stateVersion !== undefined) setState(result);
      if (result?.state?.stateVersion !== undefined) setState(result.state);
      setError(null);
      return result;
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Operation failed";
      setError(message);
      throw reason;
    }
  }, []);

  return { state, online, events, samples, error, setError, refresh, run };
}
