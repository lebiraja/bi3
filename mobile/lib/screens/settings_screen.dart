import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:provider/provider.dart';
import '../services/preferences_service.dart';
import '../services/agent_service.dart';

/// Settings screen for configuring app settings
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  final _serverUrlController = TextEditingController();
  bool _isLoading = true;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    setState(() => _isLoading = true);
    final serverUrl = await PreferencesService.getServerUrl();
    _serverUrlController.text = serverUrl;
    setState(() => _isLoading = false);
  }

  Future<void> _saveSettings() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() => _isSaving = true);

    try {
      await PreferencesService.setServerUrl(_serverUrlController.text.trim());
      
      if (mounted) {
        // Ask user if they want to apply changes now or restart later
        final shouldApplyNow = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Settings Saved'),
            content: const Text(
              'Would you like to apply the changes now?\n\n'
              'This will reconnect to the new server immediately.\n\n'
              'Otherwise, restart the app manually for changes to take effect.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Restart Later'),
              ),
              ElevatedButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Apply Now'),
              ),
            ],
          ),
        );

        if (shouldApplyNow == true) {
          // Reinitialize agent service with new URL
          final agent = Provider.of<AgentService>(context, listen: false);
          await agent.reinitialize();
          
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  agent.isConnected
                      ? 'Successfully connected to new server!'
                      : 'Settings applied. Connection failed - please check your server URL.',
                ),
                backgroundColor: agent.isConnected ? Colors.green : Colors.orange,
                duration: const Duration(seconds: 4),
              ),
            );
            Navigator.pop(context); // Go back to home screen
          }
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Settings saved! Please restart the app for changes to take effect.'),
              backgroundColor: Colors.blue,
              duration: Duration(seconds: 3),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save settings: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      setState(() => _isSaving = false);
    }
  }

  Future<void> _resetToDefault() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset to Default'),
        content: const Text('Are you sure you want to reset the server URL to the default value?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Reset'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await PreferencesService.clearServerUrl();
      await _loadSettings();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Server URL reset to default'),
            backgroundColor: Colors.blue,
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Server Configuration',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Configure the backend server URL for the Incident Agent',
                      style: TextStyle(
                        color: Colors.grey,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 24),
                    TextFormField(
                      controller: _serverUrlController,
                      decoration: const InputDecoration(
                        labelText: 'Server URL',
                        hintText: 'http://your-server-ip:8000',
                        helperText: 'For Android emulator use: http://10.0.2.2:8000\nFor physical device use your local IP',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.dns),
                      ),
                      keyboardType: TextInputType.url,
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Server URL is required';
                        }
                        
                        final uri = Uri.tryParse(value.trim());
                        if (uri == null || (!uri.scheme.startsWith('http'))) {
                          return 'Please enter a valid HTTP/HTTPS URL';
                        }
                        
                        return null;
                      },
                      maxLines: 1,
                    ),
                    const SizedBox(height: 16),
                    Card(
                      color: Colors.blue.shade50,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(Icons.info_outline, color: Colors.blue.shade700),
                                const SizedBox(width: 8),
                                Text(
                                  'Examples',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: Colors.blue.shade700,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            const Text('• Android Emulator: http://10.0.2.2:8000'),
                            const Text('• iOS Simulator: http://localhost:8000'),
                            const Text('• Physical Device: http://192.168.1.x:8000'),
                            const Text('• Production: https://your-domain.com'),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isSaving ? null : _saveSettings,
                            icon: _isSaving
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Icon(Icons.save),
                            label: Text(_isSaving ? 'Saving...' : 'Save Settings'),
                            style: ElevatedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 16),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        OutlinedButton.icon(
                          onPressed: _isSaving ? null : _resetToDefault,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Reset'),
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(
                              vertical: 16,
                              horizontal: 20,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Card(
                      color: Colors.blue.shade50,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Row(
                          children: [
                            Icon(Icons.info_outline, color: Colors.blue.shade700),
                            const SizedBox(width: 12),
                            const Expanded(
                              child: Text(
                                'You can apply changes immediately or restart the app later',
                                style: TextStyle(fontSize: 13),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
