import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import '../services/api_service.dart';

/// ISO/IEC 7810 Referans Kart (85.60mm x 53.98mm) Hizalama Kılavuzlu
/// In-Memory Kamera Tarama Ekranı
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
  bool _isAnalyzing = false;
  String _selectedProfile = 'YALE-5';
  final TextEditingController _keyNameController =
      TextEditingController(text: 'Ana Giris Kapisi');

  final List<String> _profiles = const [
    'YALE-5',
    'YALE-6',
    'KALE-KILIT',
    'ITO-KILIT',
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

  Future<void> _captureAndAnalyzeInMemory() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }

    setState(() => _isAnalyzing = true);
    try {
      final XFile captured = await _cameraController!.takePicture();
      final Uint8List rawBytes = await captured.readAsBytes();

      final String cleanProfile = _selectedProfile.split(' ').first;
      final KeyVaultItem savedItem = await widget.apiService.scanAndSaveKey(
        imageBytes: rawBytes,
        keyName: _keyNameController.text.trim().isEmpty
            ? 'Yeni Anahtar'
            : _keyNameController.text.trim(),
        profileType: cleanProfile,
      );

      // RAM'deki yerel byte tamponunu sıfırla (Data Remanence önlemi)
      rawBytes.fillRange(0, rawBytes.length, 0);

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
        setState(() => _isAnalyzing = false);
      }
    }
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    _keyNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Optik Anahtar ve Kart Tarayıcı'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _keyNameController,
                    decoration: const InputDecoration(
                      labelText: 'Anahtar Adı',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                DropdownButton<String>(
                  value: _selectedProfile,
                  items: _profiles
                      .map((p) => DropdownMenuItem(value: p, child: Text(p)))
                      .toList(),
                  onChanged: (val) {
                    if (val != null) {
                      setState(() => _selectedProfile = val);
                    }
                  },
                ),
              ],
            ),
          ),
          Expanded(
            child: Stack(
              alignment: Alignment.center,
              children: [
                if (_isCameraInitialized && _cameraController != null)
                  CameraPreview(_cameraController!)
                else
                  Container(
                    color: Colors.black87,
                    alignment: Alignment.center,
                    child: const Text(
                      'Kamera Önizlemesi\n(Referans Kart ve Anahtar Hizalama Alanı)',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white70),
                    ),
                  ),
                // Referans Kart ve Anahtar Hizalama Kılavuzu
                IgnorePointer(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 28.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          height: 150,
                          width: 240,
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.cyanAccent, width: 2.5),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          alignment: Alignment.topLeft,
                          padding: const EdgeInsets.all(8),
                          child: const Text(
                            'Referans Kart (Kredi Kartı Boyutu)',
                            style: TextStyle(
                              color: Colors.cyanAccent,
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        const SizedBox(height: 28),
                        Container(
                          height: 95,
                          width: 260,
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.amberAccent, width: 2.5),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          alignment: Alignment.topLeft,
                          padding: const EdgeInsets.all(8),
                          child: const Text(
                            'Anahtar Alanı (Düz ve Net Yerleştirin)',
                            style: TextStyle(
                              color: Colors.amberAccent,
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
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
              height: 52,
              child: FilledButton.icon(
                onPressed: _isAnalyzing ? null : _captureAndAnalyzeInMemory,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF0EA5E9),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                icon: _isAnalyzing
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.camera_alt_rounded),
                label: Text(
                  _isAnalyzing
                      ? 'Anahtar Analiz Ediliyor...'
                      : 'Fotoğraf Çek ve Kasaya Kaydet',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
