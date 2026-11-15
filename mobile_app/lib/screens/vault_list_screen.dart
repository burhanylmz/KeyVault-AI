import 'dart:convert';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/auth_storage.dart';
import 'camera_scan_screen.dart';
import 'key_detail_export_screen.dart';

/// Dijital Anahtar Kasası Liste Ekranı
class VaultListScreen extends StatefulWidget {
  final ApiService apiService;
  final AuthStorageService authStorage;

  const VaultListScreen({
    super.key,
    required this.apiService,
    required this.authStorage,
  });

  @override
  State<VaultListScreen> createState() => _VaultListScreenState();
}

class _VaultListScreenState extends State<VaultListScreen> {
  List<KeyVaultItem> _keys = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadVaultItems();
  }

  Future<void> _loadVaultItems() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final items = await widget.apiService.fetchMyVault();
      if (mounted) {
        setState(() => _keys = items);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _openCameraScanner() async {
    final result = await Navigator.of(context).push<KeyVaultItem>(
      MaterialPageRoute(
        builder: (_) => CameraScanScreen(apiService: widget.apiService),
      ),
    );
    if (result != null) {
      await _loadVaultItems();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Dijital Kasam',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            onPressed: _loadVaultItems,
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Yenile',
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCameraScanner,
        backgroundColor: const Color(0xFF0EA5E9),
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add_a_photo_rounded),
        label: const Text(
          'Anahtar Ekle',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.redAccent),
                    ),
                  ),
                )
              : _keys.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(32.0),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              padding: const EdgeInsets.all(22),
                              decoration: BoxDecoration(
                                color: Colors.white.withOpacity(0.05),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.vpn_key_off_rounded,
                                size: 52,
                                color: Colors.white38,
                              ),
                            ),
                            const SizedBox(height: 18),
                            const Text(
                              'Kasanızda henüz kayıtlı anahtar yok',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              'Sağ alttaki "Anahtar Ekle" butonuna dokunarak ilk anahtarınızı ekleyebilirsiniz.',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: Colors.white60, fontSize: 14),
                            ),
                          ],
                        ),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _loadVaultItems,
                      child: ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 90),
                        itemCount: _keys.length,
                        itemBuilder: (context, index) {
                          final item = _keys[index];
                          return _ModernKeyCard(
                            item: item,
                            onTap: () async {
                              final deleted =
                                  await Navigator.of(context).push<bool>(
                                MaterialPageRoute(
                                  builder: (_) => KeyDetailExportScreen(
                                    item: item,
                                    apiService: widget.apiService,
                                    authStorage: widget.authStorage,
                                  ),
                                ),
                              );
                              if (deleted == true) {
                                await _loadVaultItems();
                              }
                            },
                          );
                        },
                      ),
                    ),
    );
  }
}

class _ModernKeyCard extends StatelessWidget {
  final KeyVaultItem item;
  final VoidCallback onTap;

  const _ModernKeyCard({
    required this.item,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final bool isReady = item.macsValid;
    final Color statusColor = isReady ? const Color(0xFF34D399) : Colors.amberAccent;
    final String codeText = item.bittingCode ?? '${item.rawDepthsMm.length} Dişli Özel Profil';

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withOpacity(0.07)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.18),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              children: [
                // Sol İkon / Küçük 2D Önizleme
                Container(
                  width: 58,
                  height: 58,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        statusColor.withOpacity(0.22),
                        const Color(0xFF0EA5E9).withOpacity(0.16),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: item.vectorDrawingB64 != null && item.vectorDrawingB64!.isNotEmpty
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(16),
                          child: Image.memory(
                            base64Decode(item.vectorDrawingB64!),
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Icon(
                              Icons.vpn_key_rounded,
                              color: statusColor,
                              size: 28,
                            ),
                          ),
                        )
                      : Icon(
                          Icons.vpn_key_rounded,
                          color: statusColor,
                          size: 28,
                        ),
                ),
                const SizedBox(width: 16),

                // Anahtar Başlığı & Profil Rozeti
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.keyName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 9,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0EA5E9).withOpacity(0.15),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              item.profileType,
                              style: const TextStyle(
                                color: Color(0xFF38BDF8),
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Flexible(
                            child: Text(
                              codeText,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 13,
                                color: Colors.white70,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.05),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.arrow_forward_ios_rounded,
                    size: 16,
                    color: Colors.white60,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
