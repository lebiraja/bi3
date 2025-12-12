import { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Settings as SettingsIcon,
  Database,
  Cpu,
  Video,
  Clock,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { Header } from '../components/layout';
import { Card, Button } from '../components/ui';
import { SystemStatusCard } from '../components/ui/StatusIndicator';
import { useNotifications } from '../contexts/NotificationContext';
import { getConfig, getHealth } from '../services/api';
import type { ConfigResponse, HealthResponse } from '../types/api';

export const Settings = () => {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { addNotification, addPageNotification } = useNotifications();
  const hasNotifiedRef = useRef(false);

  const fetchData = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [configData, healthData] = await Promise.all([
        getConfig(),
        getHealth(),
      ]);
      setConfig(configData);
      setHealth(healthData);
      
      if (showRefresh) {
        addNotification('success', 'Settings Refreshed', 'System configuration updated successfully');
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error);
      if (!hasNotifiedRef.current) {
        addNotification('error', 'Settings Error', 'Failed to fetch system configuration');
        hasNotifiedRef.current = true;
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    if (!hasNotifiedRef.current) {
      addPageNotification('settings', 'info', 'Settings Loaded', 'Viewing system configuration and status');
      hasNotifiedRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        title="Settings"
        subtitle="System configuration and status"
      />

      {/* System Status Overview */}
      <motion.div
        className="mb-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <SystemStatusCard
          title="System Status"
          items={[
            { name: 'API Server', status: health?.status === 'healthy' ? 'online' : 'offline' },
            { name: 'MongoDB', status: config?.mongodb_connected ? 'online' : 'offline' },
            { name: 'VLM Service', status: config?.vlm_model ? 'online' : 'offline' },
          ]}
        />
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* API Status */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                  <Cpu className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold text-white">API Status</h3>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => fetchData(true)}
                loading={refreshing}
                icon={<RefreshCw className="w-4 h-4" />}
              >
                Refresh
              </Button>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse shadow-sm shadow-green-300" />
                  <span className="text-gray-900 font-medium">Server Status</span>
                </div>
                <span className="text-green-700 font-semibold">
                  {health?.status || 'Unknown'}
                </span>
              </div>

              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-xl shadow-sm">
                <span className="text-gray-600 font-medium">Service</span>
                <span className="text-gray-900 font-semibold">{health?.service || 'N/A'}</span>
              </div>

              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-100 rounded-xl shadow-sm">
                <span className="text-gray-600 font-medium">Version</span>
                <span className="text-gray-900 font-mono font-semibold">{health?.version || 'N/A'}</span>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Database Status */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                <Database className="w-5 h-5 text-green-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Database</h3>
            </div>

            <div className="space-y-4">
              <div className={`flex items-center justify-between p-4 rounded-xl shadow-sm border ${
                config?.mongodb_connected
                  ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200'
                  : 'bg-gradient-to-r from-red-50 to-rose-50 border-red-200'
              }`}>
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      config?.mongodb_connected
                        ? 'bg-green-500 animate-pulse shadow-sm shadow-green-300'
                        : 'bg-red-500'
                    }`}
                  />
                  <span className="text-gray-900 font-medium">MongoDB</span>
                </div>
                <span
                  className={`font-semibold ${
                    config?.mongodb_connected ? 'text-green-700' : 'text-red-700'
                  }`}
                >
                  {config?.mongodb_connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>

              {!config?.mongodb_connected && (
                <div className="p-4 bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-xl shadow-sm">
                  <p className="text-sm text-amber-700 font-medium">
                    MongoDB is not connected. Analysis results will not be persisted.
                  </p>
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* VLM Configuration */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">VLM Configuration</h3>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-100 rounded-xl shadow-sm">
                <p className="text-sm text-purple-600 font-medium mb-1">Model</p>
                <p className="text-gray-900 font-mono text-sm font-semibold">
                  {config?.vlm_model || 'Not configured'}
                </p>
              </div>

              <div className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-xl shadow-sm">
                <p className="text-sm text-blue-600 font-medium mb-1">Provider</p>
                <div className="flex items-center gap-2">
                  <span className="text-gray-900 font-semibold">OpenRouter</span>
                  <a
                    href="https://openrouter.ai"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:text-blue-300"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Frame Sampling */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Card>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                <Clock className="w-5 h-5 text-yellow-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Frame Sampling</h3>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-100 rounded-xl shadow-sm">
                <span className="text-gray-600 font-medium">Frames per Second</span>
                <span className="text-gray-900 font-bold">
                  {config?.frames_per_second || 0} FPS
                </span>
              </div>

              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-100 rounded-xl shadow-sm">
                <span className="text-gray-600 font-medium">Sample Interval</span>
                <span className="text-gray-900 font-bold">
                  Every {config?.sample_interval || 0} frames
                </span>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Vehicle Detection */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="lg:col-span-2"
        >
          <Card>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center">
                <Video className="w-5 h-5 text-cyan-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">
                Vehicle Detection Classes
              </h3>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {config?.vehicle_classes &&
                Object.entries(config.vehicle_classes).map(([id, name]) => (
                  <motion.div
                    key={id}
                    className="p-4 bg-gradient-to-br from-cyan-50 to-blue-50 border border-cyan-100 rounded-xl text-center shadow-sm hover:shadow-md transition-all"
                    whileHover={{ scale: 1.05, y: -2 }}
                  >
                    <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-gradient-to-br from-cyan-100 to-blue-100 flex items-center justify-center shadow-sm">
                      <span className="text-2xl">
                        {name === 'car'
                          ? '🚗'
                          : name === 'motorcycle'
                          ? '🏍️'
                          : name === 'bus'
                          ? '🚌'
                          : name === 'truck'
                          ? '🚛'
                          : '🚙'}
                      </span>
                    </div>
                    <p className="text-gray-900 font-semibold capitalize">{name}</p>
                    <p className="text-sm text-cyan-600 font-medium">Class ID: {id}</p>
                  </motion.div>
                ))}
            </div>
          </Card>
        </motion.div>

        {/* API Endpoints Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="lg:col-span-2"
        >
          <Card>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-slate-500/10 flex items-center justify-center">
                <SettingsIcon className="w-5 h-5 text-slate-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">API Endpoints</h3>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b-2 border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50">
                    <th className="text-left py-3 px-4 text-blue-700 font-semibold">
                      Method
                    </th>
                    <th className="text-left py-3 px-4 text-blue-700 font-semibold">
                      Endpoint
                    </th>
                    <th className="text-left py-3 px-4 text-blue-700 font-semibold">
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { method: 'GET', endpoint: '/', description: 'Health check' },
                    {
                      method: 'GET',
                      endpoint: '/api/config',
                      description: 'Get configuration',
                    },
                    {
                      method: 'POST',
                      endpoint: '/api/upload',
                      description: 'Upload video for analysis',
                    },
                    {
                      method: 'POST',
                      endpoint: '/api/analyze',
                      description: 'Analyze existing video',
                    },
                    {
                      method: 'GET',
                      endpoint: '/api/jobs',
                      description: 'List all jobs',
                    },
                    {
                      method: 'GET',
                      endpoint: '/api/jobs/{id}',
                      description: 'Get job status',
                    },
                    {
                      method: 'GET',
                      endpoint: '/api/jobs/{id}/result',
                      description: 'Get analysis result',
                    },
                    {
                      method: 'WS',
                      endpoint: '/ws/{job_id}',
                      description: 'Real-time progress updates',
                    },
                  ].map((api, index) => (
                    <tr
                      key={index}
                      className="border-b border-gray-100 hover:bg-gradient-to-r hover:from-blue-50 hover:to-indigo-50 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-1 rounded-md text-xs font-bold shadow-sm ${
                            api.method === 'GET'
                              ? 'bg-gradient-to-r from-green-100 to-emerald-100 text-green-700 border border-green-200'
                              : api.method === 'POST'
                              ? 'bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-700 border border-blue-200'
                              : 'bg-gradient-to-r from-purple-100 to-indigo-100 text-purple-700 border border-purple-200'
                          }`}
                        >
                          {api.method}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <code className="text-sm text-gray-800 font-mono font-semibold">
                          {api.endpoint}
                        </code>
                      </td>
                      <td className="py-3 px-4 text-gray-600">
                        {api.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  );
};
