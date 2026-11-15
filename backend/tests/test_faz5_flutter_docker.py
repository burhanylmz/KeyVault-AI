"""
FAZ 5 Birim ve Mimari Doğrulama Testleri (tests/test_faz5_flutter_docker.py)
- mobile_app/pubspec.yaml bağımlılıklarının (camera, local_auth, flutter_secure_storage, share_plus, http) kontrolü.
- 4 Flutter ekranının (login_lock_screen.dart, camera_scan_screen.dart, vault_list_screen.dart, key_detail_export_screen.dart) ve servis dosyalarının (api_service.dart, auth_storage.dart, main.dart) eksiksizliğinin kontrolü.
- backend/Dockerfile ve docker-compose.yml yapılandırmalarının doğrulanması.
"""

import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_faz5_flutter_mobile_files_and_dependencies():
    """pubspec.yaml ve tüm Dart ekran/servis dosyalarının eksiksiz oluşturulduğunu doğrula."""
    pubspec_path = os.path.join(ROOT_DIR, "mobile_app", "pubspec.yaml")
    assert os.path.isfile(pubspec_path), "pubspec.yaml bulunamadı!"

    with open(pubspec_path, "r", encoding="utf-8") as f:
        pubspec_content = f.read()

    for required_pkg in [
        "camera:",
        "local_auth:",
        "flutter_secure_storage:",
        "share_plus:",
        "http:",
    ]:
        assert required_pkg in pubspec_content, f"{required_pkg} pubspec.yaml içinde eksik!"

    required_dart_files = [
        ("mobile_app/lib/main.dart", "KeyVaultApp"),
        ("mobile_app/lib/services/api_service.dart", "scanAndSaveKey"),
        ("mobile_app/lib/services/auth_storage.dart", "authenticateWithBiometrics"),
        ("mobile_app/lib/screens/login_lock_screen.dart", "LoginLockScreen"),
        ("mobile_app/lib/screens/camera_scan_screen.dart", "CameraScanScreen"),
        ("mobile_app/lib/screens/vault_list_screen.dart", "VaultListScreen"),
        ("mobile_app/lib/screens/key_detail_export_screen.dart", "KeyDetailExportScreen"),
    ]

    for rel_path, expected_symbol in required_dart_files:
        abs_path = os.path.join(ROOT_DIR, rel_path)
        assert os.path.isfile(abs_path), f"{rel_path} bulunamadı!"
        with open(abs_path, "r", encoding="utf-8") as f:
            code = f.read()
        assert len(code) > 200, f"{rel_path} içeriği beklenenden kısa!"
        assert expected_symbol in code, f"{expected_symbol} sembolü {rel_path} içinde bulunamadı!"


def test_faz5_docker_and_compose_files():
    """Dockerfile ve docker-compose.yml dosyalarının varlığını ve içeriğini doğrula."""
    dockerfile_path = os.path.join(ROOT_DIR, "backend", "Dockerfile")
    compose_path = os.path.join(ROOT_DIR, "docker-compose.yml")

    assert os.path.isfile(dockerfile_path), "backend/Dockerfile bulunamadı!"
    assert os.path.isfile(compose_path), "docker-compose.yml bulunamadı!"

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        dockerfile_text = f.read()
    assert "uvicorn" in dockerfile_text
    assert "app.main:app" in dockerfile_text

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_text = f.read()
    assert "keyvault-backend:" in compose_text
    assert "8000:8000" in compose_text
