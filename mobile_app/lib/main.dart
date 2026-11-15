import 'package:flutter/material.dart';
import 'screens/login_lock_screen.dart';
import 'services/api_service.dart';
import 'services/auth_storage.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final authStorage = AuthStorageService();
  final apiService = ApiService(storage: authStorage);
  runApp(KeyVaultApp(apiService: apiService, authStorage: authStorage));
}

class KeyVaultApp extends StatelessWidget {
  final ApiService apiService;
  final AuthStorageService authStorage;

  const KeyVaultApp({
    super.key,
    required this.apiService,
    required this.authStorage,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'KeyVault-AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0EA5E9),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        useMaterial3: true,
      ),
      home: LoginLockScreen(
        apiService: apiService,
        authStorage: authStorage,
      ),
    );
  }
}
