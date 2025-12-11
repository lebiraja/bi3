import 'package:flutter/foundation.dart';

/// Service for logging and displaying real-time logs in the app
class LoggerService extends ChangeNotifier {
  final List<LogEntry> _logs = [];
  final int _maxLogs = 500;

  List<LogEntry> get logs => List.unmodifiable(_logs);

  void log(String message, {LogLevel level = LogLevel.info}) {
    final entry = LogEntry(
      timestamp: DateTime.now(),
      message: message,
      level: level,
    );

    _logs.insert(0, entry);

    // Keep only the latest logs
    if (_logs.length > _maxLogs) {
      _logs.removeRange(_maxLogs, _logs.length);
    }

    // Also print to console
    print('[${level.name.toUpperCase()}] $message');

    notifyListeners();
  }

  void debug(String message) => log(message, level: LogLevel.debug);
  void info(String message) => log(message, level: LogLevel.info);
  void warning(String message) => log(message, level: LogLevel.warning);
  void error(String message) => log(message, level: LogLevel.error);
  void success(String message) => log(message, level: LogLevel.success);

  void clear() {
    _logs.clear();
    notifyListeners();
  }
}

class LogEntry {
  final DateTime timestamp;
  final String message;
  final LogLevel level;

  LogEntry({
    required this.timestamp,
    required this.message,
    required this.level,
  });

  String get formattedTime {
    return '${timestamp.hour.toString().padLeft(2, '0')}:'
        '${timestamp.minute.toString().padLeft(2, '0')}:'
        '${timestamp.second.toString().padLeft(2, '0')}';
  }
}

enum LogLevel {
  debug,
  info,
  warning,
  error,
  success,
}
