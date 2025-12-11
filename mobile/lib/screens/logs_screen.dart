import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/logger_service.dart';

/// Screen to display real-time logs
class LogsScreen extends StatefulWidget {
  const LogsScreen({super.key});

  @override
  State<LogsScreen> createState() => _LogsScreenState();
}

class _LogsScreenState extends State<LogsScreen> {
  final ScrollController _scrollController = ScrollController();
  bool _autoScroll = true;

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  Color _getLevelColor(LogLevel level) {
    switch (level) {
      case LogLevel.debug:
        return Colors.grey;
      case LogLevel.info:
        return Colors.blue;
      case LogLevel.warning:
        return Colors.orange;
      case LogLevel.error:
        return Colors.red;
      case LogLevel.success:
        return Colors.green;
    }
  }

  IconData _getLevelIcon(LogLevel level) {
    switch (level) {
      case LogLevel.debug:
        return Icons.bug_report;
      case LogLevel.info:
        return Icons.info_outline;
      case LogLevel.warning:
        return Icons.warning_amber;
      case LogLevel.error:
        return Icons.error_outline;
      case LogLevel.success:
        return Icons.check_circle_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Real-time Logs'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: Icon(_autoScroll ? Icons.vertical_align_bottom : Icons.vertical_align_top),
            tooltip: _autoScroll ? 'Auto-scroll On' : 'Auto-scroll Off',
            onPressed: () {
              setState(() {
                _autoScroll = !_autoScroll;
              });
            },
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Clear Logs',
            onPressed: () {
              final logger = Provider.of<LoggerService>(context, listen: false);
              logger.clear();
            },
          ),
        ],
      ),
      body: Consumer<LoggerService>(
        builder: (context, logger, child) {
          if (logger.logs.isEmpty) {
            return const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.article_outlined, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text(
                    'No logs yet',
                    style: TextStyle(color: Colors.grey, fontSize: 16),
                  ),
                ],
              ),
            );
          }

          // Auto-scroll to top when new logs arrive
          if (_autoScroll && logger.logs.isNotEmpty) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (_scrollController.hasClients) {
                _scrollController.animateTo(
                  0,
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeOut,
                );
              }
            });
          }

          return Column(
            children: [
              // Stats bar
              Container(
                padding: const EdgeInsets.all(8),
                color: Colors.grey.shade100,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildStatChip(
                      'Total',
                      logger.logs.length,
                      Colors.blue,
                    ),
                    _buildStatChip(
                      'Errors',
                      logger.logs.where((l) => l.level == LogLevel.error).length,
                      Colors.red,
                    ),
                    _buildStatChip(
                      'Warnings',
                      logger.logs.where((l) => l.level == LogLevel.warning).length,
                      Colors.orange,
                    ),
                    _buildStatChip(
                      'Success',
                      logger.logs.where((l) => l.level == LogLevel.success).length,
                      Colors.green,
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              // Logs list
              Expanded(
                child: ListView.separated(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(8),
                  itemCount: logger.logs.length,
                  separatorBuilder: (context, index) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final log = logger.logs[index];
                    final color = _getLevelColor(log.level);
                    final icon = _getLevelIcon(log.level);

                    return Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(icon, color: color, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      log.formattedTime,
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.grey.shade600,
                                        fontFamily: 'monospace',
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 6,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: color.withOpacity(0.1),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        log.level.name.toUpperCase(),
                                        style: TextStyle(
                                          fontSize: 10,
                                          fontWeight: FontWeight.bold,
                                          color: color,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  log.message,
                                  style: const TextStyle(fontSize: 14),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildStatChip(String label, int count, Color color) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          count.toString(),
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            color: Colors.grey.shade600,
          ),
        ),
      ],
    );
  }
}
