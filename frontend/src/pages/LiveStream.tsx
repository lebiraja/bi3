import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Play,
    Square,
    Loader2,
    AlertCircle,
    Activity,
    AlertTriangle,
    Zap,
    Car,
    Video,
    Wifi,
    WifiOff,
} from 'lucide-react';
import { Header } from '../components/layout';
import { Card, Button } from '../components/ui';
import { useNotifications } from '../contexts/NotificationContext';

type StreamState = 'idle' | 'connecting' | 'initializing' | 'active' | 'stopped' | 'error';

interface StreamInfo {
    streamId: string | null;
    url: string;
    title: string;
    isLive: boolean;
    resolution: string;
    fps: number;
    state: StreamState;
    error: string | null;
}

interface Stats {
    frameCount: number;
    vehicleCount: number;
    yoloLatency: number;
    vlmLatency: number;
    vlmAnalysisCount: number;
    riskScore: number;
}

interface VLMAnalysis {
    timestamp_ms: number;
    risk_score: number;
    summary: string;
    observations: any[];
    processing_time_ms: number;
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
    });

    const [stats, setStats] = useState<Stats>({
        frameCount: 0,
        vehicleCount: 0,
        yoloLatency: 0,
        vlmLatency: 0,
        vlmAnalysisCount: 0,
        riskScore: 0,
    });

    const [currentFrame, setCurrentFrame] = useState<string | null>(null);
    const [latestAnalysis, setLatestAnalysis] = useState<VLMAnalysis | null>(null);
    const [wsConnected, setWsConnected] = useState(false);

    // WebSocket connection
    const connectWebSocket = useCallback((streamId: string) => {
        const wsUrl = `ws://${window.location.host}/ws/stream/${streamId}`;
        console.log('Connecting to WebSocket:', wsUrl);

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected');
            setWsConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'initialization_started':
                        setStreamInfo(prev => ({ ...prev, state: 'initializing' }));
                        break;

                    case 'initialization_complete':
                        setStreamInfo(prev => ({ ...prev, state: 'active' }));
                        addNotification('success', 'Stream Active', 'Continuous analysis started');
                        break;

                    case 'yolo_detection':
                        setStats(prev => ({
                            ...prev,
                            frameCount: data.frame_number || prev.frameCount,
                            vehicleCount: data.vehicle_count || 0,
                            yoloLatency: data.processing_time_ms || prev.yoloLatency,
                        }));
                        break;

                    case 'yolo_video_frame':
                        // Handle frame_base64 from backend
                        const frameData = data.frame_base64 || data.frame;
                        if (frameData) {
                            setCurrentFrame(frameData);
                            setStreamInfo(prev => ({ ...prev, state: 'active' }));
                            setStats(prev => ({
                                ...prev,
                                frameCount: data.frame_number || prev.frameCount,
                                vehicleCount: data.vehicle_count || prev.vehicleCount,
                            }));
                        }
                        break;

                    case 'vlm_analysis':
                        if (data.analysis) {
                            setLatestAnalysis(data.analysis);
                            setStats(prev => ({
                                ...prev,
                                vlmLatency: data.analysis.processing_time_ms || 0,
                                vlmAnalysisCount: prev.vlmAnalysisCount + 1,
                                riskScore: data.analysis.risk_score || 0,
                            }));
                        }
                        break;

                    case 'vlm_summary':
                        if (data.analysis) {
                            setLatestAnalysis(data.analysis);
                        }
                        break;

                    case 'enhanced_report':
                        addNotification('warning', 'Critical Incident', 'Enhanced report generated');
                        break;

                    case 'error':
                        setStreamInfo(prev => ({ ...prev, state: 'error', error: data.error }));
                        addNotification('error', 'Stream Error', data.error);
                        break;
                }
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            setWsConnected(false);
        };

        ws.onclose = () => {
            console.log('WebSocket closed');
            setWsConnected(false);
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

    const handleStartStream = async () => {
        if (!urlInput.trim()) {
            addNotification('error', 'Invalid URL', 'Please enter a valid URL');
            return;
        }

        setStreamInfo(prev => ({ ...prev, state: 'connecting' }));

        try {
            const response = await fetch('/api/stream/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: urlInput, quality: '720p' }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start stream');
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
            });

            // Reset stats
            setStats({
                frameCount: 0,
                vehicleCount: 0,
                yoloLatency: 0,
                vlmLatency: 0,
                vlmAnalysisCount: 0,
                riskScore: 0,
            });
            setCurrentFrame(null);
            setLatestAnalysis(null);

            // Connect WebSocket
            connectWebSocket(data.stream_id);

            addNotification('info', 'Stream Started', `Processing: ${data.title}`);
        } catch (error: any) {
            addNotification('error', 'Failed to Start', error.message);
            setStreamInfo(prev => ({ ...prev, state: 'error', error: error.message }));
        }
    };

    const handleStopStream = async () => {
        if (!streamInfo.streamId) return;

        try {
            await fetch('/api/stream/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stream_id: streamInfo.streamId }),
            });

            if (wsRef.current) {
                wsRef.current.close();
            }

            setStreamInfo(prev => ({ ...prev, state: 'stopped' }));
            addNotification('info', 'Stream Stopped', 'Analysis terminated');
        } catch (error: any) {
            addNotification('error', 'Stop Failed', error.message);
        }
    };

    const isValidUrl = (url: string) => {
        return url.includes('youtube.com') || url.includes('youtu.be') || url.startsWith('rtsp://') || url.startsWith('http');
    };

    const getStateColor = () => {
        switch (streamInfo.state) {
            case 'active': return 'bg-green-500';
            case 'initializing': return 'bg-yellow-500';
            case 'connecting': return 'bg-blue-500';
            case 'error': return 'bg-red-500';
            default: return 'bg-gray-400';
        }
    };

    const getRiskColor = (score: number) => {
        if (score >= 7) return 'text-red-500';
        if (score >= 4) return 'text-yellow-500';
        return 'text-green-500';
    };

    return (
        <div className="min-h-screen bg-gray-950">
            <Header
                title="Live Stream Analysis"
                subtitle="Real-time YOLO + VLM continuous analysis"
            />

            <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
                {/* URL Input */}
                <Card className="bg-gray-900 border-gray-800">
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                Stream URL
                            </label>
                            <input
                                type="text"
                                value={urlInput}
                                onChange={(e) => setUrlInput(e.target.value)}
                                placeholder="https://www.youtube.com/watch?v=... or YouTube Live URL"
                                disabled={streamInfo.state === 'connecting' || streamInfo.state === 'initializing' || streamInfo.state === 'active'}
                                className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors disabled:opacity-50"
                            />
                        </div>

                        <div className="flex gap-4">
                            {streamInfo.state === 'idle' || streamInfo.state === 'stopped' || streamInfo.state === 'error' ? (
                                <Button
                                    variant="primary"
                                    size="lg"
                                    onClick={handleStartStream}
                                    disabled={!urlInput.trim() || !isValidUrl(urlInput)}
                                    icon={<Play className="w-5 h-5" />}
                                    className="flex-1"
                                >
                                    Start Analysis
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

                {/* Status Bar */}
                {streamInfo.streamId && (
                    <Card className="bg-gray-900 border-gray-800">
                        <div className="flex items-center justify-between flex-wrap gap-4">
                            {/* Stream Info */}
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <div className={`w-3 h-3 rounded-full ${getStateColor()} animate-pulse`} />
                                    <span className="text-sm font-medium text-gray-400 capitalize">{streamInfo.state}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    {wsConnected ? (
                                        <Wifi className="w-4 h-4 text-green-500" />
                                    ) : (
                                        <WifiOff className="w-4 h-4 text-red-500" />
                                    )}
                                </div>
                                <div className="hidden md:block">
                                    <p className="text-white font-medium truncate max-w-md">{streamInfo.title}</p>
                                    <p className="text-gray-500 text-sm">
                                        {streamInfo.resolution} @ {streamInfo.fps}fps
                                        {streamInfo.isLive && <span className="ml-2 text-red-500 font-bold">● LIVE</span>}
                                    </p>
                                </div>
                            </div>

                            {/* Stats */}
                            <div className="flex items-center gap-6">
                                <div className="text-center">
                                    <div className="flex items-center gap-1 text-blue-400">
                                        <Car className="w-4 h-4" />
                                        <span className="text-xl font-bold">{stats.vehicleCount}</span>
                                    </div>
                                    <p className="text-xs text-gray-500">Vehicles</p>
                                </div>
                                <div className="text-center">
                                    <div className="flex items-center gap-1 text-green-400">
                                        <Zap className="w-4 h-4" />
                                        <span className="text-xl font-bold">{stats.yoloLatency.toFixed(0)}</span>
                                        <span className="text-xs">ms</span>
                                    </div>
                                    <p className="text-xs text-gray-500">YOLO</p>
                                </div>
                                <div className="text-center">
                                    <div className="flex items-center gap-1 text-purple-400">
                                        <Activity className="w-4 h-4" />
                                        <span className="text-xl font-bold">{(stats.vlmLatency / 1000).toFixed(1)}</span>
                                        <span className="text-xs">s</span>
                                    </div>
                                    <p className="text-xs text-gray-500">VLM</p>
                                </div>
                                <div className="text-center">
                                    <span className={`text-xl font-bold ${getRiskColor(stats.riskScore)}`}>
                                        {stats.riskScore}/10
                                    </span>
                                    <p className="text-xs text-gray-500">Risk</p>
                                </div>
                            </div>
                        </div>
                    </Card>
                )}

                {/* Loading State */}
                <AnimatePresence>
                    {(streamInfo.state === 'connecting' || streamInfo.state === 'initializing') && !currentFrame && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                        >
                            <Card className="bg-gray-900 border-gray-800">
                                <div className="text-center py-12">
                                    <Loader2 className="w-16 h-16 text-blue-500 animate-spin mx-auto mb-4" />
                                    <h3 className="text-xl font-bold text-white mb-2">
                                        {streamInfo.state === 'connecting' ? 'Connecting to Stream...' : 'Initializing Pipeline...'}
                                    </h3>
                                    <p className="text-gray-400">
                                        {streamInfo.state === 'connecting'
                                            ? 'Fetching stream information'
                                            : 'Loading YOLO model and starting VLM'}
                                    </p>
                                </div>
                            </Card>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Main Content */}
                {currentFrame && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Video Feed */}
                        <div className="lg:col-span-2">
                            <Card className="bg-gray-900 border-gray-800 p-0 overflow-hidden">
                                <div className="relative">
                                    <img
                                        src={`data:image/jpeg;base64,${currentFrame}`}
                                        alt="Live YOLO Detection"
                                        className="w-full"
                                    />
                                    {/* Overlay Stats */}
                                    <div className="absolute top-4 left-4 bg-black/70 backdrop-blur px-3 py-2 rounded-lg">
                                        <div className="flex items-center gap-2">
                                            <Video className="w-4 h-4 text-red-500" />
                                            <span className="text-white text-sm font-mono">
                                                Frame #{stats.frameCount}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="absolute top-4 right-4 bg-black/70 backdrop-blur px-3 py-2 rounded-lg">
                                        <div className="flex items-center gap-2">
                                            <Car className="w-4 h-4 text-blue-400" />
                                            <span className="text-white text-sm font-bold">
                                                {stats.vehicleCount} vehicles
                                            </span>
                                        </div>
                                    </div>
                                    <div className="absolute bottom-4 left-4 bg-black/70 backdrop-blur px-3 py-2 rounded-lg">
                                        <span className="text-green-400 text-xs font-mono">
                                            YOLO: {stats.yoloLatency.toFixed(0)}ms • 15 FPS
                                        </span>
                                    </div>
                                </div>
                            </Card>
                        </div>

                        {/* Analysis Panel */}
                        <div className="space-y-6">
                            {/* VLM Analysis */}
                            <Card className="bg-gray-900 border-gray-800">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                        <Activity className="w-5 h-5 text-purple-500" />
                                        Behavior Analysis
                                    </h3>
                                    <span className="text-xs text-gray-500">Every 2s</span>
                                </div>

                                {latestAnalysis ? (
                                    <div className="space-y-4">
                                        {/* Risk Score */}
                                        <div>
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-gray-400">Risk Score</span>
                                                <span className={`text-2xl font-bold ${getRiskColor(latestAnalysis.risk_score)}`}>
                                                    {latestAnalysis.risk_score}/10
                                                </span>
                                            </div>
                                            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full transition-all duration-500 ${
                                                        latestAnalysis.risk_score >= 7 ? 'bg-red-500' :
                                                        latestAnalysis.risk_score >= 4 ? 'bg-yellow-500' :
                                                        'bg-green-500'
                                                    }`}
                                                    style={{ width: `${latestAnalysis.risk_score * 10}%` }}
                                                />
                                            </div>
                                        </div>

                                        {/* Summary */}
                                        <p className="text-gray-300 text-sm">{latestAnalysis.summary}</p>

                                        {/* Observations */}
                                        {latestAnalysis.observations && latestAnalysis.observations.length > 0 && (
                                            <div className="space-y-2 max-h-48 overflow-y-auto">
                                                {latestAnalysis.observations.slice(0, 3).map((obs: any, idx: number) => (
                                                    <div key={idx} className="p-3 bg-gray-800 rounded-lg border border-gray-700">
                                                        <div className="flex items-center justify-between mb-1">
                                                            <span className="text-sm font-medium text-white">{obs.behavior_type}</span>
                                                            <span className={`text-xs px-2 py-0.5 rounded ${
                                                                obs.risk_level === 'critical' ? 'bg-red-500/20 text-red-400' :
                                                                obs.risk_level === 'warning' ? 'bg-yellow-500/20 text-yellow-400' :
                                                                'bg-green-500/20 text-green-400'
                                                            }`}>
                                                                {obs.risk_level}
                                                            </span>
                                                        </div>
                                                        <p className="text-xs text-gray-400">{obs.description}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        <p className="text-xs text-gray-500">
                                            Analyzed in {(latestAnalysis.processing_time_ms / 1000).toFixed(1)}s
                                        </p>
                                    </div>
                                ) : (
                                    <div className="text-center py-8">
                                        <Loader2 className="w-8 h-8 text-purple-500 animate-spin mx-auto mb-2" />
                                        <p className="text-gray-500">Waiting for VLM analysis...</p>
                                        <p className="text-xs text-gray-600 mt-1">First result in ~4 seconds</p>
                                    </div>
                                )}
                            </Card>

                            {/* Analysis Stats */}
                            <Card className="bg-gray-900 border-gray-800">
                                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                    <Zap className="w-5 h-5 text-yellow-500" />
                                    Session Stats
                                </h3>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="text-center p-3 bg-gray-800 rounded-lg">
                                        <p className="text-2xl font-bold text-white">{stats.frameCount}</p>
                                        <p className="text-xs text-gray-500">Frames Processed</p>
                                    </div>
                                    <div className="text-center p-3 bg-gray-800 rounded-lg">
                                        <p className="text-2xl font-bold text-purple-400">{stats.vlmAnalysisCount}</p>
                                        <p className="text-xs text-gray-500">VLM Analyses</p>
                                    </div>
                                </div>
                            </Card>
                        </div>
                    </div>
                )}

                {/* Error State */}
                {streamInfo.state === 'error' && streamInfo.error && (
                    <Card className="bg-gray-900 border-red-800">
                        <div className="text-center py-8">
                            <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
                            <h3 className="text-xl font-semibold text-white mb-2">Stream Error</h3>
                            <p className="text-red-400">{streamInfo.error}</p>
                            <Button
                                variant="primary"
                                onClick={() => setStreamInfo(prev => ({ ...prev, state: 'idle', error: null }))}
                                className="mt-4"
                            >
                                Try Again
                            </Button>
                        </div>
                    </Card>
                )}
            </div>
        </div>
    );
};
