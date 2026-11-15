import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import '../services/api_service.dart';
import '../services/auth_storage.dart';

/// Anahtar Detay, 2D Görünüm ve CNC / PDF Kesim Kartı İndirme Ekranı
class KeyDetailExportScreen extends StatefulWidget {
  final KeyVaultItem item;
  final ApiService apiService;
  final AuthStorageService authStorage;

  const KeyDetailExportScreen({
    super.key,
    required this.item,
    required this.apiService,
    required this.authStorage,
  });

  @override
  State<KeyDetailExportScreen> createState() => _KeyDetailExportScreenState();
}

class _KeyDetailExportScreenState extends State<KeyDetailExportScreen> {
  bool _isExporting = false;
  bool _isDeleting = false;

  Future<void> _exportAndShareGCode() async {
    setState(() => _isExporting = true);
    try {
      final gcodeText = await widget.apiService.downloadGCode(widget.item.id);
      final tempDir = await getTemporaryDirectory();
      final file = File('${tempDir.path}/keyvault_${widget.item.id}.gcode');
      await file.writeAsString(gcodeText);

      await Share.shareXFiles(
        [XFile(file.path)],
        subject: 'CNC Kesim Dosyası (${widget.item.keyName})',
      );
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
        setState(() => _isExporting = false);
      }
    }
  }

  Future<void> _exportAndSharePdfCard() async {
    setState(() => _isExporting = true);
    try {
      final Uint8List pdfBytes =
          await widget.apiService.downloadCuttingCardPdf(widget.item.id);
      final tempDir = await getTemporaryDirectory();
      final file =
          File('${tempDir.path}/keyvault_${widget.item.id}_kesim_karti.pdf');
      await file.writeAsBytes(pdfBytes);

      await Share.shareXFiles(
        [XFile(file.path)],
        subject: 'Anahtar Kesim Kartı (${widget.item.keyName})',
      );
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
        setState(() => _isExporting = false);
      }
    }
  }

  Future<void> _confirmAndDeleteKey() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text(
          'Anahtarı Sil',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        content: Text(
          '"${widget.item.keyName}" anahtarını dijital kasanızdan kalıcı olarak silmek istediğinize emin misiniz?',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Vazgeç'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text('Sil'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() => _isDeleting = true);
    try {
      await widget.apiService.deleteKey(widget.item.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${widget.item.keyName} kasadan silindi.'),
            backgroundColor: const Color(0xFF10B981),
          ),
        );
        Navigator.of(context).pop(true);
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
        setState(() => _isDeleting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    Uint8List? vectorImageBytes;
    if (item.vectorDrawingB64 != null && item.vectorDrawingB64!.isNotEmpty) {
      try {
        vectorImageBytes = base64Decode(item.vectorDrawingB64!);
      } catch (_) {
        vectorImageBytes = null;
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Anahtar Detayı'),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            onPressed: _isDeleting ? null : _confirmAndDeleteKey,
            icon: const Icon(
              Icons.delete_outline_rounded,
              color: Colors.redAccent,
            ),
            tooltip: 'Anahtarı Sil',
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Anahtar Başlık ve Durum Kartı
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF1E293B), Color(0xFF0F172A)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFF38BDF8).withOpacity(0.15),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: const Icon(
                          Icons.vpn_key_rounded,
                          color: Color(0xFF38BDF8),
                          size: 26,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.keyName,
                              style: const TextStyle(
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Marka / Profil: ${item.profileType}',
                              style: const TextStyle(
                                fontSize: 13,
                                color: Colors.white60,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 10,
                    runSpacing: 8,
                    children: [
                      _InfoChip(
                        icon: Icons.tag_rounded,
                        label: item.bittingCode ?? 'Özel Milimetrik Profil',
                        color: const Color(0xFF38BDF8),
                      ),
                      _InfoChip(
                        icon: item.macsValid
                            ? Icons.check_circle_rounded
                            : Icons.warning_amber_rounded,
                        label:
                            item.macsValid ? 'Üretime Uygun' : 'Kesim Uyarısı',
                        color: item.macsValid
                            ? const Color(0xFF34D399)
                            : Colors.amberAccent,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),

            // 2D Teknik Vektör Çizimi
            if (vectorImageBytes != null) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(14),
                  child: Image.memory(
                    vectorImageBytes,
                    width: double.infinity,
                    fit: BoxFit.contain,
                  ),
                ),
              ),
              const SizedBox(height: 18),
            ],

            // İndirme Butonları (CNC ve PDF)
            SizedBox(
              width: double.infinity,
              height: 54,
              child: FilledButton.icon(
                onPressed: _isExporting ? null : _exportAndShareGCode,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF0EA5E9),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                icon: _isExporting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.precision_manufacturing_rounded),
                label: const Text(
                  'CNC Dosyasını İndir (.gcode)',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                ),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: OutlinedButton.icon(
                onPressed: _isExporting ? null : _exportAndSharePdfCard,
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: BorderSide(color: Colors.white.withOpacity(0.2)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                icon: const Icon(Icons.picture_as_pdf_rounded),
                label: const Text(
                  'Kesim Kartını İndir (PDF)',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Diş Ölçümleri Özeti
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white.withOpacity(0.06)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Diş Derinlik Ölçümleri (Referans: 85.60 mm Kart)',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 12),
                  ...List.generate(item.rawDepthsMm.length, (idx) {
                    final xPos = idx < item.valleyPositionsMm.length
                        ? item.valleyPositionsMm[idx]
                        : (4.0 + idx * 4.5);
                    final dx = idx == 0
                        ? xPos
                        : (xPos -
                            (idx - 1 < item.valleyPositionsMm.length
                                ? item.valleyPositionsMm[idx - 1]
                                : (4.0 + (idx - 1) * 4.5)));
                    final depth = item.rawDepthsMm[idx];
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 5.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Diş #${idx + 1} (D${idx + 1})',
                            style: const TextStyle(
                              color: Colors.white70,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          Text(
                            'X: ${xPos.toStringAsFixed(2)} mm (ΔX: ${dx.toStringAsFixed(2)})  •  Derinlik: -${depth.toStringAsFixed(2)} mm',
                            style: const TextStyle(
                              color: Colors.white60,
                              fontSize: 12.5,
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _InfoChip({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
