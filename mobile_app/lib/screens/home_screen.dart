import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/auth_storage.dart';
import 'camera_scan_screen.dart';
import 'key_detail_export_screen.dart';
import 'login_lock_screen.dart';
import 'vault_list_screen.dart';

/// Giriş Sonrası Modern Ana Menü Ekranı
class HomeScreen extends StatefulWidget {
  final ApiService apiService;
  final AuthStorageService authStorage;

  const HomeScreen({
    super.key,
    required this.apiService,
    required this.authStorage,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _userName = '';
  String _userEmail = '';
  List<KeyVaultItem> _recentKeys = [];
  int _keyCount = 0;
  bool _loadingStats = true;

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
  }

  Future<void> _loadDashboardData() async {
    final fullName = await widget.authStorage.getUserFullName();
    final email = await widget.authStorage.getUserEmail();
    if (mounted) {
      setState(() {
        _userName = (fullName ?? '').trim();
        _userEmail = (email ?? '').trim();
      });
    }
    try {
      final keys = await widget.apiService.fetchMyVault();
      if (mounted) {
        setState(() {
          _keyCount = keys.length;
          _recentKeys = keys.take(3).toList();
          _loadingStats = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _loadingStats = false);
      }
    }
  }

  Future<void> _openAddKey() async {
    final result = await Navigator.of(context).push<KeyVaultItem>(
      MaterialPageRoute(
        builder: (_) => CameraScanScreen(apiService: widget.apiService),
      ),
    );
    if (result != null) {
      await _loadDashboardData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${result.keyName} dijital kasanıza eklendi.'),
            backgroundColor: const Color(0xFF10B981),
          ),
        );
      }
    }
  }

  Future<void> _openVault() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => VaultListScreen(
          apiService: widget.apiService,
          authStorage: widget.authStorage,
        ),
      ),
    );
    await _loadDashboardData();
  }

  Future<void> _openKeyDetail(KeyVaultItem item) async {
    final deleted = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => KeyDetailExportScreen(
          item: item,
          apiService: widget.apiService,
          authStorage: widget.authStorage,
        ),
      ),
    );
    if (deleted == true) {
      await _loadDashboardData();
    }
  }

  Future<void> _logout() async {
    await widget.authStorage.clearSession();
    if (mounted) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => LoginLockScreen(
            apiService: widget.apiService,
            authStorage: widget.authStorage,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final greetingTitle = _userName.isNotEmpty
        ? 'Hoş Geldin, $_userName'
        : 'KeyVault';

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadDashboardData,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Üst Başlık ve Çıkış
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            greetingTitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.w800,
                              letterSpacing: -0.5,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            _userEmail.isNotEmpty
                                ? _userEmail
                                : 'Dijital Anahtar Kasanız Hazır',
                            style: const TextStyle(
                              fontSize: 13,
                              color: Colors.white60,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    IconButton.filledTonal(
                      onPressed: _logout,
                      icon: const Icon(Icons.lock_outline_rounded),
                      tooltip: 'Kasayı Kilitle / Çıkış Yap',
                      style: IconButton.styleFrom(
                        backgroundColor: const Color(0xFF1E293B),
                        foregroundColor: Colors.white70,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 22),

                // Özet Durum Kartı
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(22),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF0284C7), Color(0xFF0F766E)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF0284C7).withOpacity(0.28),
                        blurRadius: 20,
                        offset: const Offset(0, 10),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.18),
                          borderRadius: BorderRadius.circular(18),
                        ),
                        child: const Icon(
                          Icons.shield_rounded,
                          color: Colors.white,
                          size: 34,
                        ),
                      ),
                      const SizedBox(width: 18),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Kişisel Anahtar Kasanız',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _loadingStats
                                  ? 'Yükleniyor...'
                                  : '$_keyCount Kayıtlı Anahtar',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 26),

                const Text(
                  'Hızlı İşlemler',
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 14),

                // Anahtar Ekle Kartı
                _MenuActionCard(
                  title: 'Anahtar Ekle',
                  subtitle:
                      'Fotoğraf çekin, kredi kartı referanslı diş analizini inceleyip onaylayın',
                  icon: Icons.add_a_photo_rounded,
                  accentColor: const Color(0xFF38BDF8),
                  onTap: _openAddKey,
                ),
                const SizedBox(height: 16),

                // Dijital Kasam Kartı
                _MenuActionCard(
                  title: 'Dijital Kasam',
                  subtitle:
                      'Kayıtlı anahtarlarınızı görüntüleyin, CNC (.gcode) veya PDF olarak indirin',
                  icon: Icons.vpn_key_rounded,
                  accentColor: const Color(0xFF34D399),
                  badgeText: _loadingStats ? null : '$_keyCount',
                  onTap: _openVault,
                ),

                if (_recentKeys.isNotEmpty) ...[
                  const SizedBox(height: 28),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Son Eklenen Anahtarlar',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                      TextButton(
                        onPressed: _openVault,
                        child: const Text(
                          'Tümünü Gör',
                          style: TextStyle(
                            color: Color(0xFF38BDF8),
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ..._recentKeys.map(
                    (item) => Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      decoration: BoxDecoration(
                        color: const Color(0xFF1E293B),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.06),
                        ),
                      ),
                      child: ListTile(
                        onTap: () => _openKeyDetail(item),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        leading: Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: const Color(0xFF38BDF8).withOpacity(0.14),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(
                            Icons.vpn_key_rounded,
                            color: Color(0xFF38BDF8),
                            size: 20,
                          ),
                        ),
                        title: Text(
                          item.keyName,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 15,
                          ),
                        ),
                        subtitle: Text(
                          'Marka/Profil: ${item.profileType} • ${item.rawDepthsMm.length} Diş',
                          style: const TextStyle(
                            color: Colors.white60,
                            fontSize: 12,
                          ),
                        ),
                        trailing: const Icon(
                          Icons.chevron_right_rounded,
                          color: Colors.white38,
                        ),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MenuActionCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color accentColor;
  final String? badgeText;
  final VoidCallback onTap;

  const _MenuActionCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.accentColor,
    this.badgeText,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xFF1E293B),
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: Colors.white.withOpacity(0.07)),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: accentColor.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(icon, color: accentColor, size: 30),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          title,
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                        if (badgeText != null) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 9,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: accentColor.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              badgeText!,
                              style: TextStyle(
                                color: accentColor,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 5),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 13,
                        color: Colors.white60,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(
                Icons.arrow_forward_ios_rounded,
                size: 16,
                color: Colors.white38,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
