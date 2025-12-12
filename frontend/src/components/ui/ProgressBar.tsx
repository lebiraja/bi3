import { motion } from 'framer-motion';
import clsx from 'clsx';

interface ProgressBarProps {
  progress: number; // 0-100
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  label?: string;
  variant?: 'primary' | 'success' | 'warning' | 'danger';
  animated?: boolean;
}

export const ProgressBar = ({
  progress,
  size = 'md',
  showLabel = true,
  label,
  variant = 'primary',
  animated = true,
}: ProgressBarProps) => {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  const sizeClasses = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4',
  };

  const gradientClasses = {
    primary: 'from-blue-600 via-indigo-500 to-purple-600',
    success: 'from-green-500 via-emerald-500 to-teal-500',
    warning: 'from-yellow-500 via-amber-500 to-orange-500',
    danger: 'from-red-500 via-rose-500 to-pink-600',
  };

  return (
    <div className="w-full">
      {(showLabel || label) && (
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-gray-600">{label || 'Progress'}</span>
          <span className="text-sm font-semibold text-gray-900">
            {clampedProgress.toFixed(0)}%
          </span>
        </div>
      )}
      <div
        className={clsx(
          'w-full bg-gradient-to-r from-gray-100 to-gray-200 rounded-full overflow-hidden shadow-inner',
          sizeClasses[size]
        )}
      >
        <motion.div
          className={clsx(
            'h-full rounded-full bg-gradient-to-r relative shadow-sm',
            gradientClasses[variant]
          )}
          initial={{ width: 0 }}
          animate={{ width: `${clampedProgress}%` }}
          transition={{ duration: animated ? 0.5 : 0, ease: 'easeOut' }}
        >
          {animated && clampedProgress > 0 && clampedProgress < 100 && (
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
              animate={{ x: ['-100%', '200%'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
            />
          )}
        </motion.div>
      </div>
    </div>
  );
};

interface CircularProgressProps {
  progress: number;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
  variant?: 'primary' | 'success' | 'warning' | 'danger';
}

export const CircularProgress = ({
  progress,
  size = 120,
  strokeWidth = 8,
  showLabel = true,
  variant = 'primary',
}: CircularProgressProps) => {
  const clampedProgress = Math.min(100, Math.max(0, progress));
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (clampedProgress / 100) * circumference;

  const colors = {
    primary: '#3b82f6',
    success: '#22c55e',
    warning: '#f59e0b',
    danger: '#ef4444',
  };

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#334155"
          strokeWidth={strokeWidth}
          fill="none"
        />
        {/* Progress circle */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={colors[variant]}
          strokeWidth={strokeWidth}
          fill="none"
          strokeLinecap="round"
          initial={{ strokeDasharray: circumference, strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          style={{ filter: `drop-shadow(0 0 6px ${colors[variant]}50)` }}
        />
      </svg>
      {showLabel && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold text-white">
            {clampedProgress.toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
};
