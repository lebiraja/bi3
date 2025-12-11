import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Video,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import { Header } from '../components/layout';
import { Card, Button, StatusBadge, ProgressBar } from '../components/ui';
import { listJobs } from '../services/api';
import type { AnalysisJob } from '../types/api';
import { formatDistanceToNow } from 'date-fns';

type FilterStatus = 'all' | 'pending' | 'processing' | 'completed' | 'failed';

export const Jobs = () => {
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterStatus>('all');

  const fetchJobs = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const data = await listJobs();
      setJobs(data.jobs);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(() => fetchJobs(), 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredJobs = jobs.filter((job) => {
    if (filter === 'all') return true;
    return job.status === filter;
  });

  const sortedJobs = [...filteredJobs].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const stats = {
    all: jobs.length,
    pending: jobs.filter((j) => j.status === 'pending').length,
    processing: jobs.filter((j) => j.status === 'processing').length,
    completed: jobs.filter((j) => j.status === 'completed').length,
    failed: jobs.filter((j) => j.status === 'failed').length,
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-5 h-5 text-slate-400" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Video className="w-5 h-5 text-slate-400" />;
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

  return (
    <div>
      <Header
        title="Analysis Jobs"
        subtitle="View and manage all video analysis jobs"
      />

      {/* Filter Tabs */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex gap-2 p-1 bg-slate-800/50 rounded-xl">
          {[
            { key: 'all', label: 'All', icon: Video },
            { key: 'processing', label: 'Processing', icon: Loader2 },
            { key: 'completed', label: 'Completed', icon: CheckCircle },
            { key: 'failed', label: 'Failed', icon: XCircle },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setFilter(key as FilterStatus)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
                filter === key
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <Icon className={`w-4 h-4 ${key === 'processing' && filter === key ? 'animate-spin' : ''}`} />
              <span className="font-medium">{label}</span>
              <span
                className={`px-2 py-0.5 rounded-full text-xs ${
                  filter === key
                    ? 'bg-blue-500/30 text-blue-300'
                    : 'bg-slate-700/50 text-slate-400'
                }`}
              >
                {stats[key as keyof typeof stats]}
              </span>
            </button>
          ))}
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => fetchJobs(true)}
          loading={refreshing}
          icon={<RefreshCw className="w-4 h-4" />}
        >
          Refresh
        </Button>
      </div>

      {/* Jobs List */}
      {sortedJobs.length === 0 ? (
        <Card className="text-center py-16">
          <Video className="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">
            {filter === 'all' ? 'No jobs yet' : `No ${filter} jobs`}
          </h3>
          <p className="text-slate-400 mb-6">
            {filter === 'all'
              ? 'Upload a video to start your first analysis'
              : 'Try a different filter to see more jobs'}
          </p>
          {filter === 'all' && (
            <Link to="/upload">
              <Button variant="primary">Upload Video</Button>
            </Link>
          )}
        </Card>
      ) : (
        <div className="space-y-4">
          {sortedJobs.map((job, index) => (
            <motion.div
              key={job.job_id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Link to={`/jobs/${job.job_id}`}>
                <Card
                  hover
                  className="group cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {/* Status Icon */}
                      <div
                        className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                          job.status === 'completed'
                            ? 'bg-green-500/10'
                            : job.status === 'processing'
                            ? 'bg-blue-500/10'
                            : job.status === 'failed'
                            ? 'bg-red-500/10'
                            : 'bg-slate-700/50'
                        }`}
                      >
                        {getStatusIcon(job.status)}
                      </div>

                      {/* Job Info */}
                      <div>
                        <div className="flex items-center gap-3">
                          <h3 className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                            {job.video_name}
                          </h3>
                          <StatusBadge status={job.status} size="sm" />
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-slate-400">
                          <span>ID: {job.job_id}</span>
                          <span>•</span>
                          <span>
                            {formatDistanceToNow(new Date(job.created_at), {
                              addSuffix: true,
                            })}
                          </span>
                          {job.completed_at && (
                            <>
                              <span>•</span>
                              <span>
                                Completed{' '}
                                {formatDistanceToNow(new Date(job.completed_at), {
                                  addSuffix: true,
                                })}
                              </span>
                            </>
                          )}
                        </div>

                        {/* Progress bar for processing jobs */}
                        {job.status === 'processing' && (
                          <div className="mt-3 w-64">
                            <ProgressBar
                              progress={job.progress * 100}
                              size="sm"
                              showLabel={false}
                            />
                          </div>
                        )}

                        {/* Error message for failed jobs */}
                        {job.status === 'failed' && job.error && (
                          <p className="mt-2 text-sm text-red-400">
                            Error: {job.error}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Result Summary (for completed jobs) */}
                    <div className="flex items-center gap-6">
                      {job.status === 'completed' && job.result && (
                        <div className="flex items-center gap-6 text-sm">
                          <div className="text-center">
                            <p className="text-slate-400">Duration</p>
                            <p className="font-semibold text-white">
                              {job.result.total_seconds}s
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-slate-400">Risk Score</p>
                            <p
                              className={`font-semibold ${
                                job.result.avg_risk_score < 3
                                  ? 'text-green-400'
                                  : job.result.avg_risk_score < 5
                                  ? 'text-yellow-400'
                                  : 'text-red-400'
                              }`}
                            >
                              {job.result.avg_risk_score.toFixed(1)}
                            </p>
                          </div>
                          <div className="text-center">
                            <p className="text-slate-400">Observations</p>
                            <p className="font-semibold text-white">
                              {job.result.critical_observations?.length || 0}
                            </p>
                          </div>
                        </div>
                      )}

                      <ChevronRight className="w-5 h-5 text-slate-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
                    </div>
                  </div>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
};
