import 'package:flutter/services.dart';

/// Native telephony service for automatic calls and SMS
/// Uses platform channels to communicate with Android native code
class NativeTelephonyService {
  static const platform = MethodChannel('com.bi3.incident_agent/telephony');
  
  // Callbacks for call state changes
  Function(String state, String? phoneNumber)? onCallStateChanged;
  Function(String phoneNumber, bool success, String? error)? onSMSSent;
  Function(bool granted)? onPermissionsResult;
  
  NativeTelephonyService() {
    platform.setMethodCallHandler(_handleMethodCall);
  }
  
  Future<void> _handleMethodCall(MethodCall call) async {
    switch (call.method) {
      case 'onCallStateChanged':
        final state = call.arguments['state'] as String;
        final phoneNumber = call.arguments['phoneNumber'] as String?;
        onCallStateChanged?.call(state, phoneNumber);
        print('📞 Call state changed: $state for $phoneNumber');
        break;
        
      case 'onSMSSent':
        final phoneNumber = call.arguments['phoneNumber'] as String;
        final success = call.arguments['success'] as bool;
        final error = call.arguments['error'] as String?;
        onSMSSent?.call(phoneNumber, success, error);
        print('📧 SMS sent: $success to $phoneNumber');
        break;
        
      case 'onPermissionsResult':
        final granted = call.arguments as bool;
        onPermissionsResult?.call(granted);
        print('🔐 Permissions result: $granted');
        break;
    }
  }
  
  /// Request telephony permissions from user
  Future<void> requestPermissions() async {
    try {
      await platform.invokeMethod('requestPermissions');
    } on PlatformException catch (e) {
      print('❌ Failed to request permissions: ${e.message}');
    }
  }
  
  /// Check if all required permissions are granted
  Future<bool> checkPermissions() async {
    try {
      final result = await platform.invokeMethod('checkPermissions');
      return result as bool;
    } on PlatformException catch (e) {
      print('❌ Failed to check permissions: ${e.message}');
      return false;
    }
  }
  
  /// Make a phone call automatically (no user interaction needed)
  Future<bool> makeCall(String phoneNumber) async {
    try {
      print('📞 Making call to $phoneNumber via native telephony...');
      final result = await platform.invokeMethod('makeCall', {
        'phoneNumber': phoneNumber,
      });
      return result as bool;
    } on PlatformException catch (e) {
      print('❌ Failed to make call: ${e.message}');
      return false;
    }
  }
  
  /// Send SMS automatically (no user interaction needed)
  Future<bool> sendSMS(String phoneNumber, String message) async {
    try {
      print('📧 Sending SMS to $phoneNumber via native telephony...');
      final result = await platform.invokeMethod('sendSMS', {
        'phoneNumber': phoneNumber,
        'message': message,
      });
      return result as bool;
    } on PlatformException catch (e) {
      print('❌ Failed to send SMS: ${e.message}');
      return false;
    }
  }
  
  /// Set audio mode for in-call TTS (loudspeaker at max volume)
  Future<bool> setAudioModeForCall() async {
    try {
      print('🔊 Setting audio mode for call (loudspeaker + max volume)...');
      final result = await platform.invokeMethod('setAudioModeForCall');
      return result as bool;
    } on PlatformException catch (e) {
      print('❌ Failed to set audio mode: ${e.message}');
      return false;
    }
  }
  
  /// Restore normal audio mode after call
  Future<bool> restoreAudioMode() async {
    try {
      print('🔇 Restoring normal audio mode...');
      final result = await platform.invokeMethod('restoreAudioMode');
      return result as bool;
    } on PlatformException catch (e) {
      print('❌ Failed to restore audio mode: ${e.message}');
      return false;
    }
  }
}
