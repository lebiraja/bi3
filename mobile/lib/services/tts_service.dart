import 'package:flutter_tts/flutter_tts.dart';
import '../config.dart';

/// Text-to-Speech service for emergency announcements
class TtsService {
  final FlutterTts _tts = FlutterTts();
  bool _isInitialized = false;
  bool _isSpeaking = false;

  /// Initialize TTS engine
  Future<void> initialize() async {
    if (_isInitialized) return;

    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(AppConfig.ttsRate);
    await _tts.setPitch(AppConfig.ttsPitch);
    await _tts.setVolume(AppConfig.ttsVolume);

    // Set up completion handler
    _tts.setCompletionHandler(() {
      _isSpeaking = false;
    });

    _tts.setErrorHandler((msg) {
      print('TTS Error: $msg');
      _isSpeaking = false;
    });

    _isInitialized = true;
  }

  /// Speak emergency alert message
  Future<void> speakEmergency(String message) async {
    await initialize();
    
    // Stop any current speech
    if (_isSpeaking) {
      await stop();
    }

    _isSpeaking = true;
    await _tts.speak(message);
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
    await initialize();
    
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
    await _tts.stop();
    _isSpeaking = false;
  }

  bool get isSpeaking => _isSpeaking;

  void dispose() {
    _tts.stop();
  }
}
