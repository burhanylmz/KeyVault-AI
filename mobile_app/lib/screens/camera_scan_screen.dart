import 'dart:convert';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../services/api_service.dart';

/// 2 Aşamalı Kamera Tarama Ekranı:
/// 1. Fotoğraf çekildiği an görüntüyü dondurur (kullanıcı elini sabit tutmak zorunda kalmaz) ve analiz eder.
/// 2. Kredi kartı kalibrasyon çerçevesi ve diş derinliklerinin fotoğraf üzerine çizildiği
///    "Görsel Kanıt ve Onay Ekranı"nı açar; kullanıcı onaylarsa dijital kasaya kaydeder.
class CameraScanScreen extends StatefulWidget {
  final ApiService apiService;

  const CameraScanScreen({
    super.key,
    required this.apiService,
  });

  @override
  State<CameraScanScreen> createState() => _CameraScanScreenState();
}

class _CameraScanScreenState extends State<CameraScanScreen> {
  CameraController? _cameraController;
  bool _isCameraInitialized = false;
  bool _isFlashOn = false;
  bool _isAnalyzing = false;
  bool _isSaving = false;
  bool _showVectorTab = false;

  Uint8List? _capturedPhotoBytes;
  KeyAnalysisPreview? _previewResult;

  String _selectedProfile = 'AUTO';
  final TextEditingController _keyNameController =
      TextEditingController(text: 'Ana Giriş Anahtarı');
  final TextEditingController _brandEditController = TextEditingController();

  final List<Map<String, String>> _profiles = const [
    {'value': 'AUTO', 'label': 'Otomatik Tanı (Tüm Markalar)'},
    {'value': 'BAY-TEC', 'label': 'BAY-TEC'},
    {'value': 'KALE-KILIT', 'label': 'KALE Kilit'},
    {'value': 'YALE-5', 'label': 'YALE (5 Pim)'},
    {'value': 'YALE-6', 'label': 'YALE (6 Pim)'},
    {'value': 'ITO-KILIT', 'label': 'İTO Kilit'},
    {'value': 'BKS', 'label': 'BKS'},
    {'value': 'DAF', 'label': 'DAF Kilit'},
    {'value': 'CUSTOM', 'label': 'Diğer / Özel Marka Yaz...'},
  ];

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isNotEmpty) {
        final backCamera = cameras.firstWhere(
          (c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => cameras.first,
        );
        _cameraController = CameraController(
          backCamera,
          ResolutionPreset.high,
          enableAudio: false,
        );
        await _cameraController!.initialize();
        if (mounted) {
          setState(() => _isCameraInitialized = true);
        }
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isCameraInitialized = false);
      }
    }
  }

  Future<void> _toggleFlash() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }
    try {
      final nextState = !_isFlashOn;
      await _cameraController!.setFlashMode(
        nextState ? FlashMode.torch : FlashMode.off,
      );
      if (mounted) {
        setState(() => _isFlashOn = nextState);
      }
    } catch (_) {}
  }

  /// 1. Aşama: Fotoğrafı çeker, ekranı anında dondurur (el titremesini önler)
  /// ve sunucudan görsel kanıtlı analiz önizlemesini alır.
  Future<void> _captureAndPreview() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }

    try {
      final XFile captured = await _cameraController!.takePicture();
      final Uint8List rawBytes = await captured.readAsBytes();

      if (_isFlashOn) {
        try {
          await _cameraController!.setFlashMode(FlashMode.off);
          _isFlashOn = false;
        } catch (_) {}
      }

      // Fotoğraf çekildiği anda ekranda dondur (kullanıcı elini çekebilir)
      setState(() {
        _capturedPhotoBytes = rawBytes;
        _isAnalyzing = true;
        _previewResult = null;
      });

      String profileToSend = _selectedProfile;
      if (_selectedProfile == 'CUSTOM') {
        final custom = _brandEditController.text.trim();
        profileToSend = custom.isEmpty ? 'AUTO' : custom.toUpperCase();
      }

      final KeyAnalysisPreview preview =
          await widget.apiService.analyzeKeyPreview(
        imageBytes: rawBytes,
        keyName: _keyNameController.text.trim().isEmpty
            ? 'Ana Giriş Anahtarı'
            : _keyNameController.text.trim(),
        profileType: profileToSend,
      );

      if (mounted) {
        setState(() {
          _previewResult = preview;
          _keyNameController.text = preview.keyName;
          _brandEditController.text = preview.profileType;
          _showVectorTab = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _capturedPhotoBytes = null;
          _previewResult = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceFirst('Exception: ', '')),
            backgroundColor: Colors.redAccent,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isAnalyzing = false);
      }
    }
  }

  /// 2. Aşama: Kullanıcı analiz sonucunu ve görsel kanıtı onayladığında kasaya kaydeder.
  Future<void> _confirmAndSaveToVault() async {
    final preview = _previewResult;
    if (preview == null) return;

    setState(() => _isSaving = true);
    try {
      final savedItem = await widget.apiService.confirmAndSaveKey(
        preview: preview,
        keyName: _keyNameController.text.trim().isEmpty
            ? preview.keyName
            : _keyNameController.text.trim(),
        profileType: _brandEditController.text.trim().isEmpty
            ? preview.profileType
            : _brandEditController.text.trim().toUpperCase(),
      );

      if (_capturedPhotoBytes != null) {
        _capturedPhotoBytes!.fillRange(0, _capturedPhotoBytes!.length, 0);
      }

      if (mounted) {
        Navigator.of(context).pop(savedItem);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceFirst('Exception: ', '')),
            backgroundColor: Colors.redAccent,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isSaving = false);
      }
    }
  }

  void _retakePhoto() {
    if (_capturedPhotoBytes != null) {
      _capturedPhotoBytes!.fillRange(0, _capturedPhotoBytes!.length, 0);
    }
    setState(() {
      _capturedPhotoBytes = null;
      _previewResult = null;
      _isAnalyzing = false;
    });
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    _keyNameController.dispose();
    _brandEditController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool isInPreviewState = _previewResult != null;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          isInPreviewState ? 'Analiz Doğrulama ve Onay' : 'Anahtar Tarayıcı',
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          if (!isInPreviewState && _isCameraInitialized)
            IconButton(
              onPressed: _toggleFlash,
              icon: Icon(
                _isFlashOn ? Icons.flash_on_rounded : Icons.flash_off_rounded,
                color: _isFlashOn ? Colors.amberAccent : Colors.white70,
              ),
              tooltip: 'Feneri Aç / Kapat',
            ),
        ],
      ),
      body: isInPreviewState
          ? _buildApprovalResultView(_previewResult!)
          : _buildCameraCaptureView(),
    );
  }

  Widget _buildCameraCaptureView() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(14, 6, 14, 10),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    flex: 5,
                    child: TextField(
                      controller: _keyNameController,
                      decoration: InputDecoration(
                        labelText: 'Anahtar Başlığı',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    flex: 5,
                    child: DropdownButtonFormField<String>(
                      value: _selectedProfile,
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: 'Marka / Profil',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        isDense: true,
                      ),
                      items: _profiles
                          .map(
                            (p) => DropdownMenuItem(
                              value: p['value'],
                              child: Text(
                                p['label']!,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 13),
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (val) {
                        if (val != null) {
                          setState(() => _selectedProfile = val);
                        }
                      },
                    ),
                  ),
                ],
              ),
              if (_selectedProfile == 'CUSTOM') ...[
                const SizedBox(height: 10),
                TextField(
                  controller: _brandEditController,
                  decoration: InputDecoration(
                    labelText: 'Anahtar Üzerindeki Marka / Model Adı',
                    hintText: 'Örn: BAY-TEC, KALE, MULTLOCK...',
                    prefixIcon: const Icon(Icons.label_outline_rounded),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    isDense: true,
                  ),
                ),
              ],
            ],
          ),
        ),
        Expanded(
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Fotoğraf çekildiği an donmuş kareyi göster (sabit tutma zorunluluğunu kaldırır)
              if (_capturedPhotoBytes != null)
                Image.memory(
                  _capturedPhotoBytes!,
                  fit: BoxFit.contain,
                  width: double.infinity,
                )
              else if (_isCameraInitialized && _cameraController != null)
                CameraPreview(_cameraController!)
              else
                Container(
                  color: Colors.black87,
                  alignment: Alignment.center,
                  child: const Text(
                    'Kamera Önizlemesi\n(Kart ve Anahtarı Kadraj İçine Yerleştirin)',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.white70),
                  ),
                ),

              if (_isAnalyzing)
                Container(
                  color: Colors.black.withOpacity(0.65),
                  alignment: Alignment.center,
                  child: Container(
                    padding: const EdgeInsets.all(24),
                    margin: const EdgeInsets.symmetric(horizontal: 32),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1E293B),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircularProgressIndicator(color: Color(0xFF38BDF8)),
                        SizedBox(height: 18),
                        Text(
                          'Fotoğraf Alındı! Elinizi Çekebilirsiniz',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(height: 6),
                        Text(
                          'Kredi kartı referans kalibrasyonu, marka okuma ve diş derinlik analizi yapılıyor...',
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 13, color: Colors.white70),
                        ),
                      ],
                    ),
                  ),
                )
              else
                IgnorePointer(
                  child: Container(
                    margin: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: const Color(0xFF38BDF8).withOpacity(0.85),
                        width: 2.5,
                      ),
                      borderRadius: BorderRadius.circular(22),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Container(
                          margin: const EdgeInsets.only(top: 12),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.65),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Text(
                            'Kart ve Anahtarın Tamamı Bu Çerçevede Olsun (Otomatik Hizalanır)',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Color(0xFF38BDF8),
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        Container(
                          margin: const EdgeInsets.only(bottom: 12),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.65),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Text(
                            'Fotoğraf çekildikten sonra analiz kanıtı onayınıza sunulacaktır',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 11,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16.0),
          child: SizedBox(
            width: double.infinity,
            height: 54,
            child: FilledButton.icon(
              onPressed: _isAnalyzing ? null : _captureAndPreview,
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF0EA5E9),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              icon: const Icon(Icons.camera_alt_rounded),
              label: const Text(
                'Fotoğraf Çek ve Analiz Et',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ),
      ],
    );
  }

  /// 2. Aşama Görünümü: Çekilen fotoğrafın üzerinde kredi kartı kalibrasyon kanıtı,
  /// diş derinlikleri, düzenlenebilir marka/başlık ve Onayla/Kaydet butonu.
  Widget _buildApprovalResultView(KeyAnalysisPreview preview) {
    Uint8List? proofPhotoBytes;
    if (preview.annotatedPhotoB64 != null &&
        preview.annotatedPhotoB64!.isNotEmpty) {
      try {
        proofPhotoBytes = base64Decode(preview.annotatedPhotoB64!);
      } catch (_) {}
    }

    Uint8List? vectorBytes;
    if (preview.vectorDrawingB64 != null &&
        preview.vectorDrawingB64!.isNotEmpty) {
      try {
        vectorBytes = base64Decode(preview.vectorDrawingB64!);
      } catch (_) {}
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Kalibrasyon Doğrulama Rozeti
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withOpacity(0.14),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: const Color(0xFF10B981).withOpacity(0.5),
              ),
            ),
            child: Row(
              children: [
                const Icon(
                  Icons.verified_rounded,
                  color: Color(0xFF34D399),
                  size: 24,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Referans Kart Kalibrasyonu Doğrulandı (85.60 mm = ${preview.cardPixelWidth.toStringAsFixed(0)} px  •  1 px = ${preview.scaleFactorK.toStringAsFixed(3)} mm)',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Görsel Sekme Seçici: Kanıt Fotoğrafı vs 2D CNC Çizimi
          Row(
            children: [
              Expanded(
                child: ChoiceChip(
                  label: const Text('Çekilen Fotoğraf & Kanıt'),
                  selected: !_showVectorTab,
                  onSelected: (_) => setState(() => _showVectorTab = false),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: ChoiceChip(
                  label: const Text('2D Teknik CNC Çizimi'),
                  selected: _showVectorTab,
                  onSelected: (_) => setState(() => _showVectorTab = true),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Görsel Kanıt Kutusu
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(maxHeight: 280),
            decoration: BoxDecoration(
              color: _showVectorTab ? Colors.white : const Color(0xFF0F172A),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: Colors.white.withOpacity(0.12)),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(18),
              child: _showVectorTab && vectorBytes != null
                  ? Image.memory(vectorBytes, fit: BoxFit.contain)
                  : (proofPhotoBytes != null
                      ? Image.memory(proofPhotoBytes, fit: BoxFit.contain)
                      : (_capturedPhotoBytes != null
                          ? Image.memory(_capturedPhotoBytes!, fit: BoxFit.contain)
                          : const SizedBox(height: 180))),
            ),
          ),
          const SizedBox(height: 16),

          // Düzenlenebilir Anahtar Başlığı ve Tespit Edilen Marka
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _keyNameController,
                  decoration: InputDecoration(
                    labelText: 'Anahtar Başlığı',
                    prefixIcon: const Icon(Icons.edit_note_rounded),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _brandEditController,
                  decoration: InputDecoration(
                    labelText: 'Tespit Edilen Marka',
                    prefixIcon: const Icon(Icons.workspace_premium_rounded),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    isDense: true,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),

          // Tam Kumpas & Anahtarcı Milimetrik Ölçüm Kartı
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF1E293B),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: Colors.white.withOpacity(0.08)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Fabrika Bitting Kodu:',
                      style: TextStyle(color: Colors.white70, fontSize: 13),
                    ),
                    Flexible(
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: const Color(0xFF38BDF8).withOpacity(0.18),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          preview.bittingCode ??
                              'Tablo Yok (Milimetrik CNC / RAW)',
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Color(0xFF38BDF8),
                            fontWeight: FontWeight.bold,
                            fontSize: 12.5,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const Divider(height: 20),
                const Text(
                  '1. Genel Anahtar Kumpas Ölçüleri:',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13.5,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _buildMetricBadge(
                      'Toplam Boy',
                      '${preview.totalLengthMm.toStringAsFixed(2)} mm',
                    ),
                    _buildMetricBadge(
                      'Namlu Boyu (X=0→Uç)',
                      '${preview.bladeLengthMm.toStringAsFixed(2)} mm',
                    ),
                    _buildMetricBadge(
                      'Kesilmemiş Namlu Eni',
                      '${preview.bladeWidthMm.toStringAsFixed(2)} mm',
                    ),
                    _buildMetricBadge(
                      'Baş (Bow) Genişliği',
                      '${preview.bowHeightMm.toStringAsFixed(2)} mm',
                    ),
                  ],
                ),
                const Divider(height: 22),
                const Text(
                  '2. Diş Konumu (X), Aralık (ΔX), Derinlik ve Kalan Kalınlık:',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13.5,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 10),
                ...List.generate(preview.rawDepthsMm.length, (idx) {
                  final d = preview.rawDepthsMm[idx];
                  final x = idx < preview.valleyPositionsMm.length
                      ? preview.valleyPositionsMm[idx]
                      : (4.0 + idx * 4.5);
                  final dx = idx == 0
                      ? x
                      : (x -
                          (idx - 1 < preview.valleyPositionsMm.length
                              ? preview.valleyPositionsMm[idx - 1]
                              : (4.0 + (idx - 1) * 4.5)));
                  final rem = idx < preview.remainingHeightsMm.length
                      ? preview.remainingHeightsMm[idx]
                      : (preview.bladeWidthMm > d
                          ? preview.bladeWidthMm - d
                          : 0.0);
                  return Container(
                    margin: const EdgeInsets.only(bottom: 7),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: Colors.white12),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Diş #${idx + 1}',
                          style: const TextStyle(
                            fontSize: 12.5,
                            color: Color(0xFF38BDF8),
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          'X: ${x.toStringAsFixed(2)}mm (ΔX:${dx.toStringAsFixed(2)})',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.white70,
                          ),
                        ),
                        Text(
                          'Derinlik: -${d.toStringAsFixed(2)}mm  •  Kalan: ${rem.toStringAsFixed(2)}mm',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
          const SizedBox(height: 18),

          // Alt Onay / Yeniden Çek Butonları
          Row(
            children: [
              Expanded(
                flex: 4,
                child: SizedBox(
                  height: 52,
                  child: OutlinedButton.icon(
                    onPressed: _isSaving ? null : _retakePhoto,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white24),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: const Icon(Icons.replay_rounded),
                    label: const Text('Yeniden Çek'),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 6,
                child: SizedBox(
                  height: 52,
                  child: FilledButton.icon(
                    onPressed: _isSaving ? null : _confirmAndSaveToVault,
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFF10B981),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: _isSaving
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.check_circle_rounded),
                    label: const Text(
                      'Onayla ve Kasaya Kaydet',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14.5,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetricBadge(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: const TextStyle(color: Colors.white60, fontSize: 11),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
