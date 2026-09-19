import { writable, get } from "svelte/store";

export interface Coordinates {
  latitude: number;
  longitude: number;
}

export interface AOIInfo {
  id: string;
  name: string;
  country?: string;
  type: string;
  center: Coordinates;
  area_km2: number;
  bbox: number[];
  polygon: number[][];
}

export interface MetricItem {
  label: string;
  value: string;
  change?: string;
  trend?: "increase" | "decrease" | "stable";
  unit?: string;
}

export interface TimeSeriesPoint {
  date: string;
  value: number;
  metric_name?: string;
  unit?: string;
  label?: string;
}

export interface SatelliteImagePair {
  t1_date: string;
  t1_url: string;
  t1_label: string;
  t2_date: string;
  t2_url: string;
  t2_label: string;
  description?: string;
}

export interface VisualizationSpec {
  type: string;
  title: string;
  sub_title?: string;
  date_range?: string;
  color_map?: string;
  legend_min?: number;
  legend_max?: number;
  legend_unit?: string;
  surface_opacity: number;
  vertical_exaggeration: number;
  reverse_depth?: boolean;
  surface_grid?: number[][];
  timeseries?: TimeSeriesPoint[];
}

export interface AuditTraceStage {
  stage: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  duration_ms: number;
  details?: string;
  timestamp: string;
}

export interface Provenance {
  source: string;
  worker_url?: string;
  fallback: boolean;
  model_id: string;
  model_name: string;
  dataset_ids: string[];
  acquisition_dates?: string;
  pipeline: string;
}

export interface BackendVisualization {
  id: string;
  type: string;
  title: string;
  sub_title?: string;
  description?: string;
  data?: any[];
  xAxis?: any;
  yAxis?: any;
  series?: any[];
  renderer?: string;
  unit?: string;
  source_field?: string;
  layer?: {
    layer_type?: string;
    name?: string;
    bbox?: number[];
    polygon?: number[][];
    color_hint?: string;
    metric?: {
      label?: string;
      value?: string;
    };
    opacity?: number;
  };
  legend?: {
    title?: string;
    unit?: string;
    color_scale?: string;
  };
  visualMap?: any;
  interaction?: {
    zoom?: boolean;
    tooltip?: boolean;
    legend_toggle?: boolean;
  };
}

export interface NormalizedResult {
  result_id: string;
  query: string;
  analysis_type: string;
  aoi: AOIInfo;
  location?: {
    name: string;
    latitude: number;
    longitude: number;
  };
  provenance: Provenance;
  key_finding: string;
  scientific_explanation: string;
  metrics: MetricItem[];
  image_comparison?: SatelliteImagePair;
  visualization?: VisualizationSpec;
  visualizations?: BackendVisualization[];
  time_series: TimeSeriesPoint[];
  before_image_url?: string;
  after_image_url?: string;
  aoi_bbox?: number[];
  confidence?: number | null;
  confidence_level?: string | null;
  audit_trace: AuditTraceStage[];
  suggested_questions: string[];
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  result?: NormalizedResult;
}

// Navigation & views
export type ViewState = "landing" | "processing" | "analysis";
export const appViewState = writable<ViewState>("landing");
export const activeNav = writable<"home" | "datasets" | "use-cases" | "docs">(
  "home",
);
export const activeSidebarTab = writable<
  | "chat"
  | "map"
  | "layers"
  | "analysis"
  | "investigations"
  | "history"
  | "settings"
>("chat");
export const isLandingPage = writable<boolean>(true);

// Chat & Results
export const conversationId = writable<string>(
  localStorage.getItem("sq_conv_id") || "",
);
export const messages = writable<ChatMessage[]>([]);
export const currentResult = writable<NormalizedResult | null>(null);
export const isAnalyzing = writable<boolean>(false);
export const showAuditTraceModal = writable<boolean>(false);
export const showSettingsModal = writable<boolean>(false);
export const showSaveInvestigationModal = writable<boolean>(false);

// Globe & AOI state
export const globeLocation = writable<{
  latitude: number;
  longitude: number;
  altitude: number;
  name: string;
  area_km2: number;
  bbox: number[];
  polygon: number[][];
  flyTrigger: number;
}>({
  latitude: 0,
  longitude: 0,
  altitude: 350000,
  name: "No AOI selected",
  area_km2: 0,
  bbox: [],
  polygon: [
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
  ],
  flyTrigger: 0,
});

// Layers State
export interface LayerConfig {
  id: string;
  name: string;
  category: "satellite" | "analysis" | "scientific";
  visible: boolean;
  opacity: number;
  description: string;
}

export const layersState = writable<LayerConfig[]>([
  {
    id: "sentinel2_rgb",
    name: "Sentinel-2 RGB Imagery",
    category: "satellite",
    visible: true,
    opacity: 1.0,
    description: "True-color high-resolution optical imagery",
  },
  {
    id: "sentinel1_sar",
    name: "Sentinel-1 SAR Radar",
    category: "satellite",
    visible: false,
    opacity: 0.8,
    description: "Radar backscatter surface roughness",
  },
  {
    id: "landsat_oli",
    name: "Landsat-8/9 OLI",
    category: "satellite",
    visible: false,
    opacity: 0.8,
    description: "Longitudinal multispectral coverage",
  },
  {
    id: "aoi_boundary",
    name: "AOI Footprint Boundary",
    category: "analysis",
    visible: true,
    opacity: 1.0,
    description: "Target region spatial bounding polygon",
  },
  {
    id: "ndvi_mask",
    name: "Vegetation & NDVI Mask",
    category: "analysis",
    visible: true,
    opacity: 0.85,
    description: "Normalized difference vegetation density",
  },
  {
    id: "builtup_layer",
    name: "Built-Up & Urban Growth",
    category: "analysis",
    visible: true,
    opacity: 0.85,
    description: "Impervious urban footprint expansion",
  },
  {
    id: "water_layer",
    name: "Water Bodies & Flood Extent",
    category: "analysis",
    visible: true,
    opacity: 0.85,
    description: "Surface water and inundation boundaries",
  },
  {
    id: "change_detection",
    name: "Change Detection Layer",
    category: "analysis",
    visible: true,
    opacity: 0.85,
    description: "Bi-temporal conversion and disturbance zones",
  },
  {
    id: "copernicus_dem",
    name: "Copernicus 3D Terrain",
    category: "scientific",
    visible: false,
    opacity: 0.7,
    description: "Digital Surface Model topographic relief",
  },
  {
    id: "confidence_mask",
    name: "Model Confidence Mask",
    category: "scientific",
    visible: false,
    opacity: 0.7,
    description: "Spatial model inference confidence distribution",
  },
]);

// Timeline / Timelapse State
export const timelineState = writable<{
  activeYear: string;
  years: string[];
  isPlaying: boolean;
}>({
  activeYear: "2024",
  years: ["2016", "2018", "2020", "2022", "2024", "2026"],
  isPlaying: false,
});

// Settings
export const userSettings = writable<{
  modelMode: "mock" | "worker";
  allowFallback: boolean;
  surfaceOpacity: number;
  verticalExaggeration: number;
  reverseDepth: boolean;
}>({
  modelMode: "mock",
  allowFallback: true,
  surfaceOpacity: 0.85,
  verticalExaggeration: 2.2,
  reverseDepth: false,
});
