import 'package:url_launcher/url_launcher.dart';
import '../config.dart';
import '../models/models.dart';
import 'api_service.dart';

/// Service for making phone calls and tracking call state
class CallService {
  final ApiService _apiService;
  final String deviceId;

  CallService({
    required ApiService apiService,
    required this.deviceId,
  }) : _apiService = apiService;

  /// Make a phone call to the specified number
  Future<bool> makeCall(String phoneNumber) async {
    final Uri callUri = Uri(scheme: 'tel', path: phoneNumber);
    
    try {
      if (await canLaunchUrl(callUri)) {
        await launchUrl(callUri);
        return true;
      }
      print('Cannot launch call URL');
      return false;
    } catch (e) {
      print('Call error: $e');
      return false;
    }
  }

  /// Execute a call action and report result
  Future<bool> executeCallAction(ActionItem action) async {
    // Make the call
    final callInitiated = await makeCall(action.number);
    
    // For now, we assume call was made (in production, use telephony plugin)
    final callback = MobileCallback(
      actionId: action.actionId,
      deviceId: deviceId,
      status: callInitiated ? 'sent' : 'failed',
      callState: callInitiated ? 'CALL_STATE_OFFHOOK' : 'CALL_STATE_IDLE',
      timestamp: DateTime.now().toUtc().toIso8601String(),
      errorMessage: callInitiated ? null : 'Failed to initiate call',
    );

    // Send callback to server
    await _apiService.sendCallback(callback);
    
    return callInitiated;
  }

  /// Make emergency call to police
  Future<bool> callPolice() async {
    return await makeCall(AppConfig.policeNumber);
  }

  /// Make emergency call to ambulance
  Future<bool> callAmbulance() async {
    return await makeCall(AppConfig.ambulanceNumber);
  }
}

/// Service for sending SMS messages
class SmsService {
  final ApiService _apiService;
  final String deviceId;

  SmsService({
    required ApiService apiService,
    required this.deviceId,
  }) : _apiService = apiService;

  /// Send SMS to the specified number
  Future<bool> sendSms(String phoneNumber, String message) async {
    // Encode message for URL
    final encodedMessage = Uri.encodeComponent(message);
    final Uri smsUri = Uri.parse('sms:$phoneNumber?body=$encodedMessage');
    
    try {
      if (await canLaunchUrl(smsUri)) {
        await launchUrl(smsUri);
        return true;
      }
      print('Cannot launch SMS URL');
      return false;
    } catch (e) {
      print('SMS error: $e');
      return false;
    }
  }

  /// Execute an SMS action and report result
  Future<bool> executeSmsAction(ActionItem action) async {
    // Send the SMS
    final smsSent = await sendSms(action.number, action.text);
    
    // Report callback
    final callback = MobileCallback(
      actionId: action.actionId,
      deviceId: deviceId,
      status: smsSent ? 'sent' : 'failed',
      timestamp: DateTime.now().toUtc().toIso8601String(),
      errorMessage: smsSent ? null : 'Failed to send SMS',
    );

    await _apiService.sendCallback(callback);
    
    return smsSent;
  }

  /// Generate SMS content for incident
  String generateSmsContent(Incident incident) {
    final buffer = StringBuffer();
    buffer.writeln('🚨 TRAFFIC INCIDENT ALERT');
    buffer.writeln('ID: ${incident.incidentId.substring(0, 8)}');
    buffer.writeln('Type: ${incident.vlmSummary.incidentType}');
    buffer.writeln('Severity: ${incident.enhancedReport.riskScore}/10');
    
    if (incident.location != null) {
      buffer.writeln('Location: (${incident.location!.lat.toStringAsFixed(4)}, '
          '${incident.location!.lon.toStringAsFixed(4)})');
    }
    
    if (incident.enhancedReport.executiveSummary != null) {
      final summary = incident.enhancedReport.executiveSummary!;
      if (summary.length > 100) {
        buffer.writeln('Summary: ${summary.substring(0, 100)}...');
      } else {
        buffer.writeln('Summary: $summary');
      }
    }
    
    return buffer.toString();
  }
}
