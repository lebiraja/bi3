import { motion } from 'framer-motion';
import { Search, User, Sun, Moon } from 'lucide-react';
import { useSearch } from '../../contexts/SearchContext';
import { useTheme } from '../../contexts/ThemeContext';
import { NotificationDropdown } from '../ui/NotificationDropdown';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export const Header = ({ title, subtitle }: HeaderProps) => {
  const { searchQuery, setSearchQuery } = useSearch();
  const { theme, toggleTheme } = useTheme();

  return (
    <motion.header
      className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6 sm:mb-8 relative z-50"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex-1 min-w-0">
        <h1 className="text-2xl sm:text-3xl font-bold truncate" style={{ color: 'var(--text-primary)' }}>{title}</h1>
        {subtitle && (
          <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
        {/* Search */}
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
          <input
            type="text"
            placeholder="Search videos..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-48 lg:w-64 pl-10 pr-4 py-2.5 border focus:outline-none focus:ring-2 transition-all"
            style={{
              background: 'var(--liquid-bg)',
              backdropFilter: 'blur(var(--liquid-blur))',
              WebkitBackdropFilter: 'blur(var(--liquid-blur))',
              borderColor: 'var(--liquid-border)',
              borderRadius: 'var(--radius-lg)',
              color: 'var(--text-primary)',
              boxShadow: 'var(--shadow-sm)'
            }}
          />
        </div>

        {/* Theme Toggle */}
        <motion.button
          onClick={toggleTheme}
          className="relative p-2 sm:p-2.5 border group"
          style={{
            background: 'var(--liquid-bg)',
            backdropFilter: 'blur(var(--liquid-blur))',
            WebkitBackdropFilter: 'blur(var(--liquid-blur))',
            borderColor: 'var(--liquid-border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-sm)'
          }}
          whileHover={{ scale: 1.05, rotate: 180 }}
          whileTap={{ scale: 0.95 }}
          transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
          title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? (
            <Moon className="w-5 h-5" style={{ color: 'var(--text-secondary)' }} />
          ) : (
            <Sun className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
          )}
        </motion.button>

        {/* Notifications */}
        <NotificationDropdown />

        {/* Profile */}
        <motion.button
          className="flex items-center gap-2 sm:gap-3 p-2 sm:pr-4 border"
          style={{
            background: 'var(--liquid-bg)',
            backdropFilter: 'blur(var(--liquid-blur))',
            WebkitBackdropFilter: 'blur(var(--liquid-blur))',
            borderColor: 'var(--liquid-border)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-sm)'
          }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        >
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{
            background: 'var(--gradient-primary)',
            boxShadow: '0 4px 15px rgba(99, 102, 241, 0.3)'
          }}>
            <User className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-medium hidden sm:inline" style={{ color: 'var(--text-primary)' }}>Admin</span>
        </motion.button>
      </div>
    </motion.header>
  );
};
