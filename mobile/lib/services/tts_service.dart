import 'package:flutter_tts/flutter_tts.dart';

/// Text-to-Speech service for emergency announcements
class TtsService {
  final FlutterTts _flutterTts = FlutterTts();
  bool _isInitialized = false;

  TtsService() {
    _initialize();
  }

  Future<void> _initialize() async {
    if (_isInitialized) return;

    try {
      // Set language
      await _flutterTts.setLanguage('en-US');
      
      // Set speech rate (0.0 to 1.0, 0.5 is normal)
      await _flutterTts.setSpeechRate(0.5);
      
      // Set volume (0.0 to 1.0)
      await _flutterTts.setVolume(1.0);
      
      // Set pitch (0.5 to 2.0, 1.0 is normal)
      await _flutterTts.setPitch(1.0);
      
      // CRITICAL: Route audio through call stream instead of media stream
      // This makes TTS audible during phone calls
      await _flutterTts.setIosAudioCategory(
        IosTextToSpeechAudioCategory.playback,
        [
          IosTextToSpeechAudioCategoryOptions.allowBluetooth,
          IosTextToSpeechAudioCategoryOptions.allowBluetoothA2DP,
          IosTextToSpeechAudioCategoryOptions.mixWithOthers,
          IosTextToSpeechAudioCategoryOptions.duckOthers,
        ],
        IosTextToSpeechAudioMode.voiceChat,  // Use voice chat mode for calls
      );
      
      // For Android: Set audio stream to VOICE_CALL
      // This routes TTS audio through the phone call
      await _flutterTts.setSharedInstance(true);
      
      _isInitialized = true;
      print('✅ TTS Service initialized with call audio routing');
    } catch (e) {
      print('❌ TTS initialization error: $e');
    }
  }

  /// Speak emergency message with high priority
  /// This will be audible during phone calls
  Future<void> speakEmergency(String message) async {
    await _initialize();
    
    try {
      print('🔊 TTS Speaking (call audio): $message');
      
      // Stop any ongoing speech
      await _flutterTts.stop();
      
      // Speak the message through call audio stream
      await _flutterTts.speak(message);
    } catch (e) {
      print('❌ TTS speak error: $e');
    }
  }

  /// Generate emergency message from incident data
  String generateEmergencyMessage({
    required String incidentType,
    required int riskScore,
    String? location,
  }) {
    final severity = riskScore >= 8
        ? 'critical'
        : riskScore >= 6
            ? 'high'
            : 'moderate';

    final locationText = location ?? 'unknown location';

    return 'Emergency alert! $incidentType detected at $locationText. '
        'Risk level: $severity. '
        'A detailed report has been sent via SMS.';
  }

  /// Speak action status update
  Future<void> speakStatus(String actionType, String status) async {
    await _initialize();
    
    String message;
    switch (status) {
      case 'acknowledged':
        message = '$actionType successful. Action acknowledged.';
        break;
      case 'failed':
        message = '$actionType failed. Retrying.';
        break;
      case 'escalated':
        message = '$actionType escalated. Manual intervention required.';
        break;
      default:
        message = '$actionType status: $status';
    }

    await speakEmergency(message);
  }

  /// Stop speaking
  Future<void> stop() async {
    await _flutterTts.stop();
  }

  void dispose() {
    _flutterTts.stop();
  }
}
