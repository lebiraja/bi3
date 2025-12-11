import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../services/agent_service.dart';

/// Screen showing incident details and action execution
class IncidentDetailScreen extends StatelessWidget {
  final Incident incident;

  const IncidentDetailScreen({super.key, required this.incident});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Incident ${incident.incidentId.substring(0, 8)}'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Risk Score Header
            _buildRiskHeader(context),
            const SizedBox(height: 16),

            // Incident Details
            _buildDetailsCard(context),
            const SizedBox(height: 16),

            // Action Plan
            _buildActionPlanCard(context),
            const SizedBox(height: 16),

            // Quick Actions
            _buildQuickActionsCard(context),
            const SizedBox(height: 16),

            // Audit Log
            _buildAuditCard(context),
          ],
        ),
      ),
    );
  }

  Widget _buildRiskHeader(BuildContext context) {
    final riskScore = incident.enhancedReport.riskScore;
    final color = _getRiskColor(riskScore);

    return Card(
      color: color.withOpacity(0.1),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(40),
              ),
              child: Center(
                child: Text(
                  '$riskScore',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    incident.vlmSummary.incidentType
                        .replaceAll('_', ' ')
                        .toUpperCase(),
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  Text(
                    'Confidence: ${(incident.vlmSummary.confidence * 100).toStringAsFixed(0)}%',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  Text(
                    'Status: ${incident.finalStatus.toUpperCase()}',
                    style: TextStyle(
                      color: _getStatusColor(incident.finalStatus),
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailsCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '📋 Details',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Divider(),
            _buildDetailRow('Incident ID', incident.incidentId),
            if (incident.location != null)
              _buildDetailRow(
                'Location',
                '${incident.location!.lat.toStringAsFixed(4)}, '
                    '${incident.location!.lon.toStringAsFixed(4)}',
              ),
            if (incident.vlmSummary.vehiclesInvolved != null)
              _buildDetailRow(
                'Vehicles Involved',
                '${incident.vlmSummary.vehiclesInvolved}',
              ),
            if (incident.vlmSummary.description != null)
              _buildDetailRow('Description', incident.vlmSummary.description!),
            if (incident.enhancedReport.executiveSummary != null)
              _buildDetailRow(
                'Summary',
                incident.enhancedReport.executiveSummary!,
              ),
            if (incident.operatorMessage != null)
              _buildDetailRow(
                'Operator Message',
                incident.operatorMessage!,
                isWarning: true,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value, {bool isWarning = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: isWarning ? Colors.orange : null,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: isWarning ? Colors.orange.shade800 : null,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionPlanCard(BuildContext context) {
    if (incident.actionPlan.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Icon(Icons.check_circle, size: 48, color: Colors.grey.shade400),
              const SizedBox(height: 8),
              Text(
                'No actions pending',
                style: TextStyle(color: Colors.grey.shade600),
              ),
            ],
          ),
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '📞 Action Plan (${incident.actionPlan.length})',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Divider(),
            ...incident.actionPlan.map((action) => _buildActionItem(context, action)),
          ],
        ),
      ),
    );
  }

  Widget _buildActionItem(BuildContext context, ActionItem action) {
    final icon = _getActionIcon(action.type);
    final statusColor = _getActionStatusColor(action.status);

    return Consumer<AgentService>(
      builder: (context, agent, child) {
        return Card(
          margin: const EdgeInsets.symmetric(vertical: 4),
          child: ListTile(
            leading: Icon(icon, color: statusColor),
            title: Text('${action.type.toUpperCase()} → ${action.targetRole}'),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Number: ${action.number}'),
                Text(
                  'Status: ${action.status} (${action.attempts} attempts)',
                  style: TextStyle(color: statusColor),
                ),
              ],
            ),
            trailing: action.status == 'pending'
                ? IconButton(
                    icon: const Icon(Icons.play_arrow, color: Colors.green),
                    onPressed: () => agent.executeAction(action),
                  )
                : Icon(
                    action.status == 'acknowledged' 
                        ? Icons.check_circle 
                        : Icons.error,
                    color: statusColor,
                  ),
          ),
        );
      },
    );
  }

  Widget _buildQuickActionsCard(BuildContext context) {
    return Consumer<AgentService>(
      builder: (context, agent, child) {
        return Card(
          color: Colors.blue.shade50,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '⚡ Quick Actions',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    ElevatedButton.icon(
                      onPressed: () => agent.callPolice(),
                      icon: const Icon(Icons.local_police),
                      label: const Text('Call Police'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blue,
                        foregroundColor: Colors.white,
                      ),
                    ),
                    ElevatedButton.icon(
                      onPressed: () => agent.callAmbulance(),
                      icon: const Icon(Icons.local_hospital),
                      label: const Text('Call Ambulance'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                        foregroundColor: Colors.white,
                      ),
                    ),
                    ElevatedButton.icon(
                      onPressed: () {
                        agent.ttsService.speakEmergency(
                          agent.ttsService.generateEmergencyMessage(
                            incidentType: incident.vlmSummary.incidentType,
                            riskScore: incident.enhancedReport.riskScore,
                          ),
                        );
                      },
                      icon: const Icon(Icons.volume_up),
                      label: const Text('Announce'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.purple,
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildAuditCard(BuildContext context) {
    if (incident.audit.isEmpty) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '📜 Audit Log (${incident.audit.length})',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Divider(),
            ...incident.audit.take(10).map((entry) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 50,
                    child: Text(
                      entry.ts.substring(11, 19),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          entry.step,
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        Text(
                          entry.outcome,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            )),
            if (incident.audit.length > 10)
              Text(
                '... and ${incident.audit.length - 10} more entries',
                style: Theme.of(context).textTheme.bodySmall,
              ),
          ],
        ),
      ),
    );
  }

  Color _getRiskColor(int riskScore) {
    if (riskScore >= 8) return Colors.red;
    if (riskScore >= 6) return Colors.orange;
    if (riskScore >= 4) return Colors.amber;
    return Colors.green;
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'dispatched':
        return Colors.green;
      case 'escalated':
        return Colors.orange;
      case 'queued_for_review':
        return Colors.blue;
      default:
        return Colors.grey;
    }
  }

  IconData _getActionIcon(String type) {
    switch (type) {
      case 'call':
        return Icons.phone;
      case 'sms':
        return Icons.sms;
      case 'notify':
        return Icons.notifications;
      default:
        return Icons.help;
    }
  }

  Color _getActionStatusColor(String status) {
    switch (status) {
      case 'acknowledged':
        return Colors.green;
      case 'sent':
        return Colors.blue;
      case 'pending':
        return Colors.grey;
      case 'failed':
        return Colors.red;
      case 'escalated':
        return Colors.orange;
      default:
        return Colors.grey;
    }
  }
}
