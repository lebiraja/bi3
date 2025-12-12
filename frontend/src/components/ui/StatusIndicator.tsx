import { motion } from 'framer-motion';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'connecting';
  label: string;
  size?: 'sm' | 'md' | 'lg';
}

export const StatusIndicator = ({ status, label, size = 'md' }: StatusIndicatorProps) => {
  const sizeMap = {
    sm: { dot: 'w-2 h-2', text: 'text-xs', icon: 'w-3 h-3' },
    md: { dot: 'w-2.5 h-2.5', text: 'text-sm', icon: 'w-4 h-4' },
    lg: { dot: 'w-3 h-3', text: 'text-base', icon: 'w-5 h-5' },
  };

  const statusConfig = {
    online: {
      color: 'var(--accent-emerald)',
      bg: 'rgba(16, 185, 129, 0.1)',
      icon: CheckCircle,
      label: 'Online',
    },
    offline: {
      color: 'var(--accent-rose)',
      bg: 'rgba(239, 68, 68, 0.1)',
      icon: XCircle,
      label: 'Offline',
    },
    connecting: {
      color: '#f59e0b',
      bg: 'rgba(251, 191, 36, 0.1)',
      icon: Loader2,
      label: 'Connecting',
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;
  const sizes = sizeMap[size];

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex items-center">
        {status === 'connecting' ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          >
            <Icon className={sizes.icon} style={{ color: config.color }} />
          </motion.div>
        ) : (
          <>
            <motion.div
              className={`rounded-full ${sizes.dot}`}
              style={{ background: config.color }}
              animate={status === 'online' ? { scale: [1, 1.2, 1] } : {}}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            />
            {status === 'online' && (
              <motion.div
                className={`absolute rounded-full ${sizes.dot}`}
                style={{ background: config.color }}
                animate={{
                  scale: [1, 2, 2],
                  opacity: [0.6, 0, 0],
                }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeOut' }}
              />
            )}
          </>
        )}
      </div>
      <span className={`font-medium ${sizes.text}`} style={{ color: 'var(--text-primary)' }}>
        {label}
      </span>
    </div>
  );
};

interface SystemStatusCardProps {
  title: string;
  items: Array<{
    name: string;
    status: 'online' | 'offline' | 'connecting';
  }>;
}

export const SystemStatusCard = ({ title, items }: SystemStatusCardProps) => {
  return (
    <div
      className="p-6 backdrop-blur-[var(--liquid-blur)] border"
      style={{
        background: 'var(--liquid-bg)',
        borderColor: 'var(--liquid-border)',
        borderRadius: 'var(--radius-xl)',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
        {title}
      </h3>
      <div className="space-y-3">
        {items.map((item, index) => (
          <motion.div
            key={item.name}
            className="flex items-center justify-between p-3 rounded-lg"
            style={{
              background: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-lg)',
            }}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1, duration: 0.3 }}
          >
            <span className="font-medium text-sm" style={{ color: 'var(--text-secondary)' }}>
              {item.name}
            </span>
            <StatusIndicator status={item.status} label={item.status} size="sm" />
          </motion.div>
        ))}
      </div>
    </div>
  );
};
