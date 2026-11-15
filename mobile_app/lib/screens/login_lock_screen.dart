import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/auth_storage.dart';
import 'home_screen.dart';

/// Profesyonel "Beni Hatırla" ve "Hoş Geldin, [Kullanıcı Adı]" Destekli Giriş/Kayıt Ekranı
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
  bool _rememberMe = true;
  bool _isRememberedUserMode = false;
  String? _rememberedName;
  String? _rememberedEmail;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initScreen();
  }

  Future<void> _initScreen() async {
    await widget.apiService.loadSavedBaseUrl();
    final savedEmail = await widget.authStorage.getUserEmail();
    final savedName = await widget.authStorage.getUserFullName();
    final remember = await widget.authStorage.getRememberMe();

    if (mounted) {
      setState(() {
        _rememberMe = remember;
        if (remember && savedEmail != null && savedEmail.trim().isNotEmpty) {
          _rememberedEmail = savedEmail.trim();
          _emailController.text = _rememberedEmail!;
          _rememberedName = (savedName != null && savedName.trim().isNotEmpty)
              ? savedName.trim()
              : savedEmail.split('@').first;
          _isRememberedUserMode = true;
        }
      });
    }
  }

  Future<void> _switchAccount() async {
    await widget.authStorage.forgetRememberedUser();
    if (mounted) {
      setState(() {
        _isRememberedUserMode = false;
        _rememberedName = null;
        _rememberedEmail = null;
        _emailController.clear();
        _passwordController.clear();
        _errorMessage = null;
      });
    }
  }

  Future<void> _submitAuthForm() async {
    final email = _isRememberedUserMode
        ? (_rememberedEmail ?? _emailController.text.trim())
        : _emailController.text.trim();
    final password = _passwordController.text;

    if (email.isEmpty || password.isEmpty) {
      setState(() {
        _errorMessage = 'Lütfen parola alanını doldurun.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      if (_isRegisterMode && !_isRememberedUserMode) {
        final fullName = _nameController.text.trim().isEmpty
            ? email.split('@').first
            : _nameController.text.trim();
        await widget.apiService.register(
          email: email,
          password: password,
          fullName: fullName,
          rememberMe: _rememberMe,
        );
      } else {
        await widget.apiService.login(
          email: email,
          password: password,
          rememberMe: _rememberMe,
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

  Future<void> _showServerSwitcherSheet() async {
    final formKey = GlobalKey<FormState>();
    final String initialLanUrl =
        widget.apiService.baseUrl == ApiService.defaultBaseUrl
            ? ApiService.defaultLanBaseUrl
            : widget.apiService.baseUrl;
    final lanController = TextEditingController(text: initialLanUrl);

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF1E293B),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        final bottomInset = MediaQuery.of(ctx).viewInsets.bottom;
        final bool isLocalhost =
            widget.apiService.baseUrl == ApiService.defaultBaseUrl;

        return Padding(
          padding: EdgeInsets.fromLTRB(20, 16, 20, 24 + bottomInset),
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 42,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.white24,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Sunucu Seçici',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Bağlanmak istediğiniz ortamı seçin veya yerel IP adresini girin.',
                  style: TextStyle(fontSize: 13, color: Colors.white60),
                ),
                const SizedBox(height: 18),
                Material(
                  color: isLocalhost
                      ? const Color(0xFF0EA5E9).withOpacity(0.16)
                      : const Color(0xFF0F172A),
                  borderRadius: BorderRadius.circular(16),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(16),
                    onTap: () async {
                      await widget.apiService
                          .updateBaseUrl(ApiService.defaultBaseUrl);
                      if (mounted) setState(() {});
                      if (ctx.mounted) Navigator.of(ctx).pop();
                    },
                    child: Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: isLocalhost
                              ? const Color(0xFF38BDF8)
                              : Colors.white.withOpacity(0.08),
                        ),
                      ),
                      child: Row(
                        children: [
                          const Text('💻', style: TextStyle(fontSize: 24)),
                          const SizedBox(width: 14),
                          const Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Chrome & USB Tablet (Localhost)',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                    fontSize: 15,
                                  ),
                                ),
                                SizedBox(height: 2),
                                Text(
                                  ApiService.defaultBaseUrl,
                                  style: TextStyle(
                                    color: Colors.white60,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (isLocalhost)
                            const Icon(
                              Icons.check_circle_rounded,
                              color: Color(0xFF38BDF8),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: !isLocalhost
                        ? const Color(0xFF0EA5E9).withOpacity(0.10)
                        : const Color(0xFF0F172A),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: !isLocalhost
                          ? const Color(0xFF38BDF8)
                          : Colors.white.withOpacity(0.08),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Text('📱', style: TextStyle(fontSize: 22)),
                          SizedBox(width: 10),
                          Text(
                            'Honor Tablet (Yerel Ağ)',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                              fontSize: 15,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: lanController,
                        keyboardType: TextInputType.url,
                        decoration: InputDecoration(
                          labelText: 'Bilgisayar IP Adresi',
                          hintText: 'http://192.168.1.X:8000/api',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          isDense: true,
                        ),
                        validator: (val) {
                          if (val == null || val.trim().isEmpty) {
                            return 'Lütfen geçerli bir sunucu adresi girin.';
                          }
                          if (!val.trim().startsWith('http://') &&
                              !val.trim().startsWith('https://')) {
                            return 'Adres http:// veya https:// ile başlamalıdır.';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        height: 44,
                        child: FilledButton.icon(
                          onPressed: () async {
                            if (formKey.currentState?.validate() ?? false) {
                              await widget.apiService
                                  .updateBaseUrl(lanController.text);
                              if (mounted) setState(() {});
                              if (ctx.mounted) Navigator.of(ctx).pop();
                            }
                          },
                          style: FilledButton.styleFrom(
                            backgroundColor: const Color(0xFF0EA5E9),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                          icon: const Icon(Icons.save_rounded, size: 18),
                          label: const Text('Yerel Ağ Adresini Kaydet'),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );

    lanController.dispose();
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
                      color: const Color(0xFF38BDF8).withOpacity(0.14),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      _isRememberedUserMode
                          ? Icons.verified_user_rounded
                          : Icons.vpn_key_rounded,
                      size: 44,
                      color: const Color(0xFF38BDF8),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _isRememberedUserMode
                        ? 'Hoş Geldin, ${_rememberedName ?? ""}'
                        : 'KeyVault',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 25,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _isRememberedUserMode
                        ? 'Devam etmek için yalnızca parolanızı girin'
                        : 'Güvenli Dijital Anahtar Kasanız',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 13.5, color: Colors.white60),
                  ),
                  const SizedBox(height: 24),
                  if (_errorMessage != null) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.redAccent.withOpacity(0.14),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.redAccent.withOpacity(0.5),
                        ),
                      ),
                      child: Text(
                        _errorMessage!,
                        style: const TextStyle(
                          color: Colors.redAccent,
                          fontSize: 13,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // Hatırlanan Kullanıcı Değilse E-Posta ve Kayıt Alanlarını Göster
                  if (!_isRememberedUserMode) ...[
                    if (_isRegisterMode) ...[
                      TextField(
                        controller: _nameController,
                        textCapitalization: TextCapitalization.words,
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
                  ],

                  // Parola Alanı (Her Zaman Gösterilir)
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    onSubmitted: (_) => _submitAuthForm(),
                    decoration: InputDecoration(
                      labelText: 'Parola',
                      prefixIcon: const Icon(Icons.lock_outline_rounded),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                  ),

                  // Beni Hatırla Seçeneği
                  if (!_isRememberedUserMode) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Checkbox(
                          value: _rememberMe,
                          activeColor: const Color(0xFF0EA5E9),
                          onChanged: (val) {
                            setState(() => _rememberMe = val ?? true);
                          },
                        ),
                        GestureDetector(
                          onTap: () =>
                              setState(() => _rememberMe = !_rememberMe),
                          child: const Text(
                            'Beni Hatırla (Bir sonraki girişte sadece parola sor)',
                            style: TextStyle(
                              fontSize: 12.5,
                              color: Colors.white70,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],

                  const SizedBox(height: 18),
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
                          : Icon(
                              _isRegisterMode && !_isRememberedUserMode
                                  ? Icons.person_add_rounded
                                  : Icons.login_rounded,
                            ),
                      label: Text(
                        _isRegisterMode && !_isRememberedUserMode
                            ? 'Hesap Oluştur'
                            : 'Giriş Yap',
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),

                  if (_isRememberedUserMode)
                    TextButton.icon(
                      onPressed: _switchAccount,
                      icon: const Icon(Icons.swap_horiz_rounded, size: 18),
                      label: const Text('Farklı bir hesapla giriş yap'),
                    )
                  else
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
                    onPressed: _showServerSwitcherSheet,
                    icon: Icon(
                      widget.apiService.isServerReachable
                          ? Icons.check_circle_rounded
                          : Icons.settings_ethernet_rounded,
                      size: 16,
                      color: widget.apiService.isServerReachable
                          ? const Color(0xFF34D399)
                          : Colors.amberAccent,
                    ),
                    label: Text(
                      'Sunucu: ${widget.apiService.baseUrl}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Colors.white70,
                      ),
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
