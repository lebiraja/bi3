import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Video,
  Clock,
  Calendar,
  AlertTriangle,
  Shield,
  FileText,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Car,
} from 'lucide-react';
import { Header } from '../components/layout';
import {
  Card,
  Button,
  StatusBadge,
  ProgressBar,
  CircularProgress,
  RiskBadge,
  VideoPlayer,
} from '../components/ui';
import { getJob } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import type { AnalysisJob, BehaviorObservation, WSMessage } from '../types/api';
import { format, formatDistanceToNow } from 'date-fns';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
} from 'recharts';

export const JobDetail = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedObservations, setExpandedObservations] = useState<Set<number>>(
    new Set()
  );

  // WebSocket for real-time updates on processing jobs
  useWebSocket(job?.status === 'processing' ? jobId || null : null, {
    onMessage: (message: WSMessage) => {
      if (message.type === 'progress' || message.type === 'status') {
        setJob((prev) =>
          prev
            ? {
              ...prev,
              progress: message.progress || prev.progress,
              status: (message.status as any) || prev.status,
            }
            : null
        );
      } else if (message.type === 'completed' && message.result) {
        setJob((prev) =>
          prev
            ? {
              ...prev,
              status: 'completed',
              progress: 1,
              result: message.result,
            }
            : null
        );
      }
    },
  });

  useEffect(() => {
    const fetchJob = async () => {
      if (!jobId) return;
      try {
        const data = await getJob(jobId);
        setJob(data);
      } catch (error) {
        console.error('Failed to fetch job:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchJob();
    const interval = setInterval(fetchJob, 3000);
    return () => clearInterval(interval);
  }, [jobId]);

  const toggleObservation = (index: number) => {
    setExpandedObservations((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const getRiskLevel = (score: number): 'low' | 'medium' | 'high' | 'critical' => {
    if (score < 2) return 'low';
    if (score < 4) return 'medium';
    if (score < 7) return 'high';
    return 'critical';
  };

  const getRiskColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case 'low':
        return '#22c55e';
      case 'medium':
        return '#f59e0b';
      case 'high':
        return '#f97316';
      case 'critical':
        return '#ef4444';
      default:
        return '#64748b';
    }
  };

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

  if (!job) {
    return (
      <div className="text-center py-20">
        <AlertTriangle className="w-16 h-16 text-yellow-400 mx-auto mb-4" />
        <h2 className="text-2xl font-semibold text-white mb-2">Job Not Found</h2>
        <p className="text-slate-400 mb-6">
          The job you're looking for doesn't exist or has been removed.
        </p>
        <Link to="/jobs">
          <Button variant="primary">Back to Jobs</Button>
        </Link>
      </div>
    );
  }

  // Prepare chart data
  const behaviorTypeData =
    job.result?.critical_observations?.reduce(
      (acc: { name: string; value: number }[], obs: BehaviorObservation) => {
        const existing = acc.find((item) => item.name === obs.behavior_type);
        if (existing) {
          existing.value += 1;
        } else {
          acc.push({ name: obs.behavior_type, value: 1 });
        }
        return acc;
      },
      []
    ) || [];

  const riskDistribution =
    job.result?.critical_observations?.reduce(
      (acc: { name: string; value: number; color: string }[], obs: BehaviorObservation) => {
        const level = obs.risk_level || 'unknown';
        const existing = acc.find((item) => item.name === level);
        if (existing) {
          existing.value += 1;
        } else {
          acc.push({
            name: level,
            value: 1,
            color: getRiskColor(level),
          });
        }
        return acc;
      },
      []
    ) || [];

  const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4'];

  return (
    <div>
      {/* Back Button */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/jobs')}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Jobs</span>
        </button>
      </div>

      <Header
        title={job.video_name}
        subtitle={`Job ID: ${job.job_id}`}
      />

      <div className="space-y-6">
        {/* Status Card */}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div
                className={`w-16 h-16 rounded-2xl flex items-center justify-center ${job.status === 'completed'
                  ? 'bg-green-500/10'
                  : job.status === 'processing'
                    ? 'bg-blue-500/10'
                    : job.status === 'failed'
                      ? 'bg-red-500/10'
                      : 'bg-slate-700/50'
                  }`}
              >
                <Video
                  className={`w-8 h-8 ${job.status === 'completed'
                    ? 'text-green-400'
                    : job.status === 'processing'
                      ? 'text-blue-400'
                      : job.status === 'failed'
                        ? 'text-red-400'
                        : 'text-slate-400'
                    }`}
                />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <StatusBadge status={job.status} />
                  {job.status === 'completed' && job.result && (
                    <RiskBadge
                      level={getRiskLevel(job.result.avg_risk_score)}
                      score={job.result.avg_risk_score}
                    />
                  )}
                </div>
                <div className="flex items-center gap-4 text-sm text-slate-400">
                  <div className="flex items-center gap-1">
                    <Calendar className="w-4 h-4" />
                    <span>
                      Created{' '}
                      {format(new Date(job.created_at), 'MMM d, yyyy h:mm a')}
                    </span>
                  </div>
                  {job.completed_at && (
                    <div className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      <span>
                        Completed{' '}
                        {formatDistanceToNow(new Date(job.completed_at), {
                          addSuffix: true,
                        })}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Progress for processing jobs */}
            {job.status === 'processing' && (
              <div className="flex items-center gap-6">
                <div className="w-48">
                  <ProgressBar
                    progress={job.progress * 100}
                    label="Analysis Progress"
                  />
                </div>
                <CircularProgress
                  progress={job.progress * 100}
                  size={80}
                  variant="primary"
                />
              </div>
            )}
          </div>

          {/* Error message */}
          {job.status === 'failed' && job.error && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5" />
                <div>
                  <p className="font-medium text-red-400">Analysis Failed</p>
                  <p className="text-sm text-red-300/80 mt-1">{job.error}</p>
                </div>
              </div>
            </div>
          )}
        </Card>

        {/* Results Section (for completed jobs) */}
        {job.status === 'completed' && job.result && (
          <>
            {/* YOLO Annotated Video */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
            >
              <Card>
                <h3 className="text-lg font-semibold text-white mb-4">
                  YOLO Detection Video
                </h3>
                <VideoPlayer
                  src={`/api/jobs/${job.job_id}/video`}
                  title={`${job.video_name} - YOLO Detection`}
                />
              </Card>
            </motion.div>

            {/* Summary Stats */}
            <motion.div
              className="grid grid-cols-1 md:grid-cols-4 gap-4"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
                    <Clock className="w-6 h-6 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Duration</p>
                    <p className="text-2xl font-bold text-white">
                      {job.result.total_seconds}s
                    </p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-green-500/10 flex items-center justify-center">
                    <BarChart3 className="w-6 h-6 text-green-400" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Analyzed</p>
                    <p className="text-2xl font-bold text-white">
                      {job.result.analyzed_seconds}s
                    </p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                    <Shield className="w-6 h-6 text-yellow-400" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Avg Risk</p>
                    <p
                      className={`text-2xl font-bold ${job.result.avg_risk_score < 3
                        ? 'text-green-400'
                        : job.result.avg_risk_score < 5
                          ? 'text-yellow-400'
                          : 'text-red-400'
                        }`}
                    >
                      {job.result.avg_risk_score.toFixed(1)}
                    </p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center">
                    <AlertTriangle className="w-6 h-6 text-red-400" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-400">Observations</p>
                    <p className="text-2xl font-bold text-white">
                      {job.result.critical_observations?.length || 0}
                    </p>
                  </div>
                </div>
              </Card>
            </motion.div>

            {/* Charts Row */}
            {job.result.critical_observations?.length > 0 && (
              <motion.div
                className="grid grid-cols-1 lg:grid-cols-2 gap-6"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                {/* Behavior Types */}
                <Card>
                  <h3 className="text-lg font-semibold text-white mb-4">
                    Behavior Distribution
                  </h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={behaviorTypeData}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={90}
                          paddingAngle={2}
                          dataKey="value"
                        >
                          {behaviorTypeData.map((_, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={COLORS[index % COLORS.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                          }}
                        />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                {/* Risk Distribution */}
                <Card>
                  <h3 className="text-lg font-semibold text-white mb-4">
                    Risk Level Distribution
                  </h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={riskDistribution}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={90}
                          paddingAngle={2}
                          dataKey="value"
                        >
                          {riskDistribution.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                          }}
                        />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              </motion.div>
            )}

            {/* Critical Observations */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <Card>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-slate-400" />
                    <h3 className="text-lg font-semibold text-white">
                      Critical Observations
                    </h3>
                  </div>
                  <span className="text-sm text-slate-400">
                    {job.result.critical_observations?.length || 0} findings
                  </span>
                </div>

                {!job.result.critical_observations?.length ? (
                  <div className="text-center py-12">
                    <Shield className="w-12 h-12 text-green-400 mx-auto mb-4" />
                    <h4 className="text-lg font-medium text-white mb-2">
                      No Critical Observations
                    </h4>
                    <p className="text-slate-400">
                      The video analysis did not detect any concerning behaviors.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {job.result.critical_observations.map((obs, index) => (
                      <motion.div
                        key={index}
                        className="border border-slate-700/50 rounded-xl overflow-hidden"
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <button
                          onClick={() => toggleObservation(index)}
                          className="w-full p-4 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
                        >
                          <div className="flex items-center gap-4">
                            <div
                              className="w-10 h-10 rounded-lg flex items-center justify-center"
                              style={{
                                backgroundColor: `${getRiskColor(
                                  obs.risk_level
                                )}20`,
                              }}
                            >
                              <Car
                                className="w-5 h-5"
                                style={{ color: getRiskColor(obs.risk_level) }}
                              />
                            </div>
                            <div className="text-left">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-white">
                                  {obs.behavior_type}
                                </span>
                                <RiskBadge
                                  level={obs.risk_level as any}
                                  size="sm"
                                />
                              </div>
                              <p className="text-sm text-slate-400">
                                Vehicle: {obs.vehicle_id} • Confidence:{' '}
                                {obs.confidence}
                              </p>
                            </div>
                          </div>
                          {expandedObservations.has(index) ? (
                            <ChevronUp className="w-5 h-5 text-slate-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-slate-400" />
                          )}
                        </button>

                        {expandedObservations.has(index) && (
                          <motion.div
                            className="px-4 pb-4 pt-2 border-t border-slate-700/30"
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                          >
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div>
                                <p className="text-sm text-slate-400 mb-1">
                                  Description
                                </p>
                                <p className="text-white">{obs.description}</p>
                              </div>
                              <div>
                                <p className="text-sm text-slate-400 mb-1">
                                  Evidence
                                </p>
                                <p className="text-white">{obs.evidence}</p>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                )}
              </Card>
            </motion.div>
          </>
        )}
      </div>
    </div>
  );
};
