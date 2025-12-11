import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  Video,
  CheckCircle,
  Clock,
  TrendingUp,
  ArrowRight,
  Activity,
  Shield,
} from 'lucide-react';
import { Header } from '../components/layout';
import { Card, StatCard, StatusBadge, ProgressBar, RiskBadge } from '../components/ui';
import { listJobs, getConfig } from '../services/api';
import type { AnalysisJob, ConfigResponse } from '../types/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
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
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [jobsData, configData] = await Promise.all([
          listJobs(),
          getConfig(),
        ]);
        setJobs(jobsData.jobs);
        setConfig(configData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

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

  // Mock chart data (in production, this would come from real analytics)
  const chartData = [
    { name: 'Mon', analyses: 4, risk: 2.3 },
    { name: 'Tue', analyses: 6, risk: 3.1 },
    { name: 'Wed', analyses: 8, risk: 2.8 },
    { name: 'Thu', analyses: 5, risk: 4.2 },
    { name: 'Fri', analyses: 9, risk: 3.5 },
    { name: 'Sat', analyses: 3, risk: 1.9 },
    { name: 'Sun', analyses: 7, risk: 2.7 },
  ];

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
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
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

        {/* Charts Row */}
        <motion.div
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          variants={itemVariants}
        >
          {/* Analysis Activity Chart */}
          <Card>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-white">Analysis Activity</h3>
                <p className="text-sm text-slate-400">Weekly overview</p>
              </div>
              <div className="flex items-center gap-2 text-green-400">
                <TrendingUp className="w-4 h-4" />
                <span className="text-sm font-medium">+12%</span>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorAnalyses" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="analyses"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#colorAnalyses)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Risk Score Trend */}
          <Card>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-white">Risk Score Trend</h3>
                <p className="text-sm text-slate-400">Average daily risk levels</p>
              </div>
              <RiskBadge
                level={avgRiskScore < 3 ? 'low' : avgRiskScore < 5 ? 'medium' : 'high'}
                score={parseFloat(avgRiskScore.toFixed(1))}
              />
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#64748b" />
                  <YAxis stroke="#64748b" domain={[0, 5]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="risk"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ fill: '#f59e0b', strokeWidth: 2 }}
                    activeDot={{ r: 6, fill: '#f59e0b' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </motion.div>

        {/* Recent Jobs & System Status */}
        <motion.div
          className="grid grid-cols-1 lg:grid-cols-3 gap-6"
          variants={itemVariants}
        >
          {/* Recent Jobs */}
          <Card className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-white">Recent Analyses</h3>
                <p className="text-sm text-slate-400">Latest video processing jobs</p>
              </div>
              <Link
                to="/jobs"
                className="flex items-center gap-2 text-blue-400 hover:text-blue-300 transition-colors"
              >
                <span className="text-sm font-medium">View All</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            {recentJobs.length === 0 ? (
              <div className="text-center py-12">
                <Video className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400">No analyses yet</p>
                <Link
                  to="/upload"
                  className="inline-flex items-center gap-2 mt-4 text-blue-400 hover:text-blue-300"
                >
                  Upload your first video
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {recentJobs.map((job, index) => (
                  <motion.div
                    key={job.job_id}
                    className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl hover:bg-slate-800/50 transition-colors"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-slate-700/50 flex items-center justify-center">
                        <Video className="w-5 h-5 text-slate-400" />
                      </div>
                      <div>
                        <p className="font-medium text-white">{job.video_name}</p>
                        <p className="text-sm text-slate-400">
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
                  <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse" />
                  <span className="text-slate-300">API Server</span>
                </div>
                <span className="text-sm text-green-400">Online</span>
              </div>

              {/* MongoDB Status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      config?.mongodb_connected
                        ? 'bg-green-400 animate-pulse'
                        : 'bg-red-400'
                    }`}
                  />
                  <span className="text-slate-300">MongoDB</span>
                </div>
                <span
                  className={`text-sm ${
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
