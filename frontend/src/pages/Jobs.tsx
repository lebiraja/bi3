import { useEffect, useState, useRef } from 'react';
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
import { useSearch } from '../contexts/SearchContext';
import { useNotifications } from '../contexts/NotificationContext';

type FilterStatus = 'all' | 'pending' | 'processing' | 'completed' | 'failed';

export const Jobs = () => {
  const { addNotification, addPageNotification } = useNotifications();
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterStatus>('all');
  const { searchQuery } = useSearch();
  const hasNotifiedRef = useRef(false);

  const fetchJobs = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const data = await listJobs();
      setJobs(data.jobs);
      
      if (!hasNotifiedRef.current) {
        addPageNotification('jobs', 'info', 'Jobs Loaded', `Viewing ${data.jobs.length} analysis jobs`);
        hasNotifiedRef.current = true;
      }
      
      if (showRefresh) {
        addNotification('success', 'Jobs Refreshed', `Found ${data.jobs.length} analysis jobs`);
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      if (!hasNotifiedRef.current) {
        addNotification('error', 'Failed to Load Jobs', 'Could not retrieve analysis jobs. Please try again.');
        hasNotifiedRef.current = true;
      }
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
    // Filter by status
    if (filter !== 'all' && job.status !== filter) return false;
    
    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        job.video_name.toLowerCase().includes(query) ||
        job.job_id.toLowerCase().includes(query)
      );
    }
    
    return true;
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
        return <Clock className="w-5 h-5 text-gray-500 dark:text-gray-400" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-600 dark:text-blue-400 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />;
      default:
        return <Video className="w-5 h-5 text-gray-500 dark:text-gray-400" />;
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
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div className="flex gap-2 p-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-sm overflow-x-auto w-full sm:w-auto">
          {[
            { key: 'all', label: 'All', icon: Video },
            { key: 'processing', label: 'Processing', icon: Loader2 },
            { key: 'completed', label: 'Completed', icon: CheckCircle },
            { key: 'failed', label: 'Failed', icon: XCircle },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setFilter(key as FilterStatus)}
              className={`flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 rounded-lg transition-all font-medium whitespace-nowrap ${
                filter === key
                  ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-md'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              <Icon className={`w-4 h-4 ${key === 'processing' && filter === key ? 'animate-spin' : ''}`} />
              <span className="text-sm sm:text-base">{label}</span>
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                  filter === key
                    ? 'bg-white/20 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
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
          className="w-full sm:w-auto"
        >
          Refresh
        </Button>
      </div>

      {/* Jobs List */}
      {sortedJobs.length === 0 ? (
        <Card className="text-center py-16 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-gray-800 dark:to-gray-700 border border-gray-200 dark:border-gray-600">
          <Video className="w-16 h-16 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            {searchQuery ? 'No matching videos' : filter === 'all' ? 'No jobs yet' : `No ${filter} jobs`}
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-6">
            {searchQuery
              ? 'Try a different search term'
              : filter === 'all'
              ? 'Upload a video to start your first analysis'
              : 'Try a different filter to see more jobs'}
          </p>
          {filter === 'all' && !searchQuery && (
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
                  className="group cursor-pointer bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {/* Status Icon */}
                      <div
                        className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                          job.status === 'completed'
                            ? 'bg-gradient-to-br from-green-100 to-emerald-100 dark:from-green-500/20 dark:to-emerald-500/20'
                            : job.status === 'processing'
                            ? 'bg-gradient-to-br from-blue-100 to-indigo-100 dark:from-blue-500/20 dark:to-indigo-500/20'
                            : job.status === 'failed'
                            ? 'bg-gradient-to-br from-red-100 to-rose-100 dark:from-red-500/20 dark:to-rose-500/20'
                            : 'bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-700/50 dark:to-gray-600/50'
                        }`}
                      >
                        {getStatusIcon(job.status)}
                      </div>

                      {/* Job Info */}
                      <div>
                        <div className="flex items-center gap-3">
                          <h3 className="font-semibold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                            {job.video_name}
                          </h3>
                          <StatusBadge status={job.status} size="sm" />
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-gray-500 dark:text-gray-400">
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
                          <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                            Error: {job.error}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Result Summary (for completed jobs) */}
                    <div className="flex items-center gap-6">
                      {job.status === 'completed' && job.result && (
                        <div className="flex items-center gap-6 text-sm">
                          <div className="text-center px-4 py-2 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                            <p className="text-gray-500 dark:text-gray-400 text-xs mb-1">Duration</p>
                            <p className="font-semibold text-gray-900 dark:text-white">
                              {job.result.total_seconds}s
                            </p>
                          </div>
                          <div className="text-center px-4 py-2 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
                            <p className="text-gray-500 dark:text-gray-400 text-xs mb-1">Risk Score</p>
                            <p
                              className={`font-semibold ${
                                job.result.avg_risk_score < 3
                                  ? 'text-green-600 dark:text-green-400'
                                  : job.result.avg_risk_score < 5
                                  ? 'text-yellow-600 dark:text-yellow-400'
                                  : 'text-red-600 dark:text-red-400'
                              }`}
                            >
                              {job.result.avg_risk_score.toFixed(1)}
                            </p>
                          </div>
                          <div className="text-center px-4 py-2 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-lg border border-green-200 dark:border-green-800">
                            <p className="text-gray-500 dark:text-gray-400 text-xs mb-1">Observations</p>
                            <p className="font-semibold text-gray-900 dark:text-white">
                              {job.result.critical_observations?.length || 0}
                            </p>
                          </div>
                        </div>
                      )}

                      <ChevronRight className="w-5 h-5 text-gray-400 dark:text-gray-500 group-hover:text-blue-600 dark:group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
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
