// API Types matching FastAPI backend schemas

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ConfigResponse {
  vlm_model: string;
  frames_per_second: number;
  sample_interval: number;
  vehicle_classes: Record<string, string>;
  mongodb_connected: boolean;
}

export interface UploadResponse {
  job_id: string;
  video_id: string;
  message: string;
  ws_url: string;
}

export interface AnalysisJob {
  job_id: string;
  video_id: string;
  video_name: string;
  video_path: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  completed_at?: string;
  error?: string;
  result?: AnalysisResult;
}

export interface JobListResponse {
  jobs: AnalysisJob[];
  total: number;
}

export interface BehaviorObservation {
  behavior_type: string;
  vehicle_id: string;
  confidence: string;
  evidence: string;
  risk_level: string;
  description: string;
}

export interface AnalysisResult {
  video_id: string;
  total_seconds: number;
  analyzed_seconds: number;
  avg_risk_score: number;
  max_risk_score: number;
  critical_observations: BehaviorObservation[];
  analysis_timestamp: string;
}

export interface VideoInfo {
  path: string;
  fps: number;
  total_frames: number;
  duration_seconds: number;
  width: number;
  height: number;
  sample_interval: number;
  frames_per_second_sampled: number;
}

// WebSocket message types
export interface WSMessage {
  type: 'status' | 'progress' | 'completed' | 'error' | 'pong' | 'keepalive' | 'frame_preview';
  status?: string;
  progress?: number;
  message?: string;
  result?: AnalysisResult;
  // Frame preview fields
  frame?: string;
  second?: number;
  detections?: number;
}

// UI State types
export interface DashboardStats {
  totalJobs: number;
  completedJobs: number;
  processingJobs: number;
  failedJobs: number;
  avgRiskScore: number;
}
