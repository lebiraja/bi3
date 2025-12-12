import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Service for managing device phone number
class PhoneService {
  static const String _phoneNumberKey = 'device_phone_number';

  /// Get stored phone number from preferences
  Future<String?> getPhoneNumber() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(_phoneNumberKey);
    } catch (e) {
      print('Error getting phone number: $e');
      return null;
    }
  }

  /// Save phone number to preferences
  Future<bool> savePhoneNumber(String phoneNumber) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return await prefs.setString(_phoneNumberKey, phoneNumber);
    } catch (e) {
      print('Error saving phone number: $e');
      return false;
    }
  }

  /// Clear stored phone number
  Future<bool> clearPhoneNumber() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return await prefs.remove(_phoneNumberKey);
    } catch (e) {
      print('Error clearing phone number: $e');
      return false;
    }
  }

  /// Format phone number to E.164 format
  String formatPhoneNumber(String number) {
    // Remove all non-digit characters except +
    String cleaned = number.replaceAll(RegExp(r'[^\d+]'), '');
    
    // Ensure it starts with +
    if (!cleaned.startsWith('+')) {
      // Assume India (+91) if no country code
      cleaned = '+91$cleaned';
    }
    
    return cleaned;
  }

  /// Validate phone number format (E.164)
  bool isValidPhoneNumber(String? number) {
    if (number == null || number.isEmpty) return false;
    
    // E.164 format: +[country code][number]
    // Country code: 1-3 digits, Number: up to 15 digits total
    final regex = RegExp(r'^\+[1-9]\d{1,14}$');
    return regex.hasMatch(number);
  }

  /// Request phone permission
  Future<bool> requestPhonePermission() async {
    try {
      final status = await Permission.phone.request();
      return status.isGranted;
    } catch (e) {
      print('Error requesting phone permission: $e');
      return false;
    }
  }

  /// Check if phone permission is granted
  Future<bool> hasPhonePermission() async {
    try {
      final status = await Permission.phone.status;
      return status.isGranted;
    } catch (e) {
      print('Error checking phone permission: $e');
      return false;
    }
  }
}
