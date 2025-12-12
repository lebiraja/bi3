import { motion } from 'framer-motion';
import clsx from 'clsx';

type Status = 'pending' | 'processing' | 'completed' | 'failed';

interface StatusBadgeProps {
  status: Status;
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;
}

export const StatusBadge = ({
  status,
  size = 'md',
  animated = true,
}: StatusBadgeProps) => {
  const config = {
    pending: {
      bg: 'bg-gradient-to-r from-slate-100 to-gray-100',
      text: 'text-gray-700',
      label: 'Pending',
      dot: 'bg-gray-500',
    },
    processing: {
      bg: 'bg-gradient-to-r from-blue-100 to-indigo-100',
      text: 'text-blue-800',
      label: 'Processing',
      dot: 'bg-blue-600',
    },
    completed: {
      bg: 'bg-gradient-to-r from-green-100 to-emerald-100',
      text: 'text-green-800',
      label: 'Completed',
      dot: 'bg-green-600',
    },
    failed: {
      bg: 'bg-gradient-to-r from-red-100 to-rose-100',
      text: 'text-red-800',
      label: 'Failed',
      dot: 'bg-red-600',
    },
  };

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5',
  };

  const dotSizes = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-2.5 h-2.5',
  };

  const statusConfig = config[status];

  return (
    <motion.span
      className={clsx(
        'inline-flex items-center gap-2 rounded-full font-medium',
        statusConfig.bg,
        statusConfig.text,
        sizeClasses[size]
      )}
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300 }}
    >
      <span className="relative flex">
        <span
          className={clsx('rounded-full', statusConfig.dot, dotSizes[size])}
        />
        {animated && status === 'processing' && (
          <motion.span
            className={clsx(
              'absolute inset-0 rounded-full',
              statusConfig.dot,
              dotSizes[size]
            )}
            animate={{ scale: [1, 2], opacity: [0.8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
      </span>
      {statusConfig.label}
    </motion.span>
  );
};

interface RiskBadgeProps {
  level: 'low' | 'medium' | 'high' | 'critical' | 'warning' | string;
  score?: number;
  size?: 'sm' | 'md' | 'lg';
}

export const RiskBadge = ({
  level,
  score,
  size = 'md',
}: RiskBadgeProps) => {
  const config: Record<string, { bg: string; text: string; border: string; label: string }> = {
    low: {
      bg: 'bg-gradient-to-r from-green-100 to-emerald-100',
      text: 'text-green-800',
      border: 'border-green-300',
      label: 'Low Risk',
    },
    medium: {
      bg: 'bg-gradient-to-r from-amber-100 to-yellow-100',
      text: 'text-amber-800',
      border: 'border-amber-300',
      label: 'Medium Risk',
    },
    warning: {
      bg: 'bg-gradient-to-r from-orange-100 to-amber-100',
      text: 'text-orange-800',
      border: 'border-orange-300',
      label: 'Warning',
    },
    high: {
      bg: 'bg-gradient-to-r from-orange-100 to-red-100',
      text: 'text-orange-800',
      border: 'border-orange-300',
      label: 'High Risk',
    },
    critical: {
      bg: 'bg-gradient-to-r from-red-100 to-rose-100',
      text: 'text-red-800',
      border: 'border-red-300',
      label: 'Critical',
    },
  };

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5',
  };

  // Fallback for unknown levels
  const riskConfig = config[level?.toLowerCase()] || {
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    border: 'border-gray-200',
    label: level || 'Unknown',
  };

  return (
    <motion.span
      className={clsx(
        'inline-flex items-center gap-2 rounded-lg font-medium border',
        riskConfig.bg,
        riskConfig.text,
        riskConfig.border,
        sizeClasses[size]
      )}
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
    >
      {riskConfig.label}
      {score !== undefined && (
        <span className="font-bold">({score})</span>
      )}
    </motion.span>
  );
};
