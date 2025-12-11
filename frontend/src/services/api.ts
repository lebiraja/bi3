import axios from 'axios';
import type {
  HealthResponse,
  ConfigResponse,
  UploadResponse,
  AnalysisJob,
  JobListResponse,
  AnalysisResult,
  VideoInfo,
  EnhancedReport,
} from '../types/api';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health check
export const getHealth = async (): Promise<HealthResponse> => {
  const response = await axios.get<HealthResponse>('/');
  return response.data;
};

// Get configuration
export const getConfig = async (): Promise<ConfigResponse> => {
  const response = await api.get<ConfigResponse>('/config');
  return response.data;
};

// Upload video and start analysis
export const uploadVideo = async (
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<UploadResponse>('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(progress);
      }
    },
  });

  return response.data;
};

// Analyze existing video
export const analyzeVideo = async (videoPath: string): Promise<UploadResponse> => {
  const response = await api.post<UploadResponse>('/analyze', {
    video_path: videoPath,
  });
  return response.data;
};

// List all jobs
export const listJobs = async (): Promise<JobListResponse> => {
  const response = await api.get<JobListResponse>('/jobs');
  return response.data;
};

// Get specific job
export const getJob = async (jobId: string): Promise<AnalysisJob> => {
  const response = await api.get<AnalysisJob>(`/jobs/${jobId}`);
  return response.data;
};

// Get job result
export const getJobResult = async (jobId: string): Promise<AnalysisResult> => {
  const response = await api.get<AnalysisResult>(`/jobs/${jobId}/result`);
  return response.data;
};

// Get enhanced report
export const getEnhancedReport = async (jobId: string): Promise<EnhancedReport> => {
  const response = await api.get<EnhancedReport>(`/jobs/${jobId}/enhanced-report`);
  return response.data;
};

// Get video info
export const getVideoInfo = async (path: string): Promise<VideoInfo> => {
  const response = await api.get<VideoInfo>('/video-info', {
    params: { path },
  });
  return response.data;
};

// WebSocket connection helper
export const createWebSocket = (jobId: string): WebSocket => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return new WebSocket(`${protocol}//${host}/ws/${jobId}`);
};

export default api;

