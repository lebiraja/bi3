import { motion, AnimatePresence } from 'framer-motion';
import { Eye, Car } from 'lucide-react';

interface FramePreviewProps {
    frame: string | null; // base64 encoded image
    second: number;
    detections: number;
    message: string;
    isConnected: boolean;
}

export const FramePreview = ({
    frame,
    second,
    detections,
    message,
    isConnected,
}: FramePreviewProps) => {
    return (
        <div className="relative rounded-2xl overflow-hidden bg-slate-900/50 border border-slate-700/50">
            {/* Header */}
            <div className="absolute top-0 left-0 right-0 z-10 p-4 bg-gradient-to-b from-slate-900/90 to-transparent">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Eye className="w-4 h-4 text-blue-400" />
                        <span className="text-sm font-medium text-white">Live Preview</span>
                    </div>
                    <div className="flex items-center gap-4">
                        {isConnected && (
                            <div className="flex items-center gap-2 text-green-400 text-xs">
                                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                                Connected
                            </div>
                        )}
                        <div className="flex items-center gap-2 text-slate-400 text-sm">
                            <Car className="w-4 h-4" />
                            <span>{detections} vehicles</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Frame Display */}
            <AnimatePresence mode="wait">
                {frame ? (
                    <motion.div
                        key={second}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className="aspect-video"
                    >
                        <img
                            src={`data:image/jpeg;base64,${frame}`}
                            alt={`Frame at second ${second}`}
                            className="w-full h-full object-contain"
                        />
                    </motion.div>
                ) : (
                    <div className="aspect-video flex items-center justify-center bg-slate-800/50">
                        <div className="text-center">
                            <motion.div
                                className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-blue-500/10 flex items-center justify-center"
                                animate={{ scale: [1, 1.05, 1] }}
                                transition={{ duration: 2, repeat: Infinity }}
                            >
                                <Eye className="w-8 h-8 text-blue-400" />
                            </motion.div>
                            <p className="text-slate-400">Waiting for frame preview...</p>
                        </div>
                    </div>
                )}
            </AnimatePresence>

            {/* Footer with message */}
            <div className="absolute bottom-0 left-0 right-0 z-10 p-4 bg-gradient-to-t from-slate-900/90 to-transparent">
                <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-300">{message}</span>
                    <span className="text-sm text-blue-400 font-mono">
                        Second {second + 1}
                    </span>
                </div>
            </div>
        </div>
    );
};

export default FramePreview;
