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

/// Main service that orchestrates all agent functionality
class AgentService extends ChangeNotifier {
  final LoggerService logger;
  late final ApiService apiService;
  late final TtsService ttsService;
  late final CallService callService;
  late final SmsService smsService;
  late final WebSocketService wsService;

  String _deviceId = '';
  bool _isInitialized = false;
  bool _isConnected = false;
  List<Incident> _incidents = [];
  Incident? _activeIncident;

  AgentService({required this.logger});

  // Getters
  String get deviceId => _deviceId;
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
    callService = CallService(apiService: apiService, deviceId: _deviceId);
    smsService = SmsService(apiService: apiService, deviceId: _deviceId);
    wsService = WebSocketService(deviceId: _deviceId, baseUrl: serverUrl, logger: logger);

    // Initialize TTS
    await ttsService.initialize();
    logger.success('✅ TTS service initialized');

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

    // Register device
    final device = DeviceInfo(
      deviceId: _deviceId,
      pushToken: 'flutter-app-token-$_deviceId',
    );
    await apiService.registerDevice(device);
    logger.success('✅ Device registered');

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
        case 'INITIATE_CALL':
          final number = commandData['number'] as String?;
          final spokenMessage = commandData['spoken_message'] as String?;
          
          if (number != null) {
            logger.info('📞 Initiating call to $number');
            
            // Speak the message if provided
            if (spokenMessage != null) {
              logger.info('🔊 Speaking message: $spokenMessage');
              await ttsService.speakEmergency(spokenMessage);
            }
            
            // Initiate the call
            final success = await callService.makeCall(number);
            
            if (success) {
              logger.success('✅ Call initiated successfully to $number');
            } else {
              logger.error('❌ Failed to initiate call to $number');
            }
            
            // Send callback to server
            if (actionId != null) {
              await apiService.sendActionCallback(
                actionId: actionId,
                deviceId: _deviceId,
                status: success ? 'sent' : 'failed',
                result: success ? 'Call initiated successfully' : 'Failed to initiate call',
              );
            }
          }
          break;

        case 'SEND_SMS':
          final number = commandData['number'] as String?;
          final message = commandData['message'] as String?;
          
          if (number != null && message != null) {
            logger.info('📧 Sending SMS to $number');
            
            final success = await smsService.sendSms(number, message);
            
            if (success) {
              logger.success('✅ SMS sent successfully to $number');
            } else {
              logger.error('❌ Failed to send SMS to $number');
            }
            
            // Send callback to server
            if (actionId != null) {
              await apiService.sendActionCallback(
                actionId: actionId,
                deviceId: _deviceId,
                status: success ? 'sent' : 'failed',
                result: success ? 'SMS sent successfully' : 'Failed to send SMS',
              );
            }
          }
          break;

        default:
          logger.warning('⚠️ Unknown command: $command');
          if (actionId != null) {
            await apiService.sendActionCallback(
              actionId: actionId,
              deviceId: _deviceId,
              status: 'failed',
              result: 'Unknown command type',
            );
          }
      }
    } catch (e) {
      logger.error('❌ Error handling action command: $e');
      if (actionId != null) {
        await apiService.sendActionCallback(
          actionId: actionId,
          deviceId: _deviceId,
          status: 'failed',
          errorMessage: 'Error: $e',
        );
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
