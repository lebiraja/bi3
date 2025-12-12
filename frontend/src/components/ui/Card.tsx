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
        'p-6 backdrop-blur-[var(--liquid-blur)] border transition-all duration-[var(--transition-normal)]',
        variant === 'default' && 'bg-[var(--liquid-bg)] border-[var(--liquid-border)]',
        variant === 'gradient' && 'bg-gradient-to-br from-white/80 via-blue-50/80 to-indigo-50/80 dark:from-slate-800/80 dark:via-blue-900/20 dark:to-indigo-900/20 border-[var(--liquid-border)]',
        hover && 'hover:-translate-y-2 hover:border-[var(--accent-primary)]/20',
        glow && 'animate-pulse-glow',
        className
      )}
      style={{
        borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-md)'
      }}
      whileHover={hover ? {
        boxShadow: 'var(--shadow-xl)',
        scale: 1.01
      } : undefined}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
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
    blue: 'bg-gradient-to-br from-blue-100 to-blue-200 text-blue-700 shadow-md shadow-blue-200',
    green: 'bg-gradient-to-br from-green-100 to-green-200 text-green-700 shadow-md shadow-green-200',
    yellow: 'bg-gradient-to-br from-amber-100 to-amber-200 text-amber-700 shadow-md shadow-amber-200',
    red: 'bg-gradient-to-br from-red-100 to-red-200 text-red-700 shadow-md shadow-red-200',
    purple: 'bg-gradient-to-br from-purple-100 to-purple-200 text-purple-700 shadow-md shadow-purple-200',
  };

  const borderClasses = {
    blue: 'border-blue-100',
    green: 'border-green-100',
    yellow: 'border-amber-100',
    red: 'border-red-100',
    purple: 'border-purple-100',
  };

  return (
    <Card hover className={clsx('relative overflow-hidden border-l-4', borderClasses[variant])}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-gray-600 text-sm font-medium mb-1">{title}</p>
          <motion.p
            className="text-3xl font-bold text-gray-900"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
          >
            {value}
          </motion.p>
          {trend && (
            <p
              className={clsx(
                'text-sm mt-2 flex items-center gap-1 font-medium',
                trend.isPositive ? 'text-green-600' : 'text-red-600'
              )}
            >
              <span>{trend.isPositive ? '↑' : '↓'}</span>
              <span>{Math.abs(trend.value)}%</span>
              <span className="text-gray-400">vs last week</span>
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
          'absolute -bottom-10 -right-10 w-32 h-32 rounded-full blur-3xl opacity-10',
          variant === 'blue' && 'bg-blue-400',
          variant === 'green' && 'bg-green-400',
          variant === 'yellow' && 'bg-amber-400',
          variant === 'red' && 'bg-red-400',
          variant === 'purple' && 'bg-purple-400'
        )}
      />
    </Card>
  );
};
