import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'auth_storage.dart';

/// KeyVault-AI Anahtar Modeli (Bitting, Ham Derinlikler, MACS Durumu ve 2D Vektör Çizimi)
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

/// FastAPI Backend ile İletişim Kuran REST API Servisi
class ApiService {
  String baseUrl;
  final AuthStorageService authStorage;

  ApiService({
    String? baseUrl,
    AuthStorageService? storage,
  })  : authStorage = storage ?? AuthStorageService(),
        baseUrl = baseUrl ?? resolveDefaultBaseUrl();

  /// Chrome (Web), Android Emülatör ve Tablet/Fiziksel cihazlar için
  /// çalışma zamanında dinamik Backend URL ve Port çözümler.
  static String resolveDefaultBaseUrl() {
    const String envUrl = String.fromEnvironment('API_BASE_URL', defaultValue: '');
    if (envUrl.isNotEmpty) {
      return envUrl.endsWith('/') ? envUrl.substring(0, envUrl.length - 1) : envUrl;
    }

    const String port = String.fromEnvironment('API_PORT', defaultValue: '8000');

    if (kIsWeb) {
      final host = Uri.base.host.isNotEmpty ? Uri.base.host : '127.0.0.1';
      return 'http://$host:$port';
    }

    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:$port';
    }

    return 'http://127.0.0.1:$port';
  }

  /// Kayıtlı özel sunucu adresi varsa yükler (Tablet/LAN IP için).
  Future<void> loadSavedBaseUrl() async {
    final saved = await authStorage.getBaseUrl();
    if (saved != null && saved.isNotEmpty) {
      baseUrl = saved.endsWith('/') ? saved.substring(0, saved.length - 1) : saved;
    }
  }

  /// Sunucu adresini (veya portunu) çalışma zamanında günceller ve kaydeder.
  Future<void> updateBaseUrl(String newUrl) async {
    final cleaned = newUrl.trim();
    if (cleaned.isEmpty) return;
    baseUrl = cleaned.endsWith('/') ? cleaned.substring(0, cleaned.length - 1) : cleaned;
    await authStorage.saveBaseUrl(baseUrl);
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
  }) async {
    final uri = Uri.parse('$baseUrl/api/auth/register');
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
        'full_name': fullName,
      }),
    );

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      await authStorage.saveSession(token: token, email: email);
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
  }) async {
    final uri = Uri.parse('$baseUrl/api/auth/login');
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = data['access_token'] as String;
      await authStorage.saveSession(token: token, email: email);
      return token;
    } else {
      final err = jsonDecode(response.body);
      throw Exception(err['detail'] ?? 'Giriş başarısız. E-posta veya parola hatalı.');
    }
  }

  /// POST /api/keys/scan-and-save (In-Memory görüntü gönderimi, diske kaydetmez)
  Future<KeyVaultItem> scanAndSaveKey({
    required Uint8List imageBytes,
    required String keyName,
    required String profileType,
  }) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/api/keys/scan-and-save');
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

    final streamedResponse = await request.send();
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
    final uri = Uri.parse('$baseUrl/api/keys/my-vault');
    final response = await http.get(uri, headers: headers);

    if (response.statusCode == 200) {
      final List<dynamic> list = jsonDecode(response.body) as List<dynamic>;
      return list
          .map((item) => KeyVaultItem.fromJson(item as Map<String, dynamic>))
          .toList();
    } else {
      throw Exception('Kasa listesi alınamadı (HTTP ${response.statusCode}).');
    }
  }

  /// GET /api/keys/{key_id}/export-gcode
  Future<String> downloadGCode(int keyId) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/api/keys/$keyId/export-gcode');
    final response = await http.get(uri, headers: headers);

    if (response.statusCode == 200) {
      return response.body;
    } else {
      throw Exception('CNC G-Code indirilemedi (HTTP ${response.statusCode}).');
    }
  }

  /// GET /api/keys/{key_id}/export-pdf
  Future<Uint8List> downloadCuttingCardPdf(int keyId) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$baseUrl/api/keys/$keyId/export-pdf');
    final response = await http.get(uri, headers: headers);

    if (response.statusCode == 200) {
      return response.bodyBytes;
    } else {
      throw Exception('PDF Kesim Kartı indirilemedi (HTTP ${response.statusCode}).');
    }
  }
}
