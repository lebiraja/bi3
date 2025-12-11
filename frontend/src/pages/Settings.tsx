import { useEffect, useState } from 'react';
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
import { getConfig, getHealth } from '../services/api';
import type { ConfigResponse, HealthResponse } from '../types/api';

export const Settings = () => {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [configData, healthData] = await Promise.all([
        getConfig(),
        getHealth(),
      ]);
      setConfig(configData);
      setHealth(healthData);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
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
              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse" />
                  <span className="text-white font-medium">Server Status</span>
                </div>
                <span className="text-green-400 font-medium">
                  {health?.status || 'Unknown'}
                </span>
              </div>

              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
                <span className="text-slate-400">Service</span>
                <span className="text-white">{health?.service || 'N/A'}</span>
              </div>

              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
                <span className="text-slate-400">Version</span>
                <span className="text-white font-mono">{health?.version || 'N/A'}</span>
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
              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      config?.mongodb_connected
                        ? 'bg-green-400 animate-pulse'
                        : 'bg-red-400'
                    }`}
                  />
                  <span className="text-white font-medium">MongoDB</span>
                </div>
                <span
                  className={`font-medium ${
                    config?.mongodb_connected ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {config?.mongodb_connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>

              {!config?.mongodb_connected && (
                <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
                  <p className="text-sm text-yellow-400">
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
              <div className="p-4 bg-slate-800/30 rounded-xl">
                <p className="text-sm text-slate-400 mb-1">Model</p>
                <p className="text-white font-mono text-sm">
                  {config?.vlm_model || 'Not configured'}
                </p>
              </div>

              <div className="p-4 bg-slate-800/30 rounded-xl">
                <p className="text-sm text-slate-400 mb-1">Provider</p>
                <div className="flex items-center gap-2">
                  <span className="text-white">OpenRouter</span>
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
              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
                <span className="text-slate-400">Frames per Second</span>
                <span className="text-white font-semibold">
                  {config?.frames_per_second || 0} FPS
                </span>
              </div>

              <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-xl">
                <span className="text-slate-400">Sample Interval</span>
                <span className="text-white font-semibold">
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
                    className="p-4 bg-slate-800/30 rounded-xl text-center"
                    whileHover={{ scale: 1.02 }}
                  >
                    <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-slate-700/50 flex items-center justify-center">
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
                    <p className="text-white font-medium capitalize">{name}</p>
                    <p className="text-sm text-slate-400">Class ID: {id}</p>
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
                  <tr className="border-b border-slate-700/50">
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">
                      Method
                    </th>
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">
                      Endpoint
                    </th>
                    <th className="text-left py-3 px-4 text-slate-400 font-medium">
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
                      className="border-b border-slate-800/50 hover:bg-slate-800/20"
                    >
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            api.method === 'GET'
                              ? 'bg-green-500/20 text-green-400'
                              : api.method === 'POST'
                              ? 'bg-blue-500/20 text-blue-400'
                              : 'bg-purple-500/20 text-purple-400'
                          }`}
                        >
                          {api.method}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <code className="text-sm text-slate-300 font-mono">
                          {api.endpoint}
                        </code>
                      </td>
                      <td className="py-3 px-4 text-slate-400">
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
