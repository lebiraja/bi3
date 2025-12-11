import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Upload,
  FileVideo,
  Settings,
  Activity,
  Car,
} from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/upload', label: 'Upload Video', icon: Upload },
  { path: '/jobs', label: 'Analysis Jobs', icon: FileVideo },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export const Sidebar = () => {
  const location = useLocation();

  return (
    <motion.aside
      className="fixed left-0 top-0 h-screen w-64 bg-slate-900/95 border-r border-slate-700/50 backdrop-blur-xl z-50"
      initial={{ x: -100, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Logo */}
      <div className="p-6 border-b border-slate-700/50">
        <motion.div
          className="flex items-center gap-3"
          whileHover={{ scale: 1.02 }}
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
            <Car className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">VisionDrive</h1>
            <p className="text-xs text-slate-400">Behavior Analysis</p>
          </div>
        </motion.div>
      </div>

      {/* Navigation */}
      <nav className="p-4 space-y-2">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;

          return (
            <NavLink key={item.path} to={item.path}>
              <motion.div
                className={clsx(
                  'flex items-center gap-3 px-4 py-3 rounded-xl transition-colors relative',
                  isActive
                    ? 'text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                )}
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
              >
                {isActive && (
                  <motion.div
                    className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-xl border border-blue-500/30"
                    layoutId="activeNav"
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
                <Icon className="w-5 h-5 relative z-10" />
                <span className="font-medium relative z-10">{item.label}</span>
              </motion.div>
            </NavLink>
          );
        })}
      </nav>

      {/* Status indicator */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-slate-700/50">
        <div className="flex items-center gap-3 px-4 py-3 bg-slate-800/50 rounded-xl">
          <div className="relative">
            <Activity className="w-5 h-5 text-green-400" />
            <motion.div
              className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-green-400 rounded-full"
              animate={{ scale: [1, 1.3, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-white">API Connected</p>
            <p className="text-xs text-slate-400">v1.0.0</p>
          </div>
        </div>
      </div>
    </motion.aside>
  );
};
