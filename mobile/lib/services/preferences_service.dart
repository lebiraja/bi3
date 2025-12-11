import 'package:shared_preferences/shared_preferences.dart';
import '../config.dart';

/// Service for managing app preferences
class PreferencesService {
  static const String _serverUrlKey = 'server_url';

  /// Get the configured server URL or default
  static Future<String> getServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_serverUrlKey) ?? AppConfig.defaultBaseUrl;
  }

  /// Set the server URL
  static Future<void> setServerUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_serverUrlKey, url);
  }

  /// Clear the server URL (reset to default)
  static Future<void> clearServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_serverUrlKey);
  }

  /// Check if server URL has been customized
  static Future<bool> hasCustomServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey(_serverUrlKey);
  }
}
