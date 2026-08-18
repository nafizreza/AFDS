export type State = {
  state: string;
  stateEnteredAt?: string;
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
    timings?: {
      samplingSeconds: number;
      purgeSeconds: number;
    };
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
  snapshotUrl?: string;
};

export type EngineeredFeatures = {
  initial: number;
  peak: number;
  average: number;
  final: number;
  delta: number;
  slope: number;
  duration_seconds: number;
  sample_count: number;
};

export type Classification = {
  condition: string;
  route: string;
  fruit_type: string;
  valid: boolean;
  quality: string;
  commissioned: boolean;
  evidence: Record<string, { channel: string; raw_mean?: number; adjusted_mean: number; feature_score?: number; threshold: number; threshold_index_percent: number; matched: boolean }>;
  engineered_features?: Record<string, EngineeredFeatures>;
  overall_confidence_percent?: number;
  confidence_basis?: string;
  visionEvidence?: {
    layer: number;
    name: string;
    fruitClass: string;
    confidencePercent: number;
    frameSequence?: number;
    snapshotUrl?: string;
    demo: boolean;
  };
  demoFusion?: {
    mode: string;
    overallConfidencePercent: number;
    sensor: { layer: number; name: string; source: string; weightPercent: number; contributionPercent: number; demo: boolean };
    image: { layer: number; name: string; source: string; weightPercent: number; contributionPercent: number; predictedClass: string; snapshotUrl?: string | null; demo: boolean };
    formula: string;
  };
  reasons: string[];
  disclaimer: string;
};

export type EventMessage = { sequence: number; topic: string; timestamp?: string; payload: any };

export type ConfigurationPayload = { active: Record<string, any>; thresholds: Record<string, any>; pins: Record<string, any> };
