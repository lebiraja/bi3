import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Upload,
  FileVideo,
  Settings,
  Activity,
  Car,
  X,
  Menu,
  Radio,
} from 'lucide-react';
import clsx from 'clsx';
import { useState } from 'react';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/upload', label: 'Upload Video', icon: Upload },
  { path: '/stream', label: 'Live Stream', icon: Radio },
  { path: '/jobs', label: 'Analysis Jobs', icon: FileVideo },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export const Sidebar = () => {
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Mobile Menu Button */}
      <motion.button
        onClick={() => setIsMobileMenuOpen(true)}
        className="fixed top-4 left-4 z-50 p-2 rounded-lg lg:hidden"
        style={{
          background: 'var(--liquid-bg)',
          backdropFilter: 'blur(var(--liquid-blur))',
          WebkitBackdropFilter: 'blur(var(--liquid-blur))',
          borderColor: 'var(--liquid-border)',
          border: '1px solid',
          boxShadow: 'var(--shadow-lg)'
        }}
        whileTap={{ scale: 0.95 }}
      >
        <Menu className="w-6 h-6" style={{ color: 'var(--text-primary)' }} />
      </motion.button>

      {/* Mobile Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsMobileMenuOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        className="fixed left-0 top-0 h-screen w-64 border-r z-50 -translate-x-full lg:translate-x-0"
        style={{
          background: 'var(--liquid-bg)',
          backdropFilter: 'blur(var(--liquid-blur))',
          WebkitBackdropFilter: 'blur(var(--liquid-blur))',
          borderColor: 'var(--liquid-border)',
          boxShadow: 'var(--shadow-xl)'
        }}
        initial={{ x: -264, opacity: 0 }}
        animate={{
          x: isMobileMenuOpen ? 264 : 0,
          opacity: 1,
        }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      >
        {/* Logo */}
        <div className="p-6 border-b relative" style={{
          borderColor: 'var(--liquid-border)',
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%)'
        }}>
          {/* Close button for mobile */}
          <button
            onClick={() => setIsMobileMenuOpen(false)}
            className="absolute top-4 right-4 p-1 rounded-lg lg:hidden"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X className="w-5 h-5" />
          </button>
          <motion.div
            className="flex items-center gap-3"
            whileHover={{ scale: 1.02 }}
            transition={{ duration: 0.3 }}
          >
            <div className="w-10 h-10 rounded-lg flex items-center justify-center shadow-lg" style={{
              background: 'var(--gradient-primary)',
              boxShadow: '0 4px 20px rgba(99, 102, 241, 0.3)'
            }}>
              <Car className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-clip-text text-transparent" style={{
                background: 'var(--gradient-primary)',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text'
              }}>X-IQ</h1>
              <p className="text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>Behavior Analysis</p>
            </div>
          </motion.div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;

            return (
              <NavLink key={item.path} to={item.path} onClick={() => setIsMobileMenuOpen(false)}>
                <motion.div
                  className={clsx(
                    'flex items-center gap-3 px-4 py-3 relative',
                    isActive ? 'font-medium' : ''
                  )}
                  style={{
                    borderRadius: 'var(--radius-lg)',
                    color: isActive ? 'var(--accent-primary)' : 'var(--text-secondary)',
                    background: isActive ? 'rgba(99, 102, 241, 0.08)' : 'transparent',
                    transition: 'all var(--transition-normal)'
                  }}
                  whileHover={{
                    x: 6,
                    background: isActive ? 'rgba(99, 102, 241, 0.12)' : 'rgba(99, 102, 241, 0.05)'
                  }}
                  whileTap={{ scale: 0.98 }}
                  transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                >
                  {isActive && (
                    <motion.div
                      className="absolute left-0 top-0 bottom-0 w-1 rounded-r"
                      style={{ background: 'var(--gradient-primary)' }}
                      layoutId="activeNav"
                      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    />
                  )}
                  <Icon className="w-5 h-5 relative z-10" />
                  <span className="relative z-10">{item.label}</span>
                </motion.div>
              </NavLink>
            );
          })}
        </nav>

        {/* Status indicator */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t" style={{
          borderColor: 'var(--liquid-border)',
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, transparent 100%)'
        }}>
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg border" style={{
            background: 'rgba(16, 185, 129, 0.08)',
            borderColor: 'rgba(16, 185, 129, 0.2)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: '0 4px 20px rgba(16, 185, 129, 0.15)'
          }}>
            <div className="relative">
              <Activity className="w-5 h-5" style={{ color: 'var(--accent-emerald)' }} />
              <motion.div
                className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full"
                style={{ background: 'var(--accent-emerald)' }}
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              />
            </div>
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--accent-emerald)' }}>API Connected</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>v1.0.0</p>
            </div>
          </div>
        </div>
      </motion.aside>
    </>
  );
};
