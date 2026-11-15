import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Kullanıcı Oturumu, "Beni Hatırla" Profil Bilgileri ve Güvenli Depolama Servisi.
class AuthStorageService {
  static const String _jwtKey = 'keyvault_jwt_access_token';
  static const String _emailKey = 'keyvault_user_email';
  static const String _fullNameKey = 'keyvault_user_full_name';
  static const String _rememberMeKey = 'keyvault_remember_me';
  static const String _baseUrlKey = 'keyvault_api_base_url';

  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  final LocalAuthentication _localAuth = LocalAuthentication();

  /// Oturum bilgilerini ve "Beni Hatırla" tercihini kaydeder.
  Future<void> saveSession({
    required String token,
    required String email,
    String? fullName,
    bool rememberMe = true,
  }) async {
    await _secureStorage.write(key: _jwtKey, value: token);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_rememberMeKey, rememberMe);

    if (rememberMe) {
      await _secureStorage.write(key: _emailKey, value: email);
      await prefs.setString(_emailKey, email);
      if (fullName != null && fullName.trim().isNotEmpty) {
        await prefs.setString(_fullNameKey, fullName.trim());
      }
    } else {
      await _secureStorage.delete(key: _emailKey);
      await prefs.remove(_emailKey);
      await prefs.remove(_fullNameKey);
    }
  }

  /// Kayıtlı JWT Token'ı okur.
  Future<String?> getToken() async {
    return await _secureStorage.read(key: _jwtKey);
  }

  /// Kayıtlı kullanıcı e-postasını okur.
  Future<String?> getUserEmail() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_emailKey) ?? await _secureStorage.read(key: _emailKey);
  }

  /// Kayıtlı kullanıcı Ad Soyad bilgisini okur.
  Future<String?> getUserFullName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_fullNameKey);
  }

  /// "Beni Hatırla" seçeneğinin aktif olup olmadığını döndürür.
  Future<bool> getRememberMe() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_rememberMeKey) ?? true;
  }

  /// Özel sunucu adresini kaydeder.
  Future<void> saveBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_baseUrlKey, url.trim());
  }

  /// Kayıtlı özel sunucu adresini okur.
  Future<String?> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_baseUrlKey);
  }

  /// Oturumu kapatır (Beni Hatırla aktifse e-posta ve kullanıcı adını korur).
  Future<void> clearSession() async {
    await _secureStorage.delete(key: _jwtKey);
  }

  /// Hatırlanan kullanıcı hesabını tamamen unutur ("Farklı hesapla giriş yap" için).
  Future<void> forgetRememberedUser() async {
    await _secureStorage.delete(key: _jwtKey);
    await _secureStorage.delete(key: _emailKey);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_emailKey);
    await prefs.remove(_fullNameKey);
    await prefs.setBool(_rememberMeKey, false);
  }

  Future<bool> isBiometricAvailable() async {
    try {
      final bool canCheck = await _localAuth.canCheckBiometrics;
      final bool isSupported = await _localAuth.isDeviceSupported();
      return canCheck || isSupported;
    } on PlatformException {
      return false;
    }
  }

  Future<bool> authenticateWithBiometrics({
    String reason = 'Kimliğinizi doğrulayın',
  }) async {
    try {
      final bool available = await isBiometricAvailable();
      if (!available) {
        return true;
      }
      return await _localAuth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          stickyAuth: true,
          biometricOnly: false,
          useErrorDialogs: true,
        ),
      );
    } on PlatformException {
      return true;
    }
  }
}
