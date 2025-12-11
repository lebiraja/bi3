import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import clsx from 'clsx';

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  glow?: boolean;
  variant?: 'default' | 'gradient';
}

export const Card = ({
  children,
  className,
  hover = false,
  glow = false,
  variant = 'default',
}: CardProps) => {
  return (
    <motion.div
      className={clsx(
        'rounded-2xl p-6',
        variant === 'default' && 'bg-slate-800/50 border border-slate-700/50',
        variant === 'gradient' && 'bg-gradient-to-br from-slate-800/80 to-slate-900/80 border border-slate-600/30',
        hover && 'transition-all duration-200 hover:scale-[1.02] hover:shadow-xl hover:shadow-black/20',
        glow && 'animate-pulse-glow',
        className
      )}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
};

interface StatCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  variant?: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
}

export const StatCard = ({
  title,
  value,
  icon,
  trend,
  variant = 'blue',
}: StatCardProps) => {
  const iconBgClasses = {
    blue: 'bg-blue-500/20 text-blue-400',
    green: 'bg-green-500/20 text-green-400',
    yellow: 'bg-yellow-500/20 text-yellow-400',
    red: 'bg-red-500/20 text-red-400',
    purple: 'bg-purple-500/20 text-purple-400',
  };

  return (
    <Card hover className="relative overflow-hidden">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-400 text-sm font-medium mb-1">{title}</p>
          <motion.p
            className="text-3xl font-bold text-white"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
          >
            {value}
          </motion.p>
          {trend && (
            <p
              className={clsx(
                'text-sm mt-2 flex items-center gap-1',
                trend.isPositive ? 'text-green-400' : 'text-red-400'
              )}
            >
              <span>{trend.isPositive ? '↑' : '↓'}</span>
              <span>{Math.abs(trend.value)}%</span>
              <span className="text-slate-500">vs last week</span>
            </p>
          )}
        </div>
        <div className={clsx('p-3 rounded-xl', iconBgClasses[variant])}>
          {icon}
        </div>
      </div>
      {/* Decorative gradient */}
      <div
        className={clsx(
          'absolute -bottom-10 -right-10 w-32 h-32 rounded-full blur-3xl opacity-20',
          variant === 'blue' && 'bg-blue-500',
          variant === 'green' && 'bg-green-500',
          variant === 'yellow' && 'bg-yellow-500',
          variant === 'red' && 'bg-red-500',
          variant === 'purple' && 'bg-purple-500'
        )}
      />
    </Card>
  );
};
