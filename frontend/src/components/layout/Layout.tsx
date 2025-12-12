import { Outlet } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sidebar } from './Sidebar';

export const Layout = () => {
  return (
    <div className="min-h-screen relative overflow-hidden transition-all duration-500" style={{ background: 'var(--bg-primary)' }}>
      {/* Animated gradient background overlay */}
      <div className="fixed inset-0 opacity-40 dark:opacity-30 pointer-events-none">
        <div className="absolute inset-0 animate-gradient" style={{
          background: 'radial-gradient(ellipse at top right, rgba(99, 102, 241, 0.15), transparent 50%), radial-gradient(ellipse at bottom left, rgba(139, 92, 246, 0.15), transparent 50%)',
          backgroundSize: '200% 200%'
        }} />
      </div>
      
      {/* Floating orbs with smooth animations */}
      <div className="fixed top-20 right-20 w-[500px] h-[500px] bg-gradient-to-br from-blue-400/20 to-cyan-400/20 dark:from-blue-500/10 dark:to-cyan-500/10 rounded-full blur-3xl animate-float pointer-events-none" />
      <div className="fixed bottom-20 left-20 w-[500px] h-[500px] bg-gradient-to-br from-purple-400/20 to-pink-400/20 dark:from-purple-500/10 dark:to-pink-500/10 rounded-full blur-3xl animate-float-slow pointer-events-none" />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-br from-indigo-400/15 to-violet-400/15 dark:from-indigo-500/8 dark:to-violet-500/8 rounded-full blur-3xl animate-pulse-ring pointer-events-none" />
      
      {/* Subtle geometric patterns */}
      <div className="fixed inset-0 opacity-[0.03] dark:opacity-[0.05] pointer-events-none">
        <div className="absolute top-10 left-10 w-32 h-32 border-2 border-current rounded-lg animate-rotate-slow" style={{ color: 'var(--accent-primary)' }} />
        <div className="absolute bottom-10 right-10 w-40 h-40 border-2 border-current rounded-full animate-pulse-ring" style={{ color: 'var(--accent-secondary)' }} />
        <div className="absolute top-1/3 right-1/4 w-24 h-24 border-2 border-current rounded-lg animate-float" style={{ color: 'var(--accent-tertiary)' }} />
      </div>

      <Sidebar />

      <main className="lg:ml-64 min-h-screen relative z-10">
        <motion.div
          className="p-4 sm:p-6 lg:p-8 pt-16 lg:pt-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        >
          <Outlet />
        </motion.div>
      </main>
    </div>
  );
};
