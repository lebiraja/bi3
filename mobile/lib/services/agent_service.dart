import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import 'api_service.dart';
import 'tts_service.dart';
import 'call_sms_service.dart';
import 'websocket_service.dart';
import 'preferences_service.dart';
import 'logger_service.dart';
import 'phone_service.dart';  // NEW

/// Main service that orchestrates all agent functionality
class AgentService extends ChangeNotifier {
  final LoggerService logger;
  late final ApiService apiService;
  late final TtsService ttsService;
  late final CallService callService;
  late final SmsService smsService;
  late final WebSocketService wsService;
  late final PhoneService phoneService;  // NEW

  String _deviceId = '';
  String? _phoneNumber;  // NEW
  bool _isInitialized = false;
  bool _isConnected = false;
  List<Incident> _incidents = [];
  Incident? _activeIncident;

  AgentService({required this.logger});

  // Getters
  String get deviceId => _deviceId;
  String? get phoneNumber => _phoneNumber;  // NEW
  bool get isInitialized => _isInitialized;
  bool get isConnected => _isConnected;
  List<Incident> get incidents => _incidents;
  Incident? get activeIncident => _activeIncident;

  /// Initialize the agent service
  Future<void> initialize() async {
    if (_isInitialized) return;

    logger.info('🚀 Initializing agent service...');

    // Get or create device ID
    final prefs = await SharedPreferences.getInstance();
    _deviceId = prefs.getString('device_id') ?? '';
    if (_deviceId.isEmpty) {
      _deviceId = const Uuid().v4();
      await prefs.setString('device_id', _deviceId);
      logger.success('✅ Generated new device ID: ${_deviceId.substring(0, 8)}...');
    } else {
      logger.info('📱 Using existing device ID: ${_deviceId.substring(0, 8)}...');
    }

    // Get server URL from preferences
    final serverUrl = await PreferencesService.getServerUrl();
    logger.info('🌐 Server URL: $serverUrl');

    // Initialize services
    apiService = ApiService(baseUrl: serverUrl, logger: logger);
    ttsService = TtsService();
    phoneService = PhoneService();  // NEW
    
    // Load phone number from preferences
    _phoneNumber = await phoneService.getPhoneNumber();  // NEW
    if (_phoneNumber != null) {
      logger.success('✅ Phone number loaded: $_phoneNumber');
    } else {
      logger.warning('⚠️ No phone number set. Please configure in Settings.');
    }
    
    callService = CallService(
      apiService: apiService,
      deviceId: _deviceId,
      phoneNumber: _phoneNumber,  // NEW
    );
    smsService = SmsService(
      apiService: apiService,
      deviceId: _deviceId,
      phoneNumber: _phoneNumber,  // NEW
    );
    wsService = WebSocketService(deviceId: _deviceId, baseUrl: serverUrl, logger: logger);

    // Setup WebSocket callbacks
    wsService.onConnected = () {
      _isConnected = true;
      logger.success('✅ WebSocket connected');
      notifyListeners();
    };

    wsService.onDisconnected = () {
      _isConnected = false;
      logger.warning('⚠️ WebSocket disconnected');
      notifyListeners();
    };

    wsService.onActionPlanReceived = _handleActionPlan;
    wsService.onIncidentReceived = _handleNewIncident;
    wsService.onActionCommandReceived = _handleActionCommand;

    _isInitialized = true;
    logger.success('✅ Agent service initialized');
    notifyListeners();
  }

  /// Reinitialize the agent service with new server URL
  /// This should be called after changing server URL in settings
  Future<void> reinitialize() async {
    logger.info('🔄 Reinitializing agent service...');
    
    // Disconnect existing WebSocket
    if (_isConnected) {
      wsService.disconnect();
    }

    // Mark as not initialized to force re-initialization
    _isInitialized = false;
    _isConnected = false;
    notifyListeners();

    // Re-initialize with new settings
    await initialize();
    
    // Attempt to reconnect
    await connect();
  }

  /// Connect to server
  Future<bool> connect() async {
    logger.info('🔌 Attempting to connect to server...');
    
    // Check health first
    final isHealthy = await apiService.checkHealth();
    if (!isHealthy) {
      logger.error('❌ Health check failed');
      return false;
    }

    logger.success('✅ Health check passed');

    // Register device with phone number
    final device = DeviceInfo(
      deviceId: _deviceId,
      pushToken: 'flutter-app-token-$_deviceId',
      phoneNumber: _phoneNumber,  // NEW: Include phone number
    );
    await apiService.registerDevice(device);
    logger.success('✅ Device registered${_phoneNumber != null ? " with phone: $_phoneNumber" : ""}');

    // Connect WebSocket
    final connected = await wsService.connect();
    _isConnected = connected;
    notifyListeners();
    return connected;
  }

  /// Handle received action plan
  void _handleActionPlan(List<ActionItem> actions) async {
    if (actions.isEmpty) return;

    logger.info('📋 Received action plan with ${actions.length} actions');

    // Announce via TTS
    await ttsService.speakEmergency(
      'New action plan received with ${actions.length} actions',
    );

    // Execute actions
    for (final action in actions) {
      await executeAction(action);
    }

    notifyListeners();
  }

  /// Handle new incident
  void _handleNewIncident(Incident incident) async {
    logger.info('🚨 New incident received: ${incident.incidentId}');
    logger.info('   Type: ${incident.vlmSummary.incidentType}');
    logger.info('   Risk: ${incident.enhancedReport.riskScore}/100');
    
    _incidents.insert(0, incident);
    _activeIncident = incident;

    // Announce via TTS
    final message = ttsService.generateEmergencyMessage(
      incidentType: incident.vlmSummary.incidentType,
      riskScore: incident.enhancedReport.riskScore,
      location: incident.location != null
          ? '${incident.location!.lat}, ${incident.location!.lon}'
          : null,
    );
    await ttsService.speakEmergency(message);

    notifyListeners();
  }

  /// Handle individual action command from server
  void _handleActionCommand(Map<String, dynamic> commandData) async {
    logger.debug('📥 Handling action command: $commandData');
    
    final command = commandData['command'] as String?;
    final actionId = commandData['action_id'] as String?;
    
    if (command == null) {
      logger.warning('⚠️ No command specified in action');
      return;
    }

    logger.info('⚡ Executing command: $command');

    try {
      switch (command) {
        case 'SEND_SMS':
          final number = commandData['number'] as String?;
          final message = commandData['message'] as String?;
          
          if (number != null && message != null) {
            logger.info('📧 Sending SMS to $number');
            logger.info('📝 Message: $message');
            
            final success = await smsService.sendSms(number, message);
            
            if (success) {
              logger.success('✅ SMS sent successfully to $number');
            } else {
              logger.error('❌ Failed to send SMS to $number');
            }
            
            // Send callback to server
            // ✅ CORRECT: SMS uses 'sent' status (different from calls)
            if (actionId != null) {
              final callback = MobileCallback(
                actionId: actionId,
                deviceId: _deviceId,
                phoneNumber: _phoneNumber,  // NEW: Include phone number
                status: success ? 'sent' : 'failed',
                timestamp: DateTime.now().toUtc().toIso8601String(),
              );
              await apiService.sendActionCallback(callback);
              logger.success('✅ SMS callback sent: ${callback.status}');
            }
          }
          break;

        case 'NOTIFY':
          final title = commandData['title'] as String? ?? 'Notification';
          final message = commandData['message'] as String? ?? '';
          
          logger.info('🔔 Showing notification: $title');
          
          // For now, just log the notification
          // In production, use flutter_local_notifications
          logger.info('💬 $title: $message');
          
          // Send callback
          if (actionId != null) {
            final callback = MobileCallback(
              actionId: actionId,
              deviceId: _deviceId,
              phoneNumber: _phoneNumber,
              status: 'sent',
              timestamp: DateTime.now().toUtc().toIso8601String(),
            );
            await apiService.sendActionCallback(callback);
          }
          break;

        default:
          logger.warning('⚠️ Unknown command: $command');
          if (actionId != null) {
            final callback = MobileCallback(
              actionId: actionId,
              deviceId: _deviceId,
              phoneNumber: _phoneNumber,
              status: 'failed',
              errorMessage: 'Unknown command type',
              timestamp: DateTime.now().toUtc().toIso8601String(),
            );
            await apiService.sendActionCallback(callback);
          }
      }
    } catch (e) {
      logger.error('❌ Error handling action command: $e');
      if (actionId != null) {
        final callback = MobileCallback(
          actionId: actionId,
          deviceId: _deviceId,
          phoneNumber: _phoneNumber,
          status: 'failed',
          errorMessage: 'Error: $e',
          timestamp: DateTime.now().toUtc().toIso8601String(),
        );
        await apiService.sendActionCallback(callback);
      }
    }
  }

  /// Execute a single action
  Future<bool> executeAction(ActionItem action) async {
    switch (action.type) {
      case 'call':
        return await callService.executeCallAction(action);
      case 'sms':
        return await smsService.executeSmsAction(action);
      case 'notify':
        // Handle notification (just log for now)
        print('Notification: ${action.text}');
        return true;
      default:
        print('Unknown action type: ${action.type}');
        return false;
    }
  }

  /// Create and process a test incident
  Future<Incident?> createTestIncident() async {
    final incidentData = {
      'incident_id': 'test-${DateTime.now().millisecondsSinceEpoch}',
      'vlm_summary': {
        'confidence': 0.92,
        'incident_type': 'vehicle_collision',
        'description': 'Test collision for mobile app verification',
        'vehicles_involved': 2,
        'recommended_alerts': ['call', 'sms'],
        'ambiguous': false,
      },
      'enhanced_report': {
        'report_text': 'Test incident report',
        'risk_score': 8,
        'executive_summary': 'High-severity test incident',
      },
      'location': {
        'lat': 12.9716,
        'lon': 77.5946,
      },
      'history': [],
    };

    final incident = await apiService.createIncident(incidentData);
    if (incident != null) {
      _incidents.insert(0, incident);
      _activeIncident = incident;
      notifyListeners();
    }
    return incident;
  }

  /// Quick call police
  Future<void> callPolice() async {
    await ttsService.speakEmergency('Calling police');
    await callService.callPolice();
  }

  /// Quick call ambulance
  Future<void> callAmbulance() async {
    await ttsService.speakEmergency('Calling ambulance');
    await callService.callAmbulance();
  }

  /// Update phone number
  Future<bool> updatePhoneNumber(String phoneNumber) async {
    try {
      // Validate format
      if (!phoneService.isValidPhoneNumber(phoneNumber)) {
        logger.error('❌ Invalid phone number format: $phoneNumber');
        return false;
      }
      
      // Format to E.164
      final formatted = phoneService.formatPhoneNumber(phoneNumber);
      
      // Save to preferences
      final saved = await phoneService.savePhoneNumber(formatted);
      if (saved) {
        _phoneNumber = formatted;
        logger.success('✅ Phone number updated: $formatted');
        notifyListeners();
        
        // Re-register device with new phone number
        if (_isConnected) {
          final device = DeviceInfo(
            deviceId: _deviceId,
            pushToken: 'flutter-app-token-$_deviceId',
            phoneNumber: _phoneNumber,
          );
          await apiService.registerDevice(device);
          logger.success('✅ Device re-registered with new phone number');
        }
        
        return true;
      }
      return false;
    } catch (e) {
      logger.error('❌ Error updating phone number: $e');
      return false;
    }
  }

  /// Clear active incident
  void clearActiveIncident() {
    _activeIncident = null;
    notifyListeners();
  }

  @override
  void dispose() {
    wsService.dispose();
    ttsService.dispose();
    apiService.dispose();
    super.dispose();
  }
}
