export type EvidenceStatus =
  | "observed"
  | "published_model"
  | "computed"
  | "assumed"
  | "illustrative"
  | "mock";

export interface EvidenceSource {
  id: string;
  title: string;
  authority: string;
  url: string;
  accessedDate?: string;
  note?: string;
}

export interface TideObservation {
  /** ISO 8601 timestamp including an offset or Z. */
  timestamp: string;
  value: number;
  quality?: "verified" | "preliminary" | "unknown";
}

export interface GaugeSeries {
  stationId: string;
  stationName: string;
  parameterLabel: string;
  unit: string;
  datum: string;
  status: Extract<EvidenceStatus, "observed" | "mock">;
  sourceId: string;
  observations: TideObservation[];
  limitations: string[];
}

export interface HistoricalEventEvidence {
  eventId: string;
  title: string;
  dateLabel: string;
  summary: string;
  footprintStatus: Extract<EvidenceStatus, "observed" | "illustrative" | "mock">;
  footprintLabel: string;
  gaugeSeries?: GaugeSeries;
  sources: EvidenceSource[];
  limitations: string[];
}

export interface ScenarioStatusItem {
  status: EvidenceStatus;
  label?: string;
  description?: string;
}

