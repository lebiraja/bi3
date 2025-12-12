import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/agent_service.dart';
import '../services/preferences_service.dart';
import '../config.dart';
import 'incident_detail_screen.dart';
import 'settings_screen.dart';
import 'logs_screen.dart';

/// Home screen with dashboard and quick actions
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    _initializeAgent();
  }

  Future<void> _initializeAgent() async {
    final agent = Provider.of<AgentService>(context, listen: false);
    await agent.initialize();
    await agent.connect();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('BI3 Incident Agent'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          Consumer<AgentService>(
            builder: (context, agent, child) {
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Icon(
                  agent.isConnected ? Icons.cloud_done : Icons.cloud_off,
                  color: agent.isConnected ? Colors.green : Colors.red,
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.article_outlined),
            tooltip: 'View Logs',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const LogsScreen(),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const SettingsScreen(),
                ),
              );
            },
          ),
        ],
      ),
      body: Consumer<AgentService>(
        builder: (context, agent, child) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Connection Status Card
                _buildStatusCard(agent),
                const SizedBox(height: 16),

                // Emergency Actions Card
                _buildEmergencyActionsCard(agent),
                const SizedBox(height: 16),

                // Active Incident Card
                if (agent.activeIncident != null) ...[
                  _buildActiveIncidentCard(agent),
                  const SizedBox(height: 16),
                ],

                // Test Actions Card
                _buildTestActionsCard(agent),
                const SizedBox(height: 16),

                // Recent Incidents
                _buildIncidentsList(agent),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildStatusCard(AgentService agent) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.security,
                  size: 32,
                  color: agent.isConnected ? Colors.green : Colors.grey,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Incident Orchestrator Agent',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        agent.isConnected
                            ? 'Connected to server'
                            : 'Disconnected',
                        style: TextStyle(
                          color: agent.isConnected ? Colors.green : Colors.red,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(),
            FutureBuilder<String>(
              future: PreferencesService.getServerUrl(),
              builder: (context, snapshot) {
                return Text(
                  'Server: ${snapshot.data ?? AppConfig.defaultBaseUrl}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.blue.shade700,
                  ),
                );
              },
            ),
            const SizedBox(height: 4),
            Text(
              agent.deviceId.isNotEmpty 
                  ? 'Device ID: ${agent.deviceId.substring(0, 8)}...'
                  : 'Device ID: Initializing...',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmergencyActionsCard(AgentService agent) {
    return Card(
      color: Colors.red.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '🚨 Emergency SMS Alerts',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Colors.red.shade800,
                  ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () async {
                  // Send emergency SMS to police
                  final success = await agent.smsService.sendSms(
                    '+919535879330',
                    '🚨 EMERGENCY ALERT\n\nManual emergency alert triggered from BI3 mobile app.\n\nDevice: ${agent.deviceId.substring(0, 8)}\nTime: ${DateTime.now().toLocal()}\n\nImmediate response required.',
                  );
                  
                  if (success) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('✅ Emergency SMS sent to police'),
                        backgroundColor: Colors.green,
                      ),
                    );
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('❌ Failed to send emergency SMS'),
                        backgroundColor: Colors.red,
                      ),
                    );
                  }
                },
                icon: const Icon(Icons.sms, size: 24),
                label: const Text('Send Emergency SMS'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Sends SMS alert to emergency services',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.red.shade700,
                  ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActiveIncidentCard(AgentService agent) {
    final incident = agent.activeIncident!;
    final riskColor = _getRiskColor(incident.enhancedReport.riskScore);

    return Card(
      color: riskColor.withOpacity(0.1),
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => IncidentDetailScreen(incident: incident),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.warning, color: riskColor),
                  const SizedBox(width: 8),
                  Text(
                    'Active Incident',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Spacer(),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: riskColor,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      'Risk: ${incident.enhancedReport.riskScore}/10',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                incident.vlmSummary.incidentType.replaceAll('_', ' ').toUpperCase(),
                style: Theme.of(context).textTheme.titleSmall,
              ),
              Text(
                'Status: ${incident.finalStatus}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              Text(
                'Actions: ${incident.actionPlan.length}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => agent.clearActiveIncident(),
                    child: const Text('Dismiss'),
                  ),
                  TextButton(
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              IncidentDetailScreen(incident: incident),
                        ),
                      );
                    },
                    child: const Text('View Details'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTestActionsCard(AgentService agent) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '🧪 Test Actions',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: agent.isConnected
                  ? () async {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Creating test incident...')),
                      );
                      final incident = await agent.createTestIncident();
                      if (incident != null && mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              'Incident created: ${incident.incidentId}',
                            ),
                            backgroundColor: Colors.green,
                          ),
                        );
                      }
                    }
                  : null,
              icon: const Icon(Icons.add_alert),
              label: const Text('Create Test Incident'),
            ),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: () async {
                await agent.ttsService.speakEmergency(
                  'This is a test announcement from the Incident Agent.',
                );
              },
              icon: const Icon(Icons.volume_up),
              label: const Text('Test TTS'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIncidentsList(AgentService agent) {
    if (agent.incidents.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            children: [
              Icon(Icons.inbox, size: 48, color: Colors.grey.shade400),
              const SizedBox(height: 8),
              Text(
                'No incidents yet',
                style: TextStyle(color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
      );
    }

    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              'Recent Incidents (${agent.incidents.length})',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          const Divider(height: 1),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: agent.incidents.length.clamp(0, 5),
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final incident = agent.incidents[index];
              return ListTile(
                leading: CircleAvatar(
                  backgroundColor: _getRiskColor(
                    incident.enhancedReport.riskScore,
                  ).withOpacity(0.2),
                  child: Text(
                    '${incident.enhancedReport.riskScore}',
                    style: TextStyle(
                      color: _getRiskColor(incident.enhancedReport.riskScore),
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                title: Text(incident.vlmSummary.incidentType.replaceAll('_', ' ')),
                subtitle: Text(incident.finalStatus),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => IncidentDetailScreen(incident: incident),
                    ),
                  );
                },
              );
            },
          ),
        ],
      ),
    );
  }

  Color _getRiskColor(int riskScore) {
    if (riskScore >= 8) return Colors.red;
    if (riskScore >= 6) return Colors.orange;
    if (riskScore >= 4) return Colors.amber;
    return Colors.green;
  }
}
  