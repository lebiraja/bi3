import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config.dart';
import '../models/models.dart';
import 'logger_service.dart';

/// WebSocket service for real-time communication with the server
class WebSocketService {
  WebSocketChannel? _channel;
  final String deviceId;
  final String baseUrl;
  final LoggerService logger;
  StreamSubscription? _subscription;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  bool _isConnected = false;
  bool _shouldReconnect = true;
  int _reconnectAttempts = 0;
  String? _lastWsUrl;

  // Callbacks
  Function(Incident)? onIncidentReceived;
  Function(List<ActionItem>)? onActionPlanReceived;
  Function(Map<String, dynamic>)? onActionCommandReceived;
  Function(String)? onError;
  Function()? onConnected;
  Function()? onDisconnected;

  WebSocketService({
    required this.deviceId,
    required this.baseUrl,
    required this.logger,
  });

  /// Connect to WebSocket server
  Future<bool> connect({String? url}) async {
    final wsUrl = url ?? '${AppConfig.getWsUrl(baseUrl)}/$deviceId';
    _lastWsUrl = wsUrl;
    _shouldReconnect = true;
    
    try {
      logger.info('🔌 Connecting to WebSocket: $wsUrl');
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      
      _subscription = _channel!.stream.listen(
        _handleMessage,
        onError: (error) {
          logger.error('❌ WebSocket error: $error');
          _isConnected = false;
          onError?.call(error.toString());
          onDisconnected?.call();
          _attemptReconnect();
        },
        onDone: () {
          logger.warning('⚠️ WebSocket closed');
          _isConnected = false;
          onDisconnected?.call();
          _attemptReconnect();
        },
      );

      _isConnected = true;
      _reconnectAttempts = 0;
      onConnected?.call();
      
      // Start heartbeat
      _startHeartbeat();
      
      // Send connect message
      _sendMessage({
        'type': 'connect',
        'payload': {
          'device_id': deviceId,
        },
        'timestamp': DateTime.now().toUtc().toIso8601String(),
      });
      
      return true;
    } catch (e) {
      logger.error('❌ WebSocket connect error: $e');
      onError?.call(e.toString());
      _attemptReconnect();
      return false;
    }
  }
  
  /// Attempt to reconnect with exponential backoff
  void _attemptReconnect() {
    if (!_shouldReconnect || _lastWsUrl == null) {
      return;
    }
    
    // Cancel existing reconnect timer
    _reconnectTimer?.cancel();
    
    // Calculate backoff delay (exponential: 1s, 2s, 4s, 8s, max 30s)
    final delay = Duration(
      seconds: (1 << _reconnectAttempts).clamp(1, 30),
    );
    
    _reconnectAttempts++;
    logger.info('🔄 Reconnecting in ${delay.inSeconds}s (attempt $_reconnectAttempts)...');
    
    _reconnectTimer = Timer(delay, () async {
      if (_shouldReconnect && !_isConnected) {
        await connect(url: _lastWsUrl);
      }
    });
  }

  /// Handle incoming WebSocket messages
  void _handleMessage(dynamic message) {
    try {
      logger.debug('📥 WebSocket received: ${message.toString().substring(0, message.toString().length > 100 ? 100 : message.toString().length)}...');
      final data = jsonDecode(message as String) as Map<String, dynamic>;
      final type = data['type'] as String?;
      final payload = data['payload'] as Map<String, dynamic>?;
      final command = data['command'] as String?;

      // Handle direct command messages from the server
      if (command != null) {
        logger.info('📨 Received command: $command');
        onActionCommandReceived?.call(data);
        return;
      }

      switch (type) {
        case 'action_plan':
          if (payload != null) {
            final actions = (payload['actions'] as List<dynamic>?)
                    ?.map((e) => ActionItem.fromJson(e))
                    .toList() ??
                [];
            logger.info('📋 Received action plan with ${actions.length} actions');
            onActionPlanReceived?.call(actions);
          }
          // Send ack
          _sendAck(data['message_id'] ?? '');
          break;

        case 'incident':
          if (payload != null) {
            final incident = Incident.fromJson(payload);
            logger.info('🚨 Received incident: ${incident.incidentId}');
            onIncidentReceived?.call(incident);
          }
          break;

        case 'pong':
        case 'keepalive':
          // Heartbeat response
          logger.debug('💓 Heartbeat received');
          break;

        case 'error':
          final errorMsg = payload?['message'] ?? 'Unknown error';
          logger.error('❌ Server error: $errorMsg');
          onError?.call(errorMsg);
          break;

        default:
          logger.warning('⚠️ Unknown WebSocket message type: $type');
      }
    } catch (e) {
      logger.error('❌ WebSocket message parse error: $e');
    }
  }

  /// Send acknowledgment
  void _sendAck(String messageId) {
    logger.debug('📤 Sending ack for message: $messageId');
    _sendMessage({
      'type': 'ack',
      'payload': {
        'message_id': messageId,
        'status': 'received',
      },
      'timestamp': DateTime.now().toUtc().toIso8601String(),
    });
  }

  /// Send message over WebSocket
  void _sendMessage(Map<String, dynamic> message) {
    if (_channel != null && _isConnected) {
      logger.debug('📤 Sending WebSocket message: ${message['type']}');
      _channel!.sink.add(jsonEncode(message));
    }
  }

  /// Start heartbeat timer
  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (_isConnected) {
        _sendMessage({
          'type': 'heartbeat',
          'payload': {
            'device_id': deviceId,
          },
          'timestamp': DateTime.now().toUtc().toIso8601String(),
        });
      }
    });
  }

  /// Check if connected
  bool get isConnected => _isConnected;

  /// Disconnect from WebSocket server
  void disconnect() {
    logger.info('🔌 Disconnecting WebSocket...');
    _shouldReconnect = false;  // NEW: Disable auto-reconnect
    _reconnectTimer?.cancel();  // NEW: Cancel reconnect timer
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _isConnected = false;
  }

  void dispose() {
    disconnect();
  }
}
