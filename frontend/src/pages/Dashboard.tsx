import { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  Video,
  CheckCircle,
  Clock,
  ArrowRight,
  Activity,
  Shield,
} from 'lucide-react';
import { Header } from '../components/layout';
import { Card, StatCard, StatusBadge, ProgressBar, RiskBadge } from '../components/ui';
import { listJobs, getConfig } from '../services/api';
import type { AnalysisJob, ConfigResponse } from '../types/api';
import { useNotifications } from '../contexts/NotificationContext';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export const Dashboard = () => {
  const { addNotification, addPageNotification } = useNotifications();
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const hasNotifiedRef = useRef(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [jobsData, configData] = await Promise.all([
          listJobs(),
          getConfig(),
        ]);
        setJobs(jobsData.jobs);
        setConfig(configData);
        
        if (!hasNotifiedRef.current) {
          addPageNotification('dashboard', 'success', 'Dashboard Loaded', `Found ${jobsData.jobs.length} analysis jobs`);
          hasNotifiedRef.current = true;
        }
      } catch (error) {
        console.error('Failed to fetch data:', error);
        if (!hasNotifiedRef.current) {
          addNotification('error', 'Dashboard Load Failed', 'Could not load dashboard data. Please try again.');
          hasNotifiedRef.current = true;
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [addNotification, addPageNotification]);

  // Calculate stats
  const stats = {
    total: jobs.length,
    completed: jobs.filter((j) => j.status === 'completed').length,
    processing: jobs.filter((j) => j.status === 'processing').length,
    failed: jobs.filter((j) => j.status === 'failed').length,
  };

  // Get average risk score from completed jobs
  const avgRiskScore =
    jobs
      .filter((j) => j.status === 'completed' && j.result)
      .reduce((acc, j) => acc + (j.result?.avg_risk_score || 0), 0) /
      (stats.completed || 1);

  // Job status distribution chart data
  const statusChartData = [
    { name: 'Completed', value: stats.completed, color: '#10b981' },
    { name: 'Processing', value: stats.processing, color: '#3b82f6' },
    { name: 'Failed', value: stats.failed, color: '#ef4444' },
    { name: 'Pending', value: jobs.filter((j) => j.status === 'pending').length, color: '#f59e0b' },
  ].filter(item => item.value > 0);

  // Behavior detection statistics from completed jobs
  const behaviorChartData = [
    { 
      name: 'Unsafe Lane Change',
      count: jobs.filter(j => j.status === 'completed' && j.result?.critical_observations?.some(b => b.behavior_type?.toLowerCase().includes('lane'))).length,
      color: '#ef4444'
    },
    { 
      name: 'Speeding',
      count: jobs.filter(j => j.status === 'completed' && j.result?.critical_observations?.some(b => b.behavior_type?.toLowerCase().includes('speed'))).length,
      color: '#f59e0b'
    },
    { 
      name: 'Aggressive Driving',
      count: jobs.filter(j => j.status === 'completed' && j.result?.critical_observations?.some(b => b.behavior_type?.toLowerCase().includes('aggressive'))).length,
      color: '#dc2626'
    },
    { 
      name: 'Tailgating',
      count: jobs.filter(j => j.status === 'completed' && j.result?.critical_observations?.some(b => b.behavior_type?.toLowerCase().includes('follow') || b.behavior_type?.toLowerCase().includes('tailgat'))).length,
      color: '#ea580c'
    },
  ].filter(item => item.count > 0);

  // Recent jobs (last 5)
  const recentJobs = [...jobs]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <motion.div
          className="w-16 h-16 border-4 border-blue-500/30 border-t-blue-500 rounded-full"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      </div>
    );
  }

  return (
    <div>
      <Header
        title="Dashboard"
        subtitle="Monitor your video analysis pipeline"
      />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-8"
      >
        {/* Stats Grid */}
        <motion.div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6"
          variants={itemVariants}
        >
          <StatCard
            title="Total Analyses"
            value={stats.total}
            icon={<Video className="w-6 h-6" />}
            variant="blue"
          />
          <StatCard
            title="Completed"
            value={stats.completed}
            icon={<CheckCircle className="w-6 h-6" />}
            variant="green"
          />
          <StatCard
            title="Processing"
            value={stats.processing}
            icon={<Clock className="w-6 h-6" />}
            variant="yellow"
          />
          <StatCard
            title="Avg Risk Score"
            value={avgRiskScore.toFixed(1)}
            icon={<Shield className="w-6 h-6" />}
            variant="purple"
          />
        </motion.div>

        {/* Charts Row - Job Status and Detected Behaviors */}
        <motion.div
          className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6"
          variants={itemVariants}
        >
          {/* Job Status Distribution Chart */}
          <Card>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Job Status Distribution</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Current analysis job breakdown</p>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg" style={{ 
                background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1))',
                border: '1px solid rgba(99, 102, 241, 0.2)'
              }}>
                <Activity className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{stats.total} Total Jobs</span>
              </div>
            </div>
            <div className="h-72">
              {statusChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={statusChartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <defs>
                      <linearGradient id="completedGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10b981" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#059669" stopOpacity={0.6}/>
                      </linearGradient>
                      <linearGradient id="processingGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#2563eb" stopOpacity={0.6}/>
                      </linearGradient>
                      <linearGradient id="failedGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#ef4444" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#dc2626" stopOpacity={0.6}/>
                      </linearGradient>
                      <linearGradient id="pendingGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#d97706" stopOpacity={0.6}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
                    <XAxis 
                      dataKey="name" 
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                      axisLine={{ stroke: 'rgba(148, 163, 184, 0.2)' }}
                    />
                    <YAxis 
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                      axisLine={{ stroke: 'rgba(148, 163, 184, 0.2)' }}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(99, 102, 241, 0.05)' }}
                      contentStyle={{
                        background: 'rgba(15, 23, 42, 0.95)',
                        border: '1px solid rgba(99, 102, 241, 0.3)',
                        borderRadius: '12px',
                        backdropFilter: 'blur(20px)',
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
                        padding: '12px',
                      }}
                      labelStyle={{ color: 'var(--text-primary)', fontWeight: 600, marginBottom: '4px' }}
                      itemStyle={{ color: 'var(--text-secondary)', padding: '2px 0' }}
                    />
                    <Bar dataKey="value" radius={[12, 12, 0, 0]} maxBarSize={80}>
                      {statusChartData.map((entry, index) => (
                        <Cell 
                          key={`cell-${index}`} 
                          fill={
                            entry.name === 'Completed' ? 'url(#completedGradient)' :
                            entry.name === 'Processing' ? 'url(#processingGradient)' :
                            entry.name === 'Failed' ? 'url(#failedGradient)' :
                            'url(#pendingGradient)'
                          }
                          style={{ filter: 'drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3))' }}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex flex-col items-center justify-center h-full" style={{ color: 'var(--text-muted)' }}>
                  <Activity className="w-12 h-12 mb-3 opacity-30" />
                  <p className="text-sm">No job data available</p>
                  <p className="text-xs mt-1">Upload a video to get started</p>
                </div>
              )}
            </div>
          </Card>

          {/* Behavior Detection Statistics */}
          <Card>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Detected Behaviors</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Unsafe driving patterns identified</p>
              </div>
              <RiskBadge
                level={avgRiskScore < 3 ? 'low' : avgRiskScore < 5 ? 'medium' : 'high'}
                score={parseFloat(avgRiskScore.toFixed(1))}
              />
            </div>
            <div className="h-72">
              {behaviorChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={behaviorChartData} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <defs>
                      <linearGradient id="laneChangeGradient" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#ef4444" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#dc2626" stopOpacity={0.6}/>
                      </linearGradient>
                      <linearGradient id="speedingGradient" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#d97706" stopOpacity={0.6}/>
                      </linearGradient>
                      <linearGradient id="aggressiveGradient" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#dc2626" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#b91c1c" stopOpacity={0.6}/>
                      </linearGradient>
                      <linearGradient id="tailgatingGradient" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#ea580c" stopOpacity={0.8}/>
                        <stop offset="100%" stopColor="#c2410c" stopOpacity={0.6}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" horizontal={true} vertical={false} />
                    <XAxis 
                      type="number" 
                      tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                      axisLine={{ stroke: 'rgba(148, 163, 184, 0.2)' }}
                    />
                    <YAxis 
                      dataKey="name" 
                      type="category" 
                      width={140}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                      axisLine={{ stroke: 'rgba(148, 163, 184, 0.2)' }}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(239, 68, 68, 0.05)' }}
                      contentStyle={{
                        background: 'rgba(15, 23, 42, 0.95)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '12px',
                        backdropFilter: 'blur(20px)',
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
                        padding: '12px',
                      }}
                      labelStyle={{ color: 'var(--text-primary)', fontWeight: 600, marginBottom: '4px' }}
                      itemStyle={{ color: 'var(--text-secondary)', padding: '2px 0' }}
                      formatter={(value) => [`${value} incidents`, 'Count']}
                    />
                    <Bar dataKey="count" radius={[0, 12, 12, 0]} maxBarSize={40}>
                      {behaviorChartData.map((entry, index) => (
                        <Cell 
                          key={`cell-${index}`} 
                          fill={
                            entry.name.includes('Lane') ? 'url(#laneChangeGradient)' :
                            entry.name.includes('Speed') ? 'url(#speedingGradient)' :
                            entry.name.includes('Aggressive') ? 'url(#aggressiveGradient)' :
                            'url(#tailgatingGradient)'
                          }
                          style={{ filter: 'drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3))' }}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex flex-col items-center justify-center h-full" style={{ color: 'var(--text-muted)' }}>
                  <Shield className="w-12 h-12 mb-3 opacity-30" />
                  <p className="text-sm">No behavior data available</p>
                  <p className="text-xs mt-1">Complete video analyses to see behavior patterns</p>
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Average Risk Score + Recent Jobs & System Status */}
        <motion.div
          className="grid grid-cols-1 lg:grid-cols-4 gap-4 sm:gap-6"
          variants={itemVariants}
        >
          {/* Average Risk Score Card */}
          <Card>
            <div className="text-center py-4">
              <div className="flex items-center justify-center mb-4">
                <div className="relative">
                  <div 
                    className="absolute inset-0 blur-xl opacity-50 rounded-full"
                    style={{ 
                      background: avgRiskScore < 3 ? '#10b981' : avgRiskScore < 5 ? '#f59e0b' : '#ef4444'
                    }}
                  />
                  <Shield 
                    className="w-16 h-16 relative z-10" 
                    style={{ 
                      color: avgRiskScore < 3 ? '#10b981' : avgRiskScore < 5 ? '#f59e0b' : '#ef4444',
                      filter: 'drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4))'
                    }} 
                  />
                </div>
              </div>
              <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Average Risk Score</h3>
              <div className="relative inline-block mb-3">
                <div 
                  className="text-6xl font-bold" 
                  style={{ 
                    background: avgRiskScore < 3 
                      ? 'linear-gradient(135deg, #10b981, #059669)' 
                      : avgRiskScore < 5 
                      ? 'linear-gradient(135deg, #f59e0b, #d97706)' 
                      : 'linear-gradient(135deg, #ef4444, #dc2626)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    filter: 'drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3))'
                  }}
                >
                  {avgRiskScore.toFixed(1)}
                </div>
                <div 
                  className="absolute -inset-4 blur-2xl opacity-30 rounded-full"
                  style={{ 
                    background: avgRiskScore < 3 ? '#10b981' : avgRiskScore < 5 ? '#f59e0b' : '#ef4444'
                  }}
                />
              </div>
              <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>Out of 5.0 Maximum</p>
              
              {/* Risk Level Indicator */}
              <div className="flex items-center justify-center gap-2 mt-6">
                <RiskBadge
                  level={avgRiskScore < 3 ? 'low' : avgRiskScore < 5 ? 'medium' : 'high'}
                  score={parseFloat(avgRiskScore.toFixed(1))}
                />
              </div>
              
              {/* Risk Level Description */}
              <p className="text-xs mt-4 px-4" style={{ color: 'var(--text-muted)' }}>
                {avgRiskScore < 3 
                  ? 'Low risk - Safe driving patterns detected' 
                  : avgRiskScore < 5 
                  ? 'Medium risk - Some concerning behaviors observed' 
                  : 'High risk - Multiple unsafe behaviors detected'}
              </p>
            </div>
          </Card>

          {/* Recent Jobs */}
          <Card className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Recent Analyses</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Latest video processing jobs</p>
              </div>
              <Link
                to="/jobs"
                className="flex items-center gap-2 transition-colors"
                style={{ color: 'var(--accent-primary)' }}
              >
                <span className="text-sm font-medium">View All</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            {recentJobs.length === 0 ? (
              <div className="text-center py-12">
                <Video className="w-12 h-12 mx-auto mb-4" style={{ color: 'var(--text-muted)' }} />
                <p style={{ color: 'var(--text-secondary)' }}>No analyses yet</p>
                <Link
                  to="/upload"
                  className="inline-flex items-center gap-2 mt-4 transition-colors"
                  style={{ color: 'var(--accent-primary)' }}
                >
                  Upload your first video
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {recentJobs.map((job, index) => (
                  <Link
                    key={job.job_id}
                    to={`/jobs/${job.job_id}`}
                    style={{ textDecoration: 'none' }}
                  >
                    <motion.div
                      className="flex items-center justify-between p-4 border rounded-xl transition-all cursor-pointer"
                      style={{
                        background: 'var(--liquid-bg)',
                        backdropFilter: 'blur(var(--liquid-blur))',
                        WebkitBackdropFilter: 'blur(var(--liquid-blur))',
                        borderColor: 'var(--liquid-border)',
                      }}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.1 }}
                      whileHover={{ scale: 1.01, y: -2 }}
                    >
                      <div className="flex items-center gap-4">
                        <div 
                          className="w-10 h-10 rounded-lg flex items-center justify-center"
                          style={{
                            background: 'var(--gradient-primary)',
                            boxShadow: '0 4px 15px rgba(99, 102, 241, 0.3)',
                          }}
                        >
                          <Video className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>{job.video_name}</p>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                            {new Date(job.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {job.status === 'processing' && (
                          <div className="w-24">
                            <ProgressBar
                              progress={job.progress * 100}
                              size="sm"
                              showLabel={false}
                            />
                          </div>
                        )}
                        <StatusBadge status={job.status} size="sm" />
                      </div>
                    </motion.div>
                  </Link>
                ))}
              </div>
            )}
          </Card>

          {/* System Status */}
          <Card>
            <h3 className="text-lg font-semibold text-white mb-6">System Status</h3>
            <div className="space-y-6">
              {/* API Status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                  <span className="text-slate-300">API Server</span>
                </div>
                <span className="text-sm text-green-400 font-medium">Online</span>
              </div>

              {/* MongoDB Status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      config?.mongodb_connected
                        ? 'bg-green-400 animate-pulse'
                        : 'bg-red-400'
                    }`}
                  />
                  <span className="text-slate-300">MongoDB</span>
                </div>
                <span
                  className={`text-sm font-medium ${
                    config?.mongodb_connected ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {config?.mongodb_connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>

              {/* VLM Model */}
              <div className="pt-4 border-t border-slate-700/50">
                <p className="text-sm text-slate-400 mb-2">VLM Model</p>
                <p className="text-white font-medium">
                  {config?.vlm_model || 'Not configured'}
                </p>
              </div>

              {/* Frame Settings */}
              <div className="pt-4 border-t border-slate-700/50">
                <p className="text-sm text-slate-400 mb-2">Frame Sampling</p>
                <p className="text-white font-medium">
                  {config?.frames_per_second} FPS (interval: {config?.sample_interval})
                </p>
              </div>

              {/* Vehicle Classes */}
              <div className="pt-4 border-t border-slate-700/50">
                <p className="text-sm text-slate-400 mb-2">Detected Vehicles</p>
                <div className="flex flex-wrap gap-2">
                  {config?.vehicle_classes &&
                    Object.values(config.vehicle_classes).map((cls) => (
                      <span
                        key={cls}
                        className="px-2 py-1 bg-slate-700/50 rounded text-xs text-slate-300 capitalize"
                      >
                        {cls}
                      </span>
                    ))}
                </div>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Processing Jobs (if any) */}
        {stats.processing > 0 && (
          <motion.div variants={itemVariants}>
            <Card glow>
              <div className="flex items-center gap-3 mb-4">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                >
                  <Activity className="w-5 h-5 text-blue-400" />
                </motion.div>
                <h3 className="text-lg font-semibold text-white">
                  Active Processing ({stats.processing})
                </h3>
              </div>
              <div className="space-y-4">
                {jobs
                  .filter((j) => j.status === 'processing')
                  .map((job) => (
                    <div
                      key={job.job_id}
                      className="p-4 bg-slate-800/30 rounded-xl"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <p className="font-medium text-white">{job.video_name}</p>
                        <StatusBadge status="processing" />
                      </div>
                      <ProgressBar
                        progress={job.progress * 100}
                        label="Analysis Progress"
                        variant="primary"
                      />
                    </div>
                  ))}
              </div>
            </Card>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
};
