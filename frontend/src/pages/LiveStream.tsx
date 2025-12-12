import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Play,
    Square,
    Loader2,
    AlertCircle,
    Clock,
    Activity,
    AlertTriangle,
} from 'lucide-react';
import { Header } from '../components/layout';
import { Card, Button, StatusIndicator } from '../components/ui';
import { useNotifications } from '../contexts/NotificationContext';

type StreamState = 'idle' | 'initializing' | 'active' | 'stopped' | 'error';

interface StreamInfo {
    streamId: string | null;
    url: string;
    title: string;
    isLive: boolean;
    resolution: string;
    fps: number;
    state: StreamState;
    error: string | null;
    batchCount: number;
    totalFrames: number;
    initCountdown: number;
}

interface YOLOFrame {
    frame: string; // base64
    detections: any[];
    frameNumber: number;
}

interface VLMSummary {
    second_index: number;
    risk_score: number;
    summary: string;
    observations: any[];
}

interface EnhancedReport {
    batch_index: number;
    content: string;
    timestamp: string;
}

export const LiveStream = () => {
    const { addNotification } = useNotifications();
    const wsRef = useRef<WebSocket | null>(null);
    const [urlInput, setUrlInput] = useState('');
    const [streamInfo, setStreamInfo] = useState<StreamInfo>({
        streamId: null,
        url: '',
        title: '',
        isLive: false,
        resolution: '',
        fps: 0,
        state: 'idle',
        error: null,
        batchCount: 0,
        totalFrames: 0,
        initCountdown: 20,
    });

    const [currentFrame, setCurrentFrame] = useState<YOLOFrame | null>(null);
    const [latestSummary, setLatestSummary] = useState<VLMSummary | null>(null);
    const [reports, setReports] = useState<EnhancedReport[]>([]);
    const [batchProgress, setBatchProgress] = useState({ phase: 'idle', elapsed: 0 });

    // WebSocket connection
    const connectWebSocket = useCallback((streamId: string) => {
        const ws = new WebSocket(`ws://localhost:8000/ws/${streamId}`);

        ws.onopen = () => {
            console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch (data.type) {
                case 'initialization_started':
                    setStreamInfo(prev => ({ ...prev, state: 'initializing', initCountdown: 20 }));
                    break;

                case 'initialization_complete':
                    setStreamInfo(prev => ({ ...prev, state: 'active', initCountdown: 0 }));
                    addNotification('success', 'Stream Active', 'Initialization complete. Continuous processing started.');
                    break;

                case 'yolo_detection':
                    if (data.frame) {
                        setCurrentFrame({
                            frame: data.frame,
                            detections: data.detections || [],
                            frameNumber: data.frame_number,
                        });
                    }
                    break;

                case 'vlm_summary':
                    if (data.analysis) {
                        setLatestSummary(data.analysis);
                    }
                    break;

                case 'enhanced_report':
                    if (data.report) {
                        setReports(prev => [...prev, {
                            batch_index: data.batch_index,
                            content: data.report.content,
                            timestamp: new Date().toISOString(),
                        }]);
                        addNotification('warning', 'Incident Detected', 'Enhanced report generated for critical incident');
                    }
                    break;

                case 'batch_complete':
                    setStreamInfo(prev => ({
                        ...prev,
                        batchCount: data.batch_index + 1,
                        totalFrames: prev.totalFrames + data.frame_count,
                    }));
                    setBatchProgress({ phase: 'idle', elapsed: 0 });
                    break;

                case 'wait_started':
                    setBatchProgress({ phase: 'waiting', elapsed: 0 });
                    break;

                case 'error':
                    setStreamInfo(prev => ({ ...prev, state: 'error', error: data.error }));
                    addNotification('error', 'Stream Error', data.error);
                    break;
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            addNotification('error', 'Connection Error', 'WebSocket connection failed');
        };

        ws.onclose = () => {
            console.log('WebSocket closed');
        };

        wsRef.current = ws;
    }, [addNotification]);

    // Cleanup WebSocket on unmount
    useEffect(() => {
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    // Initialization countdown
    useEffect(() => {
        if (streamInfo.state === 'initializing' && streamInfo.initCountdown > 0) {
            const timer = setTimeout(() => {
                setStreamInfo(prev => ({ ...prev, initCountdown: prev.initCountdown - 1 }));
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [streamInfo.state, streamInfo.initCountdown]);

    const handleStartStream = async () => {
        if (!urlInput.trim()) {
            addNotification('error', 'Invalid URL', 'Please enter a valid YouTube or stream URL');
            return;
        }

        try {
            const response = await fetch('http://localhost:8000/api/stream/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: urlInput, quality: '720p' }),
            });

            if (!response.ok) {
                throw new Error('Failed to start stream');
            }

            const data = await response.json();

            setStreamInfo({
                streamId: data.stream_id,
                url: data.url,
                title: data.title,
                isLive: data.is_live,
                resolution: data.resolution,
                fps: data.fps,
                state: 'initializing',
                error: null,
                batchCount: 0,
                totalFrames: 0,
                initCountdown: 20,
            });

            // Connect WebSocket
            connectWebSocket(data.stream_id);

            addNotification('info', 'Stream Started', `Processing ${data.title}`);
        } catch (error: any) {
            addNotification('error', 'Start Failed', error.message);
            setStreamInfo(prev => ({ ...prev, state: 'error', error: error.message }));
        }
    };

    const handleStopStream = async () => {
        if (!streamInfo.streamId) return;

        try {
            await fetch('http://localhost:8000/api/stream/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stream_id: streamInfo.streamId }),
            });

            if (wsRef.current) {
                wsRef.current.close();
            }

            setStreamInfo(prev => ({ ...prev, state: 'stopped' }));
            addNotification('info', 'Stream Stopped', 'Stream processing terminated');
        } catch (error: any) {
            addNotification('error', 'Stop Failed', error.message);
        }
    };

    const isValidYouTubeUrl = (url: string) => {
        return url.includes('youtube.com') || url.includes('youtu.be');
    };

    return (
        <div>
            <Header
                title="Live Stream Analysis"
                subtitle="Process YouTube videos and live streams in real-time"
            />

            <div className="max-w-7xl mx-auto space-y-6">
                {/* URL Input & Controls */}
                <Card>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-semibold text-gray-900 mb-2">
                                YouTube or Stream URL
                            </label>
                            <input
                                type="text"
                                value={urlInput}
                                onChange={(e) => setUrlInput(e.target.value)}
                                placeholder="https://www.youtube.com/watch?v=..."
                                disabled={streamInfo.state === 'initializing' || streamInfo.state === 'active'}
                                className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                            />
                            <p className="mt-2 text-sm text-gray-600">
                                Supports YouTube videos and YouTube Live streams
                            </p>
                        </div>

                        <div className="flex gap-4">
                            {streamInfo.state === 'idle' || streamInfo.state === 'stopped' || streamInfo.state === 'error' ? (
                                <Button
                                    variant="primary"
                                    size="lg"
                                    onClick={handleStartStream}
                                    disabled={!urlInput.trim() || !isValidYouTubeUrl(urlInput)}
                                    icon={<Play className="w-5 h-5" />}
                                    className="flex-1"
                                >
                                    Start Stream
                                </Button>
                            ) : (
                                <Button
                                    variant="danger"
                                    size="lg"
                                    onClick={handleStopStream}
                                    icon={<Square className="w-5 h-5" />}
                                    className="flex-1"
                                >
                                    Stop Stream
                                </Button>
                            )}
                        </div>
                    </div>
                </Card>

                {/* Stream Status */}
                {streamInfo.streamId && (
                    <Card>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <StatusIndicator
                                    status={streamInfo.state === 'active' ? 'online' : streamInfo.state === 'initializing' ? 'connecting' : 'offline'}
                                    size="lg"
                                    label="Stream Status"
                                />
                                <div>
                                    <h3 className="text-lg font-semibold text-gray-900">{streamInfo.title || 'Loading...'}</h3>
                                    <p className="text-gray-600 font-medium">
                                        {streamInfo.resolution} @ {streamInfo.fps}fps
                                        {streamInfo.isLive && <span className="ml-2 text-red-600 font-semibold">● LIVE</span>}
                                    </p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="text-sm text-gray-600">Batches Processed</p>
                                <p className="text-2xl font-bold text-gray-900">{streamInfo.batchCount}</p>
                            </div>
                        </div>
                    </Card>
                )}

                {/* Initialization Countdown */}
                <AnimatePresence>
                    {streamInfo.state === 'initializing' && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                        >
                            <Card glow>
                                <div className="text-center">
                                    <motion.div
                                        className="w-24 h-24 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-200 flex items-center justify-center shadow-lg"
                                        animate={{ scale: [1, 1.05, 1] }}
                                        transition={{ duration: 2, repeat: Infinity }}
                                    >
                                        <Clock className="w-12 h-12 text-blue-600" />
                                    </motion.div>
                                    <h3 className="text-2xl font-bold text-gray-900 mb-2">
                                        Initializing Stream
                                    </h3>
                                    <p className="text-gray-600 mb-4 font-medium">
                                        Processing first 15 seconds of video...
                                    </p>
                                    <div className="text-5xl font-bold text-blue-600">
                                        {streamInfo.initCountdown}s
                                    </div>
                                </div>
                            </Card>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Main Content Grid */}
                {(streamInfo.state === 'active' || streamInfo.state === 'initializing') && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* YOLO Video Feed */}
                        <div className="lg:col-span-2">
                            <Card>
                                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <Activity className="w-5 h-5 text-blue-600" />
                                    Live YOLO Detection
                                    {streamInfo.state === 'initializing' && (
                                        <span className="text-sm text-orange-600 font-normal">
                                            (Initializing - {streamInfo.initCountdown}s remaining)
                                        </span>
                                    )}
                                </h3>
                                {currentFrame ? (
                                    <div className="relative">
                                        <img
                                            src={`data:image/jpeg;base64,${currentFrame.frame}`}
                                            alt="YOLO Detection"
                                            className="w-full rounded-lg shadow-lg"
                                        />
                                        <div className="absolute top-4 right-4 bg-black/70 px-3 py-1 rounded-lg">
                                            <p className="text-white text-sm font-semibold">
                                                {currentFrame.detections.length} vehicles detected
                                            </p>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center">
                                        <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
                                    </div>
                                )}
                            </Card>

                            {/* Batch Progress */}
                            <Card className="mt-6">
                                <h3 className="text-lg font-semibold text-gray-900 mb-4">Batch Progress</h3>
                                <div className="flex items-center gap-4">
                                    <div className="flex-1">
                                        <div className="flex justify-between text-sm mb-2">
                                            <span className="text-gray-600 font-medium">
                                                {batchProgress.phase === 'waiting' ? 'Waiting (5s)' : 'Processing (15s)'}
                                            </span>
                                            <span className="text-gray-900 font-semibold">Batch #{streamInfo.batchCount + 1}</span>
                                        </div>
                                        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                                            <motion.div
                                                className={`h-full ${batchProgress.phase === 'waiting' ? 'bg-yellow-500' : 'bg-blue-500'}`}
                                                initial={{ width: '0%' }}
                                                animate={{ width: '100%' }}
                                                transition={{ duration: batchProgress.phase === 'waiting' ? 5 : 15, ease: 'linear' }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </Card>
                        </div>

                        {/* VLM Summary & Reports */}
                        <div className="space-y-6">
                            {/* Latest VLM Summary */}
                            <Card>
                                <h3 className="text-lg font-semibold text-gray-900 mb-4">Latest Behavior Analysis</h3>
                                {latestSummary ? (
                                    <div className="space-y-3">
                                        <div className="flex items-center justify-between">
                                            <span className="text-gray-600 font-medium">Risk Score</span>
                                            <span className={`text-2xl font-bold ${latestSummary.risk_score >= 7 ? 'text-red-600' :
                                                latestSummary.risk_score >= 4 ? 'text-yellow-600' :
                                                    'text-green-600'
                                                }`}>
                                                {latestSummary.risk_score}/10
                                            </span>
                                        </div>
                                        <p className="text-gray-700 text-sm font-medium">{latestSummary.summary}</p>
                                        {latestSummary.observations.length > 0 && (
                                            <div className="mt-4 space-y-2">
                                                {latestSummary.observations.map((obs, idx) => (
                                                    <div key={idx} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                                                        <p className="text-sm font-semibold text-gray-900">{obs.behavior_type}</p>
                                                        <p className="text-xs text-gray-600 mt-1">{obs.description}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <p className="text-gray-500 text-center py-8 font-medium">Waiting for analysis...</p>
                                )}
                            </Card>

                            {/* Enhanced Reports */}
                            <Card>
                                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                    <AlertTriangle className="w-5 h-5 text-orange-600" />
                                    Incident Reports ({reports.length})
                                </h3>
                                <div className="space-y-3 max-h-96 overflow-y-auto">
                                    {reports.length > 0 ? (
                                        reports.map((report, idx) => (
                                            <div key={idx} className="p-4 bg-red-50 border border-red-200 rounded-lg">
                                                <div className="flex items-center justify-between mb-2">
                                                    <span className="text-sm font-semibold text-red-900">Batch #{report.batch_index}</span>
                                                    <span className="text-xs text-red-700">{new Date(report.timestamp).toLocaleTimeString()}</span>
                                                </div>
                                                <p className="text-sm text-red-800 line-clamp-3">{report.content}</p>
                                            </div>
                                        ))
                                    ) : (
                                        <p className="text-gray-500 text-center py-8 font-medium">No incidents detected</p>
                                    )}
                                </div>
                            </Card>
                        </div>
                    </div>
                )}

                {/* Error State */}
                {streamInfo.state === 'error' && streamInfo.error && (
                    <Card>
                        <div className="text-center">
                            <AlertCircle className="w-16 h-16 text-red-600 mx-auto mb-4" />
                            <h3 className="text-xl font-semibold text-gray-900 mb-2">Stream Error</h3>
                            <p className="text-red-700 font-medium">{streamInfo.error}</p>
                        </div>
                    </Card>
                )}
            </div>
        </div>
    );
};
