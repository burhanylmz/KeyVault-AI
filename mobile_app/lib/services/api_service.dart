import 'dart:async';
import 'dart:collection';
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'auth_storage.dart';

/// KeyVault-AI Kayıtlı Anahtar Modeli
class KeyVaultItem {
  final int id;
  final String keyName;
  final String profileType;
  final String mode;
  final String? bittingCode;
  final List<double> rawDepthsMm;
  final List<double> valleyPositionsMm;
  final bool macsValid;
  final String macsState;
  final double scaleFactorK;
  final String? vectorDrawingB64;
  final String createdAt;

  KeyVaultItem({
    required this.id,
    required this.keyName,
    required this.profileType,
    required this.mode,
    required this.bittingCode,
    required this.rawDepthsMm,
    required this.valleyPositionsMm,
    required this.macsValid,
    required this.macsState,
    required this.scaleFactorK,
    required this.vectorDrawingB64,
    required this.createdAt,
  });

  factory KeyVaultItem.fromJson(Map<String, dynamic> json) {
    return KeyVaultItem(
      id: json['id'] as int,
      keyName: json['key_name'] as String,
      profileType: json['profile_type'] as String,
      mode: json['mode'] as String,
      bittingCode: json['bitting_code'] as String?,
      rawDepthsMm: (json['raw_depths_mm'] as List<dynamic>)
          .map((e) => (e as num).toDouble())
          .toList(),
      valleyPositionsMm: (json['valley_positions_mm'] as List<dynamic>)
          .map((e) => (e as num).toDouble())
          .toList(),
      macsValid: json['macs_valid'] as bool,
      macsState: json['macs_state'] as String,
      scaleFactorK: (json['scale_factor_k'] as num).toDouble(),
      vectorDrawingB64: json['vector_drawing_b64'] as String?,
      createdAt: json['created_at'].toString(),
    );
  }
}

/// Kasaya Kaydetmeden Önce Kullanıcıya Gösterilen Kanıt & Analiz Önizleme Modeli
class KeyAnalysisPreview {
  final String keyName;
  final String profileType;
  final String? detectedBrand;
  final String mode;
  final String? bittingCode;
  final List<double> rawDepthsMm;
  final List<double> valleyPositionsMm;
  final List<double> remainingHeightsMm;
  final List<double> pitchValuesMm;
  final double totalLengthMm;
  final double bowHeightMm;
  final double bladeLengthMm;
  final double bladeWidthMm;
  final bool macsValid;
  final String macsState;
  final double scaleFactorK;
  final double cardPixelWidth;
  final String? vectorDrawingB64;
  final String? annotatedPhotoB64;

  KeyAnalysisPreview({
    required this.keyName,
    required this.profileType,
    required this.detectedBrand,
    required this.mode,
    required this.bittingCode,
    required this.rawDepthsMm,
    required this.valleyPositionsMm,
    required this.remainingHeightsMm,
    required this.pitchValuesMm,
    required this.totalLengthMm,
    required this.bowHeightMm,
    required this.bladeLengthMm,
    required this.bladeWidthMm,
    required this.macsValid,
    required this.macsState,
    required this.scaleFactorK,
    required this.cardPixelWidth,
    required this.vectorDrawingB64,
    required this.annotatedPhotoB64,
  });

  factory KeyAnalysisPreview.fromJson(Map<String, dynamic> json) {
    return KeyAnalysisPreview(
      keyName: json['key_name'] as String,
      profileType: json['profile_type'] as String,
      detectedBrand: json['detected_brand'] as String?,
      mode: json['mode'] as String,
      bittingCode: json['bitting_code'] as String?,
      rawDepthsMm: (json['raw_depths_mm'] as List<dynamic>)
          .map((e) => (e as num).toDouble())
          .toList(),
      valleyPositionsMm: (json['valley_positions_mm'] as List<dynamic>)
          .map((e) => (e as num).toDouble())
          .toList(),
      remainingHeightsMm: (json['remaining_heights_mm'] as List<dynamic>? ?? [])
          .map((e) => (e as num).toDouble())
          .toList(),
      pitchValuesMm: (json['pitch_values_mm'] as List<dynamic>? ?? [])
          .map((e) => (e as num).toDouble())
          .toList(),
      totalLengthMm: (json['total_length_mm'] as num? ?? 0.0).toDouble(),
      bowHeightMm: (json['bow_height_mm'] as num? ?? 0.0).toDouble(),
      bladeLengthMm: (json['blade_length_mm'] as num? ?? 0.0).toDouble(),
      bladeWidthMm: (json['blade_width_mm'] as num? ?? 0.0).toDouble(),
      macsValid: json['macs_valid'] as bool,
      macsState: json['macs_state'] as String,
      scaleFactorK: (json['scale_factor_k'] as num).toDouble(),
      cardPixelWidth: (json['card_pixel_width'] as num).toDouble(),
      vectorDrawingB64: json['vector_drawing_b64'] as String?,
      annotatedPhotoB64: json['annotated_photo_b64'] as String?,
    );
  }
}

/// FastAPI Backend ile İletişim Kuran Akıllı REST API Servisi
class ApiService {
  static const String defaultBaseUrl = 'http://127.0.0.1:8000/api';
  static const String defaultLanBaseUrl = 'http://172.20.10.3:8000/api';
  static const String _prefBaseUrlKey = 'keyvault_api_base_url';

  String baseUrl;
  bool isServerReachable = false;
  final AuthStorageService authStorage;

  ApiService({
    String? baseUrl,
    AuthStorageService? storage,
  })  : authStorage = storage ?? AuthStorageService(),
        baseUrl = _normalizeApiUrl(baseUrl ?? defaultBaseUrl);

  static String _normalizeApiUrl(String url) {
    String trimmed = url.trim();
    if (trimmed.isEmpty) return defaultBaseUrl;
    while (trimmed.endsWith('/')) {
      trimmed = trimmed.substring(0, trimmed.length - 1);
    }
    if (!trimmed.endsWith('/api')) {
      trimmed = '$trimmed/api';
    }
    return trimmed;
  }

  static String _rootFromApiUrl(String apiUrl) {
    final norm = _normalizeApiUrl(apiUrl);
    if (norm.endsWith('/api')) {
      return norm.substring(0, norm.length - 4);
    }
    return norm;
  }

  Future<bool> checkServerHealth(
    String candidateApiUrl, {
    Duration timeout = const Duration(milliseconds: 1200),
  }) async {
    try {
      final root = _rootFromApiUrl(candidateApiUrl);
      final resp = await http
          .get(Uri.parse('$root/health'))
          .timeout(timeout);
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<String> loadSavedBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_prefBaseUrlKey);

    final List<String> candidates = [
      if (saved != null && saved.trim().isNotEmpty) _normalizeApiUrl(saved),
      defaultBaseUrl,
      defaultLanBaseUrl,
      'http://10.0.2.2:8000/api',
    ];

    final Set<String> uniqueCandidates = LinkedHashSet<String>.from(candidates);

    for (final candidate in uniqueCandidates) {
      final ok = await checkServerHealth(candidate);
      if (ok) {
        baseUrl = candidate;
        isServerReachable = true;
        await prefs.setString(_prefBaseUrlKey, candidate);
        return baseUrl;
      }
    }

    baseUrl = defaultBaseUrl;
    isServerReachable = false;
    return baseUrl;
  }

  Future<bool> updateBaseUrl(String newUrl) async {
    final normalized = _normalizeApiUrl(newUrl);
    baseUrl = normalized;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefBaseUrlKey, normalized);
    isServerReachable = await checkServerHealth(normalized);
    return isServerReachable;
  }

  Future<Map<String, String>> _authHeaders() async {
    final token = await authStorage.getToken();
    if (token == null || token.isEmpty) {
      throw Exception('Oturum bulunamadı. Lütfen tekrar giriş yapın.');
    }
    return {
      'Authorization': 'Bearer $token',
      'Accept': 'application/json',
    };
  }

  /// POST /api/auth/register
  Future<String> register({
    required String email,
    required String password,
    required String fullName,
    bool rememberMe = true,
  }) async {
    http.Response response;
    try {
      response = await http
          .post(
            Uri.parse('$baseUrl/auth/register'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'email': email,
              'password': password,
              'full_name': fullName,
            }),
          )
          .timeout(const Duration(seconds: 8));
    } catch (_) {
      await loadSavedBaseUrl();
      response = await http
          .post(
            Uri.parse('$baseUrl/auth/register'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'email': email,
              'password': password,
              'full_name': fullName,
            }),
          )
          .timeout(const Duration(seconds: 8));
    }

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      final userMap = data['user'] as Map<String, dynamic>?;
      final returnedName = (userMap?['full_name'] as String?) ?? fullName;
      await authStorage.saveSession(
        token: token,
        email: email,
        fullName: returnedName,
        rememberMe: rememberMe,
      );
      return token;
    } else {
      final err = jsonDecode(response.body);
      throw Exception(err['detail'] ?? 'Kayıt işlemi başarısız oldu.');
    }
  }

  /// POST /api/auth/login
  Future<String> login({
    required String email,
    required String password,
    bool rememberMe = true,
  }) async {
    http.Response response;
    try {
      response = await http
          .post(
            Uri.parse('$baseUrl/auth/login'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'email': email,
              'password': password,
            }),
          )
          .timeout(const Duration(seconds: 8));
    } catch (_) {
      await loadSavedBaseUrl();
      response = await http
          .post(
            Uri.parse('$baseUrl/auth/login'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'email': email,
              'password': password,
            }),
          )
          .timeout(const Duration(seconds: 8));
    }

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      final userMap = data['user'] as Map<String, dynamic>?;
      final returnedName = userMap?['full_name'] as String?;
      await authStorage.saveSession(
        token: token,
        email: email,
        fullName: returnedName,
        rememberMe: rememberMe,
      );
      return token;
    } else {
      final err = jsonDecode(response.body);
      throw Exception(err['detail'] ?? 'Giriş başarısız. E-posta veya parola hatalı.');
    }
  }

  /// POST /api/keys/analyze-preview (Kaydetmeden önce görsel kanıtlı analiz önizlemesi)
  Future<KeyAnalysisPreview> analyzeKeyPreview({
    required Uint8List imageBytes,
    required String keyName,
    required String profileType,
  }) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/keys/analyze-preview');
    final request = http.MultipartRequest('POST', uri)
      ..headers.addAll(headers)
      ..fields['key_name'] = keyName
      ..fields['profile_type'] = profileType
      ..files.add(
        http.MultipartFile.fromBytes(
          'file',
          imageBytes,
          filename: 'in_memory_key_scan.png',
        ),
      );

    final streamedResponse =
        await request.send().timeout(const Duration(seconds: 25));
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return KeyAnalysisPreview.fromJson(data);
    } else {
      final err = jsonDecode(response.body);
      throw Exception(err['detail'] ?? 'Anahtar analizi başarısız oldu.');
    }
  }

  /// POST /api/keys/confirm-save (Kullanıcı onayladıktan sonra kasaya kaydetme)
  Future<KeyVaultItem> confirmAndSaveKey({
    required KeyAnalysisPreview preview,
    required String keyName,
    required String profileType,
  }) async {
    final headers = await _authHeaders();
    headers['Content-Type'] = 'application/json';
    final uri = Uri.parse('$baseUrl/keys/confirm-save');
    final response = await http
        .post(
          uri,
          headers: headers,
          body: jsonEncode({
            'key_name': keyName,
            'profile_type': profileType,
            'mode': preview.mode,
            'bitting_code': preview.bittingCode,
            'raw_depths_mm': preview.rawDepthsMm,
            'valley_positions_mm': preview.valleyPositionsMm,
            'macs_valid': preview.macsValid,
            'macs_state': preview.macsState,
            'scale_factor_k': preview.scaleFactorK,
            'vector_drawing_b64': preview.vectorDrawingB64,
          }),
        )
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return KeyVaultItem.fromJson(data);
    } else {
      final err = jsonDecode(response.body);
      throw Exception(err['detail'] ?? 'Anahtar kaydedilemedi.');
    }
  }

  /// POST /api/keys/scan-and-save
  Future<KeyVaultItem> scanAndSaveKey({
    required Uint8List imageBytes,
    required String keyName,
    required String profileType,
  }) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/keys/scan-and-save');
    final request = http.MultipartRequest('POST', uri)
      ..headers.addAll(headers)
      ..fields['key_name'] = keyName
      ..fields['profile_type'] = profileType
      ..files.add(
        http.MultipartFile.fromBytes(
          'file',
          imageBytes,
          filename: 'in_memory_key_scan.png',
        ),
      );

    final streamedResponse =
        await request.send().timeout(const Duration(seconds: 25));
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return KeyVaultItem.fromJson(data);
    } else {
      final err = jsonDecode(response.body);
      throw Exception(err['detail'] ?? 'Anahtar analizi başarısız oldu.');
    }
  }

  /// GET /api/keys/my-vault
  Future<List<KeyVaultItem>> fetchMyVault() async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/keys/my-vault');
    final response = await http
        .get(uri, headers: headers)
        .timeout(const Duration(seconds: 8));

    if (response.statusCode == 200) {
      final List<dynamic> list = jsonDecode(response.body) as List<dynamic>;
      return list
          .map((item) => KeyVaultItem.fromJson(item as Map<String, dynamic>))
          .toList();
    } else {
      throw Exception('Kasa listesi alınamadı (HTTP ${response.statusCode}).');
    }
  }

  /// DELETE /api/keys/{key_id}
  Future<void> deleteKey(int keyId) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/keys/$keyId');
    final response = await http
        .delete(uri, headers: headers)
        .timeout(const Duration(seconds: 8));

    if (response.statusCode != 204 && response.statusCode != 200) {
      throw Exception('Anahtar silinemedi (HTTP ${response.statusCode}).');
    }
  }

  /// GET /api/keys/{key_id}/export-gcode
  Future<String> downloadGCode(int keyId) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/keys/$keyId/export-gcode');
    final response = await http
        .get(uri, headers: headers)
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      return response.body;
    } else {
      throw Exception('CNC dosyası indirilemedi (HTTP ${response.statusCode}).');
    }
  }

  /// GET /api/keys/{key_id}/export-pdf
  Future<Uint8List> downloadCuttingCardPdf(int keyId) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/keys/$keyId/export-pdf');
    final response = await http
        .get(uri, headers: headers)
        .timeout(const Duration(seconds: 12));

    if (response.statusCode == 200) {
      return response.bodyBytes;
    } else {
      throw Exception('PDF Kesim Kartı indirilemedi (HTTP ${response.statusCode}).');
    }
  }
}
