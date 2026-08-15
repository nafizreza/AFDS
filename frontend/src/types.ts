export type State = {
  state: string;
  stateVersion: number;
  owner: string;
  operator?: string | null;
  sessionId?: string | null;
  cycleId?: string | null;
  cycleNumber: number;
  stopAfterCurrent: boolean;
  lastError?: { code: string; message: string } | null;
  lastDetection?: Detection | null;
  lastClassification?: Classification | null;
  hardware: {
    connected: boolean;
    port: string;
    lastHeartbeatAgeSeconds?: number | null;
    latestSensorSample?: SensorSample | null;
    sensorStreaming?: boolean;
    sensorIntervalMs?: number | null;
    outputs: Record<string, string>;
  };
  vision: {
    ready: boolean;
    cameraReady: boolean;
    modelReady: boolean;
    modelPath: string;
    lastError?: string | null;
    latestDetection?: Detection | null;
  };
  summary: Record<string, number>;
  configuration: {
    version?: string;
    checksum: string;
    thresholdProfile?: string;
    thresholdsCommissioned: boolean;
  };
  controls: Record<string, boolean>;
};

export type SensorSample = {
  mq3?: number | { value: number };
  mq136?: number | { value: number };
  ch2o?: number | { value: number };
  temperature?: number | { value: number };
  humidity?: number | { value: number };
  elapsed?: number;
  deviceMillis?: number;
  sequence?: number;
};

export type Detection = {
  count: number;
  frameSequence: number;
  latencyMs: number;
  detections: Array<{ fruitClass: string; rawClass: string; confidence: number; boundingBox: Record<string, number> }>;
  selected?: { fruitClass: string; rawClass: string; confidence: number };
};

export type Classification = {
  condition: string;
  route: string;
  fruit_type: string;
  valid: boolean;
  quality: string;
  commissioned: boolean;
  evidence: Record<string, { channel: string; adjusted_mean: number; threshold: number; threshold_index_percent: number; matched: boolean }>;
  reasons: string[];
  disclaimer: string;
};

export type EventMessage = { sequence: number; topic: string; timestamp?: string; payload: any };

export type ConfigurationPayload = { active: Record<string, any>; thresholds: Record<string, any>; pins: Record<string, any> };
