import 'package:url_launcher/url_launcher.dart';
import '../config.dart';
import '../models/models.dart';
import 'api_service.dart';
import 'native_telephony_service.dart';  // NEW

/// Service for making phone calls and tracking call state
class CallService {
  final ApiService _apiService;
  final String deviceId;
  final String? phoneNumber;  // NEW
  final NativeTelephonyService nativeTelephony;  // PUBLIC - for audio mode access

  CallService({
    required ApiService apiService,
    required this.deviceId,
    this.phoneNumber,  // NEW
  }) : _apiService = apiService,
       nativeTelephony = NativeTelephonyService() {  // PUBLIC
    // Listen to call state changes
    nativeTelephony.onCallStateChanged = (state, number) {
      print('📞 Call state: $state for $number');
    };
  }

  /// Make a phone call to the specified number
  Future<bool> makeCall(String phoneNumber) async {
    try {
      // Use native telephony for automatic calling
      return await nativeTelephony.makeCall(phoneNumber);
    } catch (e) {
      print('❌ Call error: $e');
      return false;
    }
  }

  /// Execute a call action and report result
  Future<bool> executeCallAction(ActionItem action) async {
    // Make the call
    final callInitiated = await makeCall(action.number);
    
    // For now, we assume call was made (in production, use telephony plugin)
    // ✅ FIX: Use 'acknowledged' status for calls (backend expects this for answered calls)
    // Backend checks: result.status == ActionStatus.ACKNOWLEDGED (actions.py:203)
    final callback = MobileCallback(
      actionId: action.actionId,
      deviceId: deviceId,
      phoneNumber: phoneNumber,  // NEW: Include phone number
      status: callInitiated ? 'acknowledged' : 'failed',  // Changed from 'sent' to 'acknowledged'
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

/// Service for handling SMS messages
class SmsService {
  final ApiService _apiService;
  final String deviceId;
  final String? phoneNumber;  // NEW
  final NativeTelephonyService _nativeTelephony;  // NEW
  
  SmsService({
    required ApiService apiService,
    required this.deviceId,
    this.phoneNumber,  // NEW
  }) : _apiService = apiService,
       _nativeTelephony = NativeTelephonyService() {  // NEW
    // Listen to SMS sent events
    _nativeTelephony.onSMSSent = (number, success, error) {
      print('📧 SMS to $number: ${success ? "sent" : "failed"} ${error ?? ""}');
    };
  }

  /// Send SMS using native telephony (automatic, no user interaction)
  Future<bool> sendSms(String phoneNumber, String message) async {
    try {
      // Use native telephony for automatic SMS
      return await _nativeTelephony.sendSMS(phoneNumber, message);
    } catch (e) {
      print('❌ SMS error: $e');
      return false;
    }
  }

  /// Execute an SMS action and report result
  Future<bool> executeSmsAction(ActionItem action) async {
    // Send the SMS
    final smsSent = await sendSms(action.number, action.text);
    
    // Report callback
    // ✅ CORRECT: SMS uses 'sent' status (different from calls which use 'acknowledged')
    final callback = MobileCallback(
      actionId: action.actionId,
      deviceId: deviceId,
      phoneNumber: phoneNumber,  // NEW: Include phone number
      status: smsSent ? 'sent' : 'failed',  // Correct for SMS
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
