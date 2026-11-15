import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';

/// Biyometrik (Parmak İzi / FaceID / Cihaz PIN) Kimlik Doğrulama
/// ve Donanım Destekli Güvenli Depolama (Keystore / Keychain) Servisi.
class AuthStorageService {
  static const String _jwtKey = 'keyvault_jwt_access_token';
  static const String _emailKey = 'keyvault_user_email';
  static const String _baseUrlKey = 'keyvault_api_base_url';

  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  final LocalAuthentication _localAuth = LocalAuthentication();

  /// JWT Token'ı şifreli donanım deposuna kaydeder.
  Future<void> saveSession({
    required String token,
    required String email,
  }) async {
    await _secureStorage.write(key: _jwtKey, value: token);
    await _secureStorage.write(key: _emailKey, value: email);
  }

  /// Kayıtlı JWT Token'ı okur.
  Future<String?> getToken() async {
    return await _secureStorage.read(key: _jwtKey);
  }

  /// Kayıtlı kullanıcı e-postasını okur.
  Future<String?> getUserEmail() async {
    return await _secureStorage.read(key: _emailKey);
  }

  /// Özel sunucu adresini (örn. http://192.168.1.50:8000) kaydeder.
  Future<void> saveBaseUrl(String url) async {
    await _secureStorage.write(key: _baseUrlKey, value: url.trim());
  }

  /// Kayıtlı özel sunucu adresini okur.
  Future<String?> getBaseUrl() async {
    return await _secureStorage.read(key: _baseUrlKey);
  }

  /// Oturumu sonlandırır ve güvenli depoyu temizler.
  Future<void> clearSession() async {
    await _secureStorage.delete(key: _jwtKey);
    await _secureStorage.delete(key: _emailKey);
  }

  /// Cihazın biyometrik veya PIN doğrulamasını destekleyip desteklemediğini kontrol eder.
  Future<bool> isBiometricAvailable() async {
    try {
      final bool canCheck = await _localAuth.canCheckBiometrics;
      final bool isSupported = await _localAuth.isDeviceSupported();
      return canCheck || isSupported;
    } on PlatformException {
      return false;
    }
  }

  /// Kasayı açmadan veya CNC G-Code/PDF dışa aktarmadan önce
  /// Biyometrik (Parmak izi / Yüz tanıma) veya Cihaz PIN doğrulaması ister.
  Future<bool> authenticateWithBiometrics({
    String reason = 'KeyVault-AI Dijital Anahtar Kasasına erişmek için kimliğinizi doğrulayın',
  }) async {
    try {
      final bool available = await isBiometricAvailable();
      if (!available) {
        return false;
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
      return false;
    }
  }
}
