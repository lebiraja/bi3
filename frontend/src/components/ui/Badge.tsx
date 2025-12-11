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
      bg: 'bg-slate-500/20',
      text: 'text-slate-400',
      label: 'Pending',
      dot: 'bg-slate-400',
    },
    processing: {
      bg: 'bg-blue-500/20',
      text: 'text-blue-400',
      label: 'Processing',
      dot: 'bg-blue-400',
    },
    completed: {
      bg: 'bg-green-500/20',
      text: 'text-green-400',
      label: 'Completed',
      dot: 'bg-green-400',
    },
    failed: {
      bg: 'bg-red-500/20',
      text: 'text-red-400',
      label: 'Failed',
      dot: 'bg-red-400',
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
  level: 'low' | 'medium' | 'high' | 'critical';
  score?: number;
  size?: 'sm' | 'md' | 'lg';
}

export const RiskBadge = ({
  level,
  score,
  size = 'md',
}: RiskBadgeProps) => {
  const config = {
    low: {
      bg: 'bg-green-500/20',
      text: 'text-green-400',
      border: 'border-green-500/30',
      label: 'Low Risk',
    },
    medium: {
      bg: 'bg-yellow-500/20',
      text: 'text-yellow-400',
      border: 'border-yellow-500/30',
      label: 'Medium Risk',
    },
    high: {
      bg: 'bg-orange-500/20',
      text: 'text-orange-400',
      border: 'border-orange-500/30',
      label: 'High Risk',
    },
    critical: {
      bg: 'bg-red-500/20',
      text: 'text-red-400',
      border: 'border-red-500/30',
      label: 'Critical',
    },
  };

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5',
  };

  const riskConfig = config[level];

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
