import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/auth_storage.dart';
import 'home_screen.dart';

/// Biyometrik / PIN Kilit ve Giriş/Kayıt Ekranı
class LoginLockScreen extends StatefulWidget {
  final ApiService apiService;
  final AuthStorageService authStorage;

  const LoginLockScreen({
    super.key,
    required this.apiService,
    required this.authStorage,
  });

  @override
  State<LoginLockScreen> createState() => _LoginLockScreenState();
}

class _LoginLockScreenState extends State<LoginLockScreen> {
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _nameController = TextEditingController();

  bool _isRegisterMode = false;
  bool _isLoading = false;
  bool _hasSavedToken = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _checkExistingSession();
  }

  Future<void> _checkExistingSession() async {
    await widget.apiService.loadSavedBaseUrl();
    final token = await widget.authStorage.getToken();
    final savedEmail = await widget.authStorage.getUserEmail();
    if (savedEmail != null) {
      _emailController.text = savedEmail;
    }
    if (token != null && token.isNotEmpty) {
      setState(() => _hasSavedToken = true);
      await _unlockWithBiometrics();
    }
  }

  Future<void> _unlockWithBiometrics() async {
    final authenticated = await widget.authStorage.authenticateWithBiometrics(
      reason: 'Dijital Anahtar Kasanızı açmak için kimliğinizi doğrulayın',
    );
    if (authenticated && mounted) {
      _navigateToHome();
    } else if (mounted) {
      setState(() {
        _errorMessage = 'Biyometrik doğrulama tamamlanamadı. Parola ile giriş yapabilirsiniz.';
      });
    }
  }

  Future<void> _submitAuthForm() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final email = _emailController.text.trim();
      final password = _passwordController.text;

      if (_isRegisterMode) {
        final fullName = _nameController.text.trim().isEmpty
            ? 'KeyVault Kullanıcısı'
            : _nameController.text.trim();
        await widget.apiService.register(
          email: email,
          password: password,
          fullName: fullName,
        );
      } else {
        await widget.apiService.login(
          email: email,
          password: password,
        );
      }

      if (mounted) {
        _navigateToHome();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceFirst('Exception: ', '');
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _navigateToHome() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => HomeScreen(
          apiService: widget.apiService,
          authStorage: widget.authStorage,
        ),
      ),
    );
  }

  Future<void> _showServerConfigDialog() async {
    final controller = TextEditingController(text: widget.apiService.baseUrl);
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Sunucu Bağlantısı'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Sunucu Adresi (örn. http://192.168.1.10:8000)',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('İptal'),
          ),
          ElevatedButton(
            onPressed: () async {
              await widget.apiService.updateBaseUrl(controller.text);
              if (mounted) {
                setState(() {});
                Navigator.of(ctx).pop();
              }
            },
            child: const Text('Kaydet'),
          ),
        ],
      ),
    );
    controller.dispose();
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Container(
              constraints: const BoxConstraints(maxWidth: 440),
              padding: const EdgeInsets.all(26.0),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.35),
                    blurRadius: 24,
                    offset: const Offset(0, 12),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF38BDF8).withOpacity(0.12),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.vpn_key_rounded,
                      size: 46,
                      color: Color(0xFF38BDF8),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'KeyVault',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Güvenli Dijital Anahtar Kasanız',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 14, color: Colors.white60),
                  ),
                  const SizedBox(height: 26),
                  if (_errorMessage != null) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.redAccent.withOpacity(0.14),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.redAccent.withOpacity(0.5)),
                      ),
                      child: Text(
                        _errorMessage!,
                        style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  if (_isRegisterMode) ...[
                    TextField(
                      controller: _nameController,
                      decoration: InputDecoration(
                        labelText: 'Ad Soyad',
                        prefixIcon: const Icon(Icons.person_outline_rounded),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                  ],
                  TextField(
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    decoration: InputDecoration(
                      labelText: 'E-Posta Adresi',
                      prefixIcon: const Icon(Icons.email_outlined),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: 'Parola',
                      prefixIcon: const Icon(Icons.lock_outline_rounded),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                  ),
                  const SizedBox(height: 22),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: FilledButton.icon(
                      onPressed: _isLoading ? null : _submitAuthForm,
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFF0EA5E9),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      icon: _isLoading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : Icon(_isRegisterMode ? Icons.person_add_rounded : Icons.login_rounded),
                      label: Text(
                        _isRegisterMode ? 'Hesap Oluştur' : 'Giriş Yap',
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ),
                  if (_hasSavedToken) ...[
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      height: 46,
                      child: OutlinedButton.icon(
                        onPressed: _unlockWithBiometrics,
                        style: OutlinedButton.styleFrom(
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14),
                          ),
                        ),
                        icon: const Icon(Icons.fingerprint_rounded, size: 22),
                        label: const Text('Biyometrik / PIN ile Aç'),
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: () {
                      setState(() {
                        _isRegisterMode = !_isRegisterMode;
                        _errorMessage = null;
                      });
                    },
                    child: Text(
                      _isRegisterMode
                          ? 'Zaten hesabınız var mı? Giriş Yapın'
                          : 'Yeni hesap oluşturmak için tıklayın',
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _showServerConfigDialog,
                    icon: const Icon(Icons.dns_outlined, size: 15),
                    label: Text(
                      'Sunucu: ${widget.apiService.baseUrl}',
                      style: const TextStyle(fontSize: 12, color: Colors.white54),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
