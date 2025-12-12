import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/agent_service.dart';
import 'services/logger_service.dart';
import 'services/native_telephony_service.dart';  // NEW
import 'screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Request telephony permissions on app start
  final telephony = NativeTelephonyService();
  await telephony.requestPermissions();
  
  runApp(const IncidentAgentApp());
}

/// Main app for BI3 Incident Orchestrator Agent
class IncidentAgentApp extends StatelessWidget {
  const IncidentAgentApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => LoggerService()),
        ChangeNotifierProvider(
          create: (context) => AgentService(
            logger: context.read<LoggerService>(),
          ),
        ),
      ],
      child: MaterialApp(
        title: 'BI3 Incident Agent',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: Colors.red,
            brightness: Brightness.light,
          ),
          useMaterial3: true,
          cardTheme: const CardTheme(
            elevation: 2,
            margin: EdgeInsets.symmetric(vertical: 4),
          ),
          appBarTheme: const AppBarTheme(
            centerTitle: true,
            elevation: 0,
          ),
        ),
        darkTheme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: Colors.red,
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
        ),
        themeMode: ThemeMode.system,
        home: const HomeScreen(),
      ),
    );
  }
}
