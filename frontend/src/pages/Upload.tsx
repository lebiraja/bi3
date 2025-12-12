import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload as UploadIcon,
  FileVideo,
  X,
  Check,
  AlertCircle,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { Header } from '../components/layout';
import { Card, Button, ProgressBar, CircularProgress, FramePreview, StatusIndicator } from '../components/ui';
import { uploadVideo } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { useNotifications } from '../contexts/NotificationContext';
import type { WSMessage } from '../types/api';

type UploadState = 'idle' | 'uploading' | 'processing' | 'completed' | 'error';

interface UploadInfo {
  file: File | null;
  uploadProgress: number;
  analysisProgress: number;
  jobId: string | null;
  videoId: string | null;
  message: string;
  error: string | null;
  // Frame preview data
  framePreview: string | null;
  frameSecond: number;
  frameDetections: number;
}

export const Upload = () => {
  const navigate = useNavigate();
  const { addNotification, addPageNotification } = useNotifications();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [state, setState] = useState<UploadState>('idle');
  const hasNotifiedRef = useRef(false);
  const [info, setInfo] = useState<UploadInfo>({
    file: null,
    uploadProgress: 0,
    analysisProgress: 0,
    jobId: null,
    videoId: null,
    message: '',
    error: null,
    framePreview: null,
    frameSecond: 0,
    frameDetections: 0,
  });

  // WebSocket for real-time progress
  const { isConnected } = useWebSocket(info.jobId, {
    onMessage: (message: WSMessage) => {
      if (message.type === 'progress' || message.type === 'status') {
        setInfo((prev) => ({
          ...prev,
          analysisProgress: (message.progress || 0) * 100,
          message: message.message || prev.message,
        }));
      } else if (message.type === 'frame_preview') {
        // Handle frame preview for live visualization
        setInfo((prev) => ({
          ...prev,
          framePreview: message.frame || null,
          frameSecond: message.second || 0,
          frameDetections: message.detections || 0,
          message: message.message || prev.message,
        }));
      } else if (message.type === 'completed') {
        setState('completed');
        setInfo((prev) => ({
          ...prev,
          analysisProgress: 100,
          message: 'Analysis completed successfully!',
        }));
        addNotification('success', 'Analysis Complete', 'Video analysis finished successfully!');
      } else if (message.type === 'error') {
        setState('error');
        const errorMsg = message.message || 'Analysis failed';
        setInfo((prev) => ({
          ...prev,
          error: errorMsg,
        }));
        addNotification('error', 'Analysis Failed', errorMsg);
      }
    },
    autoReconnect: true,
  });

  useEffect(() => {
    if (!hasNotifiedRef.current) {
      addPageNotification('upload', 'info', 'Upload Page Ready', 'Select or drag a video file to begin analysis');
      hasNotifiedRef.current = true;
    }
  }, [addPageNotification]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  }, []);

  const handleFileSelect = (file: File) => {
    const validTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/x-matroska'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|avi|mov|mkv)$/i)) {
      const errorMsg = 'Invalid file type. Please upload MP4, AVI, MOV, or MKV files.';
      setInfo((prev) => ({
        ...prev,
        error: errorMsg,
      }));
      addNotification('error', 'Invalid File Type', errorMsg);
      return;
    }

    setInfo({
      file,
      uploadProgress: 0,
      analysisProgress: 0,
      jobId: null,
      videoId: null,
      message: '',
      error: null,
      framePreview: null,
      frameSecond: 0,
      frameDetections: 0,
    });
    setState('idle');
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleUpload = async () => {
    if (!info.file) return;

    setState('uploading');
    setInfo((prev) => ({ ...prev, error: null }));

    addNotification('info', 'Upload Started', `Uploading ${info.file.name}...`);

    try {
      const response = await uploadVideo(info.file, (progress) => {
        setInfo((prev) => ({ ...prev, uploadProgress: progress }));
      });

      setInfo((prev) => ({
        ...prev,
        jobId: response.job_id,
        videoId: response.video_id,
        uploadProgress: 100,
        message: 'Upload complete. Starting analysis...',
      }));
      setState('processing');
      addNotification('success', 'Upload Complete', 'Video uploaded successfully. Analysis in progress...');
    } catch (error: any) {
      setState('error');
      const errorMessage = error.response?.data?.detail || 'Upload failed. Please try again.';
      setInfo((prev) => ({
        ...prev,
        error: errorMessage,
      }));
      addNotification('error', 'Upload Failed', errorMessage);
    }
  };

  const handleReset = () => {
    setState('idle');
    setInfo({
      file: null,
      uploadProgress: 0,
      analysisProgress: 0,
      jobId: null,
      videoId: null,
      message: '',
      error: null,
      framePreview: null,
      frameSecond: 0,
      frameDetections: 0,
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div>
      <Header
        title="Upload Video"
        subtitle="Upload a video file to analyze driving behavior"
      />

      <div className="max-w-4xl mx-auto">
        <AnimatePresence mode="wait">
          {/* Idle / File Selection State */}
          {(state === 'idle' || state === 'error') && !info.file && (
            <motion.div
              key="upload-zone"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <Card className="p-0 overflow-hidden">
                <div
                  className={`relative p-12 border-2 border-dashed rounded-2xl transition-all cursor-pointer ${dragOver
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-slate-600 hover:border-slate-500 hover:bg-slate-800/30'
                    }`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".mp4,.avi,.mov,.mkv,video/*"
                    className="hidden"
                    onChange={handleInputChange}
                  />

                  <div className="text-center">
                    <motion.div
                      className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-200 flex items-center justify-center shadow-lg"
                      animate={dragOver ? { scale: 1.1 } : { scale: 1 }}
                    >
                      <UploadIcon className="w-10 h-10 text-blue-600" />
                    </motion.div>

                    <h3 className="text-xl font-semibold text-gray-900 mb-2">
                      Drop your video here
                    </h3>
                    <p className="text-gray-600 mb-4 font-medium">
                      or click to browse from your computer
                    </p>
                    <p className="text-sm text-gray-500">
                      Supported formats: MP4, AVI, MOV, MKV
                    </p>
                  </div>
                </div>
              </Card>

              {info.error && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-4 p-4 bg-gradient-to-r from-red-50 to-rose-50 border border-red-200 rounded-xl flex items-center gap-3 shadow-sm"
                >
                  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                  <p className="text-red-700 font-medium">{info.error}</p>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* File Selected State */}
          {state === 'idle' && info.file && (
            <motion.div
              key="file-selected"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <Card>
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-100 to-indigo-200 flex items-center justify-center shadow-md">
                      <FileVideo className="w-7 h-7 text-blue-700" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">
                        {info.file.name}
                      </h3>
                      <p className="text-gray-600 font-medium">
                        {formatFileSize(info.file.size)}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleReset}
                    icon={<X className="w-4 h-4" />}
                  >
                    Remove
                  </Button>
                </div>

                <div className="flex gap-4">
                  <Button
                    variant="primary"
                    size="lg"
                    className="flex-1"
                    onClick={handleUpload}
                    icon={<UploadIcon className="w-5 h-5" />}
                  >
                    Start Analysis
                  </Button>
                  <Button
                    variant="secondary"
                    size="lg"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Choose Different File
                  </Button>
                </div>
              </Card>
            </motion.div>
          )}

          {/* Uploading State */}
          {state === 'uploading' && (
            <motion.div
              key="uploading"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <Card>
                <div className="text-center mb-8">
                  <motion.div
                    className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-200 flex items-center justify-center shadow-lg"
                    animate={{ scale: [1, 1.05, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                  </motion.div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    Uploading Video
                  </h3>
                  <p className="text-gray-600 font-medium">{info.file?.name}</p>
                </div>

                <ProgressBar
                  progress={info.uploadProgress}
                  label="Upload Progress"
                  variant="primary"
                />
              </Card>
            </motion.div>
          )}

          {/* Processing State */}
          {state === 'processing' && (
            <motion.div
              key="processing"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <Card glow>
                {/* Frame Preview */}
                {info.framePreview && (
                  <div className="mb-6">
                    <FramePreview
                      frame={info.framePreview}
                      second={info.frameSecond}
                      detections={info.frameDetections}
                      message={info.message || 'Analyzing...'}
                      isConnected={isConnected}
                    />
                  </div>
                )}

                <div className="flex flex-col items-center mb-8">
                  <CircularProgress
                    progress={info.analysisProgress}
                    size={160}
                    variant="primary"
                  />
                  <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-2">
                    Analyzing Video
                  </h3>
                  <p className="text-gray-600 text-center max-w-md font-medium">
                    {info.message || 'Processing frames and detecting behaviors...'}
                  </p>
                  <div className="flex items-center gap-2 mt-4">
                    <StatusIndicator 
                      status={isConnected ? 'online' : 'connecting'} 
                      size="sm" 
                      label="Live updates"
                    />
                  </div>
                </div>

                {/* Analysis Steps */}
                <div className="space-y-4 p-4 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-xl shadow-sm">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center ${info.analysisProgress >= 10
                        ? 'bg-green-500/20'
                        : 'bg-slate-700/50'
                        }`}
                    >
                      {info.analysisProgress >= 10 ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : (
                        <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
                      )}
                    </div>
                    <span
                      className={
                        info.analysisProgress >= 10
                          ? 'text-white'
                          : 'text-slate-400'
                      }
                    >
                      Extracting video frames
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center ${info.analysisProgress >= 40
                        ? 'bg-green-500/20'
                        : info.analysisProgress >= 10
                          ? 'bg-blue-500/20'
                          : 'bg-slate-700/50'
                        }`}
                    >
                      {info.analysisProgress >= 40 ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : info.analysisProgress >= 10 ? (
                        <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                      ) : (
                        <span className="w-2 h-2 bg-slate-500 rounded-full" />
                      )}
                    </div>
                    <span
                      className={
                        info.analysisProgress >= 10
                          ? 'text-white'
                          : 'text-slate-400'
                      }
                    >
                      YOLO vehicle detection
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center ${info.analysisProgress >= 95
                        ? 'bg-green-500/20'
                        : info.analysisProgress >= 40
                          ? 'bg-blue-500/20'
                          : 'bg-slate-700/50'
                        }`}
                    >
                      {info.analysisProgress >= 95 ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : info.analysisProgress >= 40 ? (
                        <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                      ) : (
                        <span className="w-2 h-2 bg-slate-500 rounded-full" />
                      )}
                    </div>
                    <span
                      className={
                        info.analysisProgress >= 40
                          ? 'text-white'
                          : 'text-slate-400'
                      }
                    >
                      VLM behavior analysis
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center ${info.analysisProgress >= 100
                        ? 'bg-green-500/20'
                        : info.analysisProgress >= 95
                          ? 'bg-blue-500/20'
                          : 'bg-slate-700/50'
                        }`}
                    >
                      {info.analysisProgress >= 100 ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : info.analysisProgress >= 95 ? (
                        <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                      ) : (
                        <span className="w-2 h-2 bg-slate-500 rounded-full" />
                      )}
                    </div>
                    <span
                      className={
                        info.analysisProgress >= 95
                          ? 'text-white'
                          : 'text-slate-400'
                      }
                    >
                      Generating summary report
                    </span>
                  </div>
                </div>
              </Card>
            </motion.div>
          )}

          {/* Completed State */}
          {state === 'completed' && (
            <motion.div
              key="completed"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              <Card>
                <div className="text-center mb-8">
                  <motion.div
                    className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 200 }}
                  >
                    <Check className="w-10 h-10 text-green-400" />
                  </motion.div>
                  <h3 className="text-xl font-semibold text-white mb-2">
                    Analysis Complete!
                  </h3>
                  <p className="text-slate-400">
                    Your video has been analyzed successfully
                  </p>
                </div>

                <div className="flex gap-4">
                  <Button
                    variant="primary"
                    size="lg"
                    className="flex-1"
                    onClick={() => navigate(`/jobs/${info.jobId}`)}
                    icon={<ArrowRight className="w-5 h-5" />}
                    iconPosition="right"
                  >
                    View Results
                  </Button>
                  <Button variant="secondary" size="lg" onClick={handleReset}>
                    Upload Another
                  </Button>
                </div>
              </Card>
            </motion.div>
          )}

          {/* Error State */}
          {state === 'error' && info.error && (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <Card>
                <div className="text-center mb-8">
                  <motion.div
                    className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-red-100 to-rose-100 flex items-center justify-center shadow-lg"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 200 }}
                  >
                    <AlertCircle className="w-10 h-10 text-red-600" />
                  </motion.div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    Analysis Failed
                  </h3>
                  <p className="text-red-700 font-medium">{info.error}</p>
                </div>

                <div className="flex gap-4">
                  <Button
                    variant="primary"
                    size="lg"
                    className="flex-1"
                    onClick={handleUpload}
                  >
                    Retry Analysis
                  </Button>
                  <Button variant="secondary" size="lg" onClick={handleReset}>
                    Choose Different File
                  </Button>
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tips */}
        <motion.div
          className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          {[
            {
              title: 'Optimal Duration',
              description: 'Videos between 30 seconds and 5 minutes work best',
            },
            {
              title: 'Clear Footage',
              description: 'Ensure good visibility and stable camera movement',
            },
            {
              title: 'Traffic Content',
              description: 'Include vehicles and traffic scenarios for best analysis',
            },
          ].map((tip, index) => (
            <div
              key={index}
              className="p-4 bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 border border-blue-200 rounded-xl shadow-sm hover:shadow-md transition-all"
            >
              <h4 className="font-semibold text-gray-900 mb-1">{tip.title}</h4>
              <p className="text-sm text-gray-600">{tip.description}</p>
            </div>
          ))}
        </motion.div>
      </div>
    </div>
  );
};
