import { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
    Play,
    Pause,
    Maximize,
    Volume2,
    VolumeX,
    Download,
    RefreshCw,
} from 'lucide-react';

interface VideoPlayerProps {
    src: string;
    title?: string;
    onError?: (error: Error) => void;
}

export const VideoPlayer = ({ src, title, onError }: VideoPlayerProps) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [isMuted, setIsMuted] = useState(true);
    const [progress, setProgress] = useState(0);
    const [duration, setDuration] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;

        const handleLoadedMetadata = () => {
            setDuration(video.duration);
            setIsLoading(false);
        };

        const handleTimeUpdate = () => {
            setCurrentTime(video.currentTime);
            setProgress((video.currentTime / video.duration) * 100);
        };

        const handleEnded = () => {
            setIsPlaying(false);
        };

        const handleError = () => {
            setError('Failed to load video');
            setIsLoading(false);
            onError?.(new Error('Failed to load video'));
        };

        video.addEventListener('loadedmetadata', handleLoadedMetadata);
        video.addEventListener('timeupdate', handleTimeUpdate);
        video.addEventListener('ended', handleEnded);
        video.addEventListener('error', handleError);

        return () => {
            video.removeEventListener('loadedmetadata', handleLoadedMetadata);
            video.removeEventListener('timeupdate', handleTimeUpdate);
            video.removeEventListener('ended', handleEnded);
            video.removeEventListener('error', handleError);
        };
    }, [onError]);

    const togglePlay = () => {
        const video = videoRef.current;
        if (!video) return;

        if (isPlaying) {
            video.pause();
        } else {
            video.play();
        }
        setIsPlaying(!isPlaying);
    };

    const toggleMute = () => {
        const video = videoRef.current;
        if (!video) return;

        video.muted = !isMuted;
        setIsMuted(!isMuted);
    };

    const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
        const video = videoRef.current;
        if (!video) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const pos = (e.clientX - rect.left) / rect.width;
        video.currentTime = pos * video.duration;
    };

    const toggleFullscreen = () => {
        const container = containerRef.current;
        if (!container) return;

        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            container.requestFullscreen();
        }
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const handleDownload = () => {
        const link = document.createElement('a');
        link.href = src;
        link.download = title || 'processed_video.mp4';
        link.click();
    };

    const handleRetry = () => {
        setError(null);
        setIsLoading(true);
        if (videoRef.current) {
            videoRef.current.load();
        }
    };

    return (
        <div
            ref={containerRef}
            className="relative rounded-2xl overflow-hidden bg-slate-900 border border-slate-700/50"
        >
            {/* Title Header */}
            {title && (
                <div className="absolute top-0 left-0 right-0 z-10 p-4 bg-gradient-to-b from-slate-900/90 to-transparent">
                    <h3 className="text-sm font-medium text-white">{title}</h3>
                </div>
            )}

            {/* Video Element */}
            <div className="aspect-video bg-black">
                {error ? (
                    <div className="w-full h-full flex flex-col items-center justify-center">
                        <p className="text-red-400 mb-4">{error}</p>
                        <button
                            onClick={handleRetry}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-colors"
                        >
                            <RefreshCw className="w-4 h-4" />
                            Retry
                        </button>
                    </div>
                ) : (
                    <video
                        ref={videoRef}
                        src={src}
                        className="w-full h-full object-contain"
                        muted={isMuted}
                        playsInline
                    />
                )}

                {/* Loading Overlay */}
                {isLoading && !error && (
                    <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50">
                        <motion.div
                            className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full"
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        />
                    </div>
                )}

                {/* Play Button Overlay */}
                {!isPlaying && !isLoading && !error && (
                    <button
                        onClick={togglePlay}
                        className="absolute inset-0 flex items-center justify-center group"
                    >
                        <motion.div
                            className="w-20 h-20 rounded-full bg-blue-500/80 flex items-center justify-center group-hover:bg-blue-500 transition-colors"
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.95 }}
                        >
                            <Play className="w-8 h-8 text-white ml-1" />
                        </motion.div>
                    </button>
                )}
            </div>

            {/* Controls */}
            <div className="p-4 bg-slate-800/50">
                {/* Progress Bar */}
                <div
                    className="w-full h-1.5 bg-slate-700 rounded-full mb-3 cursor-pointer group"
                    onClick={handleSeek}
                >
                    <motion.div
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full relative"
                        style={{ width: `${progress}%` }}
                    >
                        <span className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
                    </motion.div>
                </div>

                {/* Control Buttons */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <button
                            onClick={togglePlay}
                            className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                        >
                            {isPlaying ? (
                                <Pause className="w-5 h-5 text-white" />
                            ) : (
                                <Play className="w-5 h-5 text-white" />
                            )}
                        </button>
                        <button
                            onClick={toggleMute}
                            className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                        >
                            {isMuted ? (
                                <VolumeX className="w-5 h-5 text-slate-400" />
                            ) : (
                                <Volume2 className="w-5 h-5 text-white" />
                            )}
                        </button>
                        <span className="text-sm text-slate-400 font-mono">
                            {formatTime(currentTime)} / {formatTime(duration)}
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleDownload}
                            className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                            title="Download"
                        >
                            <Download className="w-5 h-5 text-slate-400 hover:text-white" />
                        </button>
                        <button
                            onClick={toggleFullscreen}
                            className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                            title="Fullscreen"
                        >
                            <Maximize className="w-5 h-5 text-slate-400 hover:text-white" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default VideoPlayer;
