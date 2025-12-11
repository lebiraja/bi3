/// Data models for the Incident Orchestrator Agent

/// Location model
class Location {
  final double lat;
  final double lon;

  Location({required this.lat, required this.lon});

  factory Location.fromJson(Map<String, dynamic> json) {
    return Location(
      lat: (json['lat'] as num).toDouble(),
      lon: (json['lon'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {'lat': lat, 'lon': lon};
}

/// VLM Summary from analysis
class VLMSummary {
  final double confidence;
  final String incidentType;
  final String? description;
  final int? vehiclesInvolved;
  final List<String>? recommendedAlerts;
  final bool ambiguous;

  VLMSummary({
    required this.confidence,
    required this.incidentType,
    this.description,
    this.vehiclesInvolved,
    this.recommendedAlerts,
    this.ambiguous = false,
  });

  factory VLMSummary.fromJson(Map<String, dynamic> json) {
    return VLMSummary(
      confidence: (json['confidence'] as num).toDouble(),
      incidentType: json['incident_type'] ?? 'unknown',
      description: json['description'],
      vehiclesInvolved: json['vehicles_involved'],
      recommendedAlerts: (json['recommended_alerts'] as List<dynamic>?)
          ?.map((e) => e.toString())
          .toList(),
      ambiguous: json['ambiguous'] ?? false,
    );
  }
}

/// Enhanced report data
class EnhancedReport {
  final String reportText;
  final int riskScore;
  final String? executiveSummary;

  EnhancedReport({
    required this.reportText,
    required this.riskScore,
    this.executiveSummary,
  });

  factory EnhancedReport.fromJson(Map<String, dynamic> json) {
    return EnhancedReport(
      reportText: json['report_text'] ?? '',
      riskScore: json['risk_score'] ?? 0,
      executiveSummary: json['executive_summary'],
    );
  }
}

/// Action plan item
class ActionItem {
  final String actionId;
  final String type; // call, sms, notify
  final String targetRole; // ambulance, police, traffic_control
  final String number;
  final String text;
  String status; // pending, sent, acknowledged, failed, escalated
  int attempts;
  Map<String, dynamic>? lastResult;

  ActionItem({
    required this.actionId,
    required this.type,
    required this.targetRole,
    required this.number,
    required this.text,
    this.status = 'pending',
    this.attempts = 0,
    this.lastResult,
  });

  factory ActionItem.fromJson(Map<String, dynamic> json) {
    return ActionItem(
      actionId: json['action_id'] ?? '',
      type: json['type'] ?? '',
      targetRole: json['target_role'] ?? '',
      number: json['number'] ?? '',
      text: json['text'] ?? '',
      status: json['status'] ?? 'pending',
      attempts: json['attempts'] ?? 0,
      lastResult: json['last_result'],
    );
  }

  Map<String, dynamic> toJson() => {
        'action_id': actionId,
        'type': type,
        'target_role': targetRole,
        'number': number,
        'text': text,
        'status': status,
        'attempts': attempts,
        'last_result': lastResult,
      };
}

/// Audit entry
class AuditEntry {
  final String ts;
  final String actor;
  final String step;
  final String outcome;
  final String? actionId;

  AuditEntry({
    required this.ts,
    required this.actor,
    required this.step,
    required this.outcome,
    this.actionId,
  });

  factory AuditEntry.fromJson(Map<String, dynamic> json) {
    return AuditEntry(
      ts: json['ts'] ?? '',
      actor: json['actor'] ?? '',
      step: json['step'] ?? '',
      outcome: json['outcome'] ?? '',
      actionId: json['action_id'],
    );
  }
}

/// Full incident data
class Incident {
  final String incidentId;
  final VLMSummary vlmSummary;
  final EnhancedReport enhancedReport;
  final Location? location;
  final List<ActionItem> actionPlan;
  final String finalStatus;
  final List<AuditEntry> audit;
  final String? operatorMessage;

  Incident({
    required this.incidentId,
    required this.vlmSummary,
    required this.enhancedReport,
    this.location,
    this.actionPlan = const [],
    this.finalStatus = 'pending',
    this.audit = const [],
    this.operatorMessage,
  });

  factory Incident.fromJson(Map<String, dynamic> json) {
    // Handle both direct incident format and action_result format
    final actionResult = json['action_result'] ?? json;
    
    return Incident(
      incidentId: actionResult['incident_id'] ?? json['incident_id'] ?? '',
      vlmSummary: json['vlm_summary'] != null
          ? VLMSummary.fromJson(json['vlm_summary'])
          : VLMSummary(confidence: 0, incidentType: 'unknown'),
      enhancedReport: json['enhanced_report'] != null
          ? EnhancedReport.fromJson(json['enhanced_report'])
          : EnhancedReport(reportText: '', riskScore: 0),
      location:
          json['location'] != null ? Location.fromJson(json['location']) : null,
      actionPlan: (actionResult['action_plan'] as List<dynamic>?)
              ?.map((e) => ActionItem.fromJson(e))
              .toList() ??
          [],
      finalStatus: actionResult['final_status'] ?? 'pending',
      audit: (actionResult['audit'] as List<dynamic>?)
              ?.map((e) => AuditEntry.fromJson(e))
              .toList() ??
          [],
      operatorMessage: actionResult['operator_message'],
    );
  }

  /// Get risk level color
  String get riskLevel {
    if (enhancedReport.riskScore >= 8) return 'critical';
    if (enhancedReport.riskScore >= 6) return 'high';
    if (enhancedReport.riskScore >= 4) return 'medium';
    return 'low';
  }
}

/// Device info for registration
class DeviceInfo {
  final String deviceId;
  final String pushToken;
  final bool canMakeCalls;
  final bool canSendSms;
  final bool canReceivePush;

  DeviceInfo({
    required this.deviceId,
    required this.pushToken,
    this.canMakeCalls = true,
    this.canSendSms = true,
    this.canReceivePush = true,
  });

  Map<String, dynamic> toJson() => {
        'device_id': deviceId,
        'push_token': pushToken,
        'capabilities': {
          'calls': canMakeCalls,
          'sms': canSendSms,
          'push': canReceivePush,
        },
        'device_api_key': 'mobile-app-key-$deviceId',
      };
}

/// Mobile callback to report action results
class MobileCallback {
  final String actionId;
  final String deviceId;
  final String status;
  final String? callState;
  final int? durationSeconds;
  final String? errorMessage;
  final String timestamp;

  MobileCallback({
    required this.actionId,
    required this.deviceId,
    required this.status,
    this.callState,
    this.durationSeconds,
    this.errorMessage,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() => {
        'action_id': actionId,
        'device_id': deviceId,
        'status': status,
        'call_state': callState,
        'duration_seconds': durationSeconds,
        'error_message': errorMessage,
        'timestamp': timestamp,
      };
}
