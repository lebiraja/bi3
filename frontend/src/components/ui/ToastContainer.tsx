import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { useNotifications } from '../../contexts/NotificationContext';

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorMap = {
  success: {
    bg: 'rgba(16, 185, 129, 0.1)',
    border: 'rgba(16, 185, 129, 0.3)',
    icon: 'var(--accent-emerald)',
    text: 'var(--text-primary)',
  },
  error: {
    bg: 'rgba(239, 68, 68, 0.1)',
    border: 'rgba(239, 68, 68, 0.3)',
    icon: 'var(--accent-rose)',
    text: 'var(--text-primary)',
  },
  warning: {
    bg: 'rgba(251, 191, 36, 0.1)',
    border: 'rgba(251, 191, 36, 0.3)',
    icon: '#f59e0b',
    text: 'var(--text-primary)',
  },
  info: {
    bg: 'rgba(99, 102, 241, 0.1)',
    border: 'rgba(99, 102, 241, 0.3)',
    icon: 'var(--accent-primary)',
    text: 'var(--text-primary)',
  },
};

export const ToastContainer = () => {
  const { notifications, clearNotification } = useNotifications();

  // Only show unread notifications as toasts
  const toastNotifications = notifications.filter((n) => !n.read).slice(0, 3);

  return (
    <div className="fixed top-20 sm:top-20 right-2 sm:right-6 left-2 sm:left-auto z-[9999] flex flex-col gap-3 pointer-events-none">
      <AnimatePresence>
        {toastNotifications.map((notification, index) => {
          const Icon = iconMap[notification.type];
          const colors = colorMap[notification.type];

          return (
            <motion.div
              key={notification.id}
              className="pointer-events-auto max-w-md backdrop-blur-xl border shadow-xl overflow-hidden"
              style={{
                background: colors.bg,
                borderColor: colors.border,
                borderRadius: 'var(--radius-lg)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
              }}
              initial={{ opacity: 0, y: -50, scale: 0.95, x: 100 }}
              animate={{ opacity: 1, y: 0, scale: 1, x: 0 }}
              exit={{ opacity: 0, x: 100, scale: 0.95 }}
              transition={{
                duration: 0.3,
                ease: [0.4, 0, 0.2, 1],
                delay: index * 0.1,
              }}
            >
              <div className="flex items-start gap-3 p-4">
                <div className="flex-shrink-0 mt-0.5">
                  <Icon className="w-5 h-5" style={{ color: colors.icon }} />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-semibold text-sm mb-0.5" style={{ color: colors.text }}>
                    {notification.title}
                  </h4>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {notification.message}
                  </p>
                </div>
                <button
                  onClick={() => clearNotification(notification.id)}
                  className="flex-shrink-0 p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                >
                  <X className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                </button>
              </div>
              
              {/* Progress bar */}
              <motion.div
                className="h-1"
                style={{ background: colors.icon, opacity: 0.3 }}
                initial={{ width: '100%' }}
                animate={{ width: '0%' }}
                transition={{ duration: 2, ease: 'linear' }}
              />
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
};
