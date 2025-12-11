import { motion } from 'framer-motion';
import clsx from 'clsx';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
}

export const Skeleton = ({
  className,
  variant = 'text',
  width,
  height,
}: SkeletonProps) => {
  const variantClasses = {
    text: 'rounded h-4',
    circular: 'rounded-full',
    rectangular: 'rounded-xl',
  };

  return (
    <motion.div
      className={clsx(
        'bg-slate-700/50 shimmer',
        variantClasses[variant],
        className
      )}
      style={{ width, height }}
      initial={{ opacity: 0.5 }}
      animate={{ opacity: [0.5, 0.8, 0.5] }}
      transition={{ duration: 1.5, repeat: Infinity }}
    />
  );
};

export const CardSkeleton = () => (
  <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6 space-y-4">
    <div className="flex items-center gap-4">
      <Skeleton variant="rectangular" width={48} height={48} />
      <div className="flex-1 space-y-2">
        <Skeleton width="60%" />
        <Skeleton width="40%" />
      </div>
    </div>
    <Skeleton variant="rectangular" height={100} className="w-full" />
  </div>
);

export const TableRowSkeleton = () => (
  <div className="flex items-center gap-4 p-4 border-b border-slate-700/30">
    <Skeleton variant="rectangular" width={48} height={48} />
    <div className="flex-1 space-y-2">
      <Skeleton width="50%" />
      <Skeleton width="30%" />
    </div>
    <Skeleton variant="rectangular" width={80} height={24} />
  </div>
);
