import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../models/models.dart';
import 'preferences_service.dart';
import 'logger_service.dart';

/// API Service for communicating with the Incident Orchestrator Agent
class ApiService {
  final String baseUrl;
  final http.Client _client;
  final LoggerService logger;

  ApiService({String? baseUrl, http.Client? client, required this.logger})
      : baseUrl = baseUrl ?? AppConfig.defaultBaseUrl,
        _client = client ?? http.Client();
  
  /// Create ApiService with URL from preferences
  static Future<ApiService> create({http.Client? client, required LoggerService logger}) async {
    final serverUrl = await PreferencesService.getServerUrl();
    return ApiService(baseUrl: serverUrl, client: client, logger: logger);
  }

  /// Headers for API requests
  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  /// Check server health
  Future<bool> checkHealth() async {
    try {
      logger.debug('🔍 Checking server health...');
      final response = await _client.get(
        Uri.parse('$baseUrl${AppConfig.healthEndpoint}'),
        headers: _headers,
      );
      final healthy = response.statusCode == 200;
      if (healthy) {
        logger.success('✅ Server is healthy');
      } else {
        logger.error('❌ Server health check failed: ${response.statusCode}');
      }
      return healthy;
    } catch (e) {
      logger.error('❌ Health check error: $e');
      return false;
    }
  }

  /// Create/process a new incident
  Future<Incident?> createIncident(Map<String, dynamic> incidentData) async {
    try {
      logger.debug('📤 Creating incident...');
      final response = await _client.post(
        Uri.parse('$baseUrl${AppConfig.incidentsEndpoint}'),
        headers: _headers,
        body: jsonEncode(incidentData),
      );

      if (response.statusCode == 201 || response.statusCode == 200) {
        final data = jsonDecode(response.body);
        logger.success('✅ Incident created successfully');
        return Incident.fromJson(data);
      }
      logger.error('❌ Create incident failed: ${response.statusCode}');
      return null;
    } catch (e) {
      logger.error('❌ Create incident error: $e');
      return null;
    }
  }

  /// Get incident by ID
  Future<Incident?> getIncident(String incidentId) async {
    try {
      logger.debug('📥 Fetching incident $incidentId...');
      final response = await _client.get(
        Uri.parse('$baseUrl${AppConfig.incidentsEndpoint}/$incidentId'),
        headers: _headers,
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        logger.success('✅ Incident fetched successfully');
        return Incident.fromJson(data);
      }
      logger.error('❌ Get incident failed: ${response.statusCode}');
      return null;
    } catch (e) {
      logger.error('❌ Get incident error: $e');
      return null;
    }
  }

  /// Register device with server
  Future<bool> registerDevice(DeviceInfo device) async {
    try {
      logger.debug('📱 Registering device...');
      final response = await _client.post(
        Uri.parse('$baseUrl${AppConfig.devicesEndpoint}/register'),
        headers: _headers,
        body: jsonEncode(device.toJson()),
      );

      return response.statusCode == 201 || response.statusCode == 200;
    } catch (e) {
      logger.error('❌ Register device error: $e');
      return false;
    }
  }

  /// Send mobile callback after action execution
  Future<bool> sendCallback(MobileCallback callback) async {
    try {
      logger.debug('📤 Sending callback...');
      final response = await _client.post(
        Uri.parse('$baseUrl${AppConfig.callbackEndpoint}'),
        headers: _headers,
        body: jsonEncode(callback.toJson()),
      );

      if (response.statusCode == 200) {
        logger.success('✅ Callback sent successfully');
        return true;
      } else {
        logger.error('❌ Callback failed: ${response.statusCode}');
        return false;
      }
    } catch (e) {
      logger.error('❌ Send callback error: $e');
      return false;
    }
  }

  /// Send action callback to server
  Future<bool> sendActionCallback(MobileCallback callback) async {
    try {
      logger.debug('📤 Sending action callback for ${callback.actionId}...');
      final response = await _client.post(
        Uri.parse('$baseUrl${AppConfig.mobileCallbackEndpoint}'),
        headers: _headers,
        body: jsonEncode(callback.toJson()),
      );

      if (response.statusCode == 200) {
        logger.success('✅ Action callback sent successfully');
        return true;
      }
      logger.error('❌ Send action callback failed: ${response.statusCode}');
      return false;
    } catch (e) {
      logger.error('❌ Send action callback error: $e');
      return false;
    }
  }

  /// Manual override action
  Future<bool> manualOverride(
    String incidentId, {
    required String action,
    required String reason,
    required String operatorId,
  }) async {
    try {
      logger.debug('📤 Sending manual override for $incidentId...');
      final response = await _client.post(
        Uri.parse('$baseUrl/v1/actions/$incidentId'),
        headers: _headers,
        body: jsonEncode({
          'action': action,
          'reason': reason,
          'operator_id': operatorId,
        }),
      );

      if (response.statusCode == 200) {
        logger.success('✅ Manual override successful');
        return true;
      } else {
        logger.error('❌ Manual override failed: ${response.statusCode}');
        return false;
      }
    } catch (e) {
      logger.error('❌ Manual override error: $e');
      print('Manual override error: $e');
      return false;
    }
  }

  void dispose() {
    _client.close();
  }
}
