import { motion, AnimatePresence } from 'framer-motion';
import { Bell, X, CheckCheck, Trash2, CheckCircle, XCircle, AlertTriangle, Info } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useNotifications } from "../../contexts/NotificationContext";
import { formatDistanceToNow } from "date-fns";

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorMap = {
  success: 'var(--accent-emerald)',
  error: 'var(--accent-rose)',
  warning: '#f59e0b',
  info: 'var(--accent-primary)',
};

export const NotificationDropdown = () => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { notifications, unreadCount, markAsRead, markAllAsRead, clearNotification, clearAll } = useNotifications();

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Notification Bell Button */}
      <motion.button
        className="relative p-2.5 border group"
        style={{
          background: 'var(--liquid-bg)',
          backdropFilter: 'blur(var(--liquid-blur))',
          WebkitBackdropFilter: 'blur(var(--liquid-blur))',
          borderColor: 'var(--liquid-border)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-sm)',
        }}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <Bell className="w-5 h-5" style={{ color: 'var(--text-secondary)' }} />
        {unreadCount > 0 && (
          <motion.span
            className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full flex items-center justify-center text-[10px] font-bold text-white"
            style={{
              background: 'var(--gradient-primary)',
              boxShadow: '0 0 10px rgba(99, 102, 241, 0.5)',
            }}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 15 }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </motion.span>
        )}
      </motion.button>

      {/* Dropdown Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="fixed sm:absolute right-2 sm:right-0 left-2 sm:left-auto top-20 sm:top-auto mt-0 sm:mt-2 w-auto sm:w-96 max-h-[calc(100vh-6rem)] sm:max-h-[600px] flex flex-col border overflow-hidden"
            style={{
              background: 'var(--liquid-bg)',
              backdropFilter: 'blur(var(--liquid-blur))',
              WebkitBackdropFilter: 'blur(var(--liquid-blur))',
              borderColor: 'var(--liquid-border)',
              borderRadius: 'var(--radius-xl)',
              boxShadow: 'var(--shadow-xl)',
              zIndex: 9999,
            }}
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--liquid-border)' }}>
              <div>
                <h3 className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                  Notifications
                </h3>
                {unreadCount > 0 && (
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {unreadCount} unread
                  </p>
                )}
              </div>
              {notifications.length > 0 && (
                <div className="flex items-center gap-2">
                  {unreadCount > 0 && (
                    <button
                      onClick={markAllAsRead}
                      className="p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                      title="Mark all as read"
                    >
                      <CheckCheck className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                    </button>
                  )}
                  <button
                    onClick={clearAll}
                    className="p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    title="Clear all"
                  >
                    <Trash2 className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                  </button>
                </div>
              )}
            </div>

            {/* Notifications List */}
            <div className="flex-1 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 px-4">
                  <Bell className="w-12 h-12 mb-3" style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    No notifications
                  </p>
                  <p className="text-xs text-center mt-1" style={{ color: 'var(--text-muted)' }}>
                    You're all caught up!
                  </p>
                </div>
              ) : (
                <div className="divide-y" style={{ borderColor: 'var(--liquid-border)' }}>
                  {notifications.map((notification) => {
                    const Icon = iconMap[notification.type];
                    const iconColor = colorMap[notification.type];

                    return (
                      <motion.div
                        key={notification.id}
                        className="p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer relative"
                        onClick={() => !notification.read && markAsRead(notification.id)}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                      >
                        {!notification.read && (
                          <div
                            className="absolute left-0 top-0 bottom-0 w-1"
                            style={{ background: iconColor }}
                          />
                        )}
                        <div className="flex items-start gap-3 pl-2">
                          <div className="flex-shrink-0 mt-0.5">
                            <Icon className="w-5 h-5" style={{ color: iconColor }} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4
                              className="font-semibold text-sm mb-0.5"
                              style={{ color: 'var(--text-primary)' }}
                            >
                              {notification.title}
                            </h4>
                            <p className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
                              {notification.message}
                            </p>
                            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                              {formatDistanceToNow(notification.timestamp, { addSuffix: true })}
                            </p>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              clearNotification(notification.id);
                            }}
                            className="flex-shrink-0 p-1 rounded-lg hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                          >
                            <X className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                          </button>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
