/// Configuration for the Incident Agent app
class AppConfig {
  // Server configuration - Default values
  static const String defaultBaseUrl = 'http://10.0.2.2:8000'; // Android emulator localhost
  static const String defaultWsUrl = 'ws://10.0.2.2:8000/ws';
  
  // Legacy: Keep for backward compatibility
  @Deprecated('Use PreferencesService.getServerUrl() instead')
  static const String baseUrl = defaultBaseUrl;
  
  // For physical device, use your local IP
  // Example: 'http://192.168.1.x:8000'
  
  // API Endpoints
  static const String healthEndpoint = '/health';
  static const String devicesEndpoint = '/v1/devices';  // Fixed: removed duplicate /register
  static const String incidentsEndpoint = '/v1/incidents';
  static const String callbackEndpoint = '/v1/mobile/callback';
  static const String mobileCallbackEndpoint = '/v1/mobile/callback';  // Same as callbackEndpoint
  
  // WebSocket path
  static const String wsPath = '/ws';
  
  // Hardcoded emergency contacts
  static const String policeNumber = '+919535879330';
  static const String ambulanceNumber = '+916369445764';
  
  // TTS settings
  static const double ttsRate = 0.5;
  static const double ttsPitch = 1.0;
  static const double ttsVolume = 1.0;
  
  // Retry policy
  static const int maxRetries = 3;
  static const int retryDelaySeconds = 10;
  static const int callTimeoutSeconds = 30;
  
  /// Get WebSocket URL from base URL
  static String getWsUrl(String baseUrl) {
    final uri = Uri.parse(baseUrl);
    final wsScheme = uri.scheme == 'https' ? 'wss' : 'ws';
    return '$wsScheme://${uri.host}:${uri.port}$wsPath';
  }
}
