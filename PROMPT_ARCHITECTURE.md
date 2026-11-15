# PROJE ADI: KeyVault-AI — Otonom Geliştirme ve Test Protokolü (5 Fazlı Mimari)

## 🚨 OTONOM ÇALIŞMA KURALLARI (AGENT DIRECTIVES - KESİN UYULACAK)
1. **SIFIR KULLANICI MÜDAHALESİ:** Kullanıcı bilgisayar başında değildir. Hiçbir adımda onay bekleme, soru sorma ("Devam edeyim mi?" vb. yazma). Tüm kararları mühendislik standartlarına göre kendin al ve 5 fazın tamamı bitene kadar kesintisiz çalış.
2. **TDD VE KAPI KONTROLÜ (PHASE GATEKEEPER):** Her fazın sonunda o faza ait bir otomatik test betiği (`tests/test_faz_X.py`) yazacaksın ve terminalden çalıştıracaksın.
3. **KENDİ KENDİNİ ONARMA (SELF-HEALING):** Eğer bir fazın testi hata verirse (`AssertionError`, `ImportError`, `SyntaxError` vb.), hatayı analiz et, ilgili kodu düzelt ve testi tekrar çalıştır. **Bir fazın testi %100 BAŞARILI (`PASSED`) olmadan kesinlikle bir sonraki faza geçme!**
4. **GERÇEK KOD ZORUNLULUĞU:** Hiçbir fonksiyonu `pass`, `TODO` veya sahte veriyle bırakma. Tüm matematiksel (Homografi, SciPy), biçimsel (DFA, Regex) ve kriptografik (Bcrypt, AES-256) algoritmaları gerçek ve çalışır şekilde kodla.
5. **DURUM TAKİBİ:** Her faz başarıyla bittiğinde ana dizindeki `BUILD_STATUS.md` dosyasına `[FAZ X - TAMAMLANDI VE TESTLER GEÇTİ]` şeklinde kayıt düş.

---

## 0. HEDEF KLASÖR MİMARİSİ
```text
keyvault-ai/
├── BUILD_STATUS.md
├── backend/
│   ├── venv/                       # Sanal ortam (Otonom kurulacak)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI giriş noktası ve CORS ayarları
│   │   ├── config.py               # AES-256 (32-byte key) ve JWT ayarları
│   │   ├── database.py             # SQLite + SQLAlchemy ORM bağlantısı
│   │   ├── models.py               # User ve KeyVault ilişkisel (1-to-Many) tabloları
│   │   ├── schemas.py              # Pydantic veri doğrulama şemaları
│   │   ├── security.py             # Bcrypt (passlib/bcrypt), AES-256 (cryptography) ve JWT
│   │   ├── vision_pipeline.py      # YOLOv8/OpenCV, 3x3 Homografi, SciPy çukur ölçümü
│   │   ├── compiler_dfa.py         # MACS DFA Otomatı, Regex, GCodeCompiler
│   │   ├── report_generator.py     # Matplotlib 2D Vektör Çizim + ReportLab PDF Kesim Kartı
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── auth.py             # Kayıt ve JWT Login uç noktaları
│   │       └── keys.py             # In-Memory analiz, kasa kayıt, G-Code/PDF indirme
│   ├── tests/
│   │   ├── test_faz1_vision.py
│   │   ├── test_faz2_compiler.py
│   │   ├── test_faz3_security_db.py
│   │   └── test_faz4_api.py
│   ├── requirements.txt
│   └── Dockerfile
├── mobile_app/                     # Flutter Mobil Uygulaması
│   ├── pubspec.yaml
│   └── lib/
│       ├── main.dart
│       ├── services/
│       │   ├── api_service.dart    # REST API iletişimi
│       │   └── auth_storage.dart   # local_auth (Biyometrik/PIN) & flutter_secure_storage
│       └── screens/
│           ├── login_lock_screen.dart
│           ├── camera_scan_screen.dart
│           ├── vault_list_screen.dart
│           └── key_detail_export_screen.dart
└── docker-compose.yml
HAZIRLIK ADIMI: ORTAM KURULUMU
backend/ klasörünü oluştur, içine requirements.txt yaz (fastapi, uvicorn, sqlalchemy, pydantic, python-multipart, passlib[bcrypt], bcrypt==4.0.1, cryptography, pyjwt, numpy, opencv-python-headless, scipy, matplotlib, reportlab, ultralytics, pytest, httpx).

Terminalden sanal ortam oluştur veya paketleri doğrudan yükle ve kurulumun sorunsuz olduğunu doğrula.

FAZ 1: GÖRÜNTÜ İŞLEME, KALİBRASYON VE SAYISAL ÖLÇÜM (vision_pipeline.py)
In-Memory (RAM) Görüntü Okuma ve Güvenli İmha:

Görüntü ASLA diske (save()) kaydedilmeyecek. raw_bytes üzerinden np.frombuffer ve cv2.imdecode ile doğrudan RAM'de matrise çevrilecek.

İşlem sonunda finally: bloğunda img[:] = 0 komutuyla tüm pikseller sıfırlanacak (Data Remanence önlemi) ve gc.collect() ile RAM'den silinecek.

ISO/IEC 7810 Referans Kart Kalibrasyonu ve 3x3 Homografi:

Sabit Kart Boyutu: 85.60 mm x 53.98 mm.

YOLOv8 (veya ağırlık dosyası yoksa OpenCV kontur/köşe tespiti fallback mekanizması) ile referans kartın 4 köşesini ve anahtar ROI alanını tespit et.

cv2.getPerspectiveTransform ve cv2.warpPerspective ile görüntüyü 90° dik düzleme oturt.

Ölçek Katsayısı: k = 85.60 / card_pixel_width (mm/piksel) hesapla.

OpenCV Ön İşleme ve SciPy ile Diş Çukuru Ölçümü:

Gri tonlama, GaussianBlur ve Canny ile kenar profilini çıkar. Anahtarın omuz çıkıntısını X=0 referans noktası al.

scipy.signal.find_peaks ile diş çukurlarını (yerel minimumları) bul ve k ile çarparak milimetrik derinlik dizisini (raw_depths_mm) çıkar.

Esnek Mimari (Graceful Degradation) & Edge Cases:

Standart YALE-5 profiliyse bitting tablosuyla eşleştirip örn. 3-1-4-2-5 şifresi üret.

Veri Kısıtlaması (Kapalı Kaynak Profiller - Kale/İto vb.): Tabloda yoksa veya eşleşmezse ÇÖKME; otomatik olarak RAW_MODE (Ham Ölçüm Modu) durumuna geç ve doğrudan milimetrik derinlikleri döndür.

Donanım Kısıtlaması (Bilyalı Anahtar): Z ekseninde çukurları olan bilyalı anahtar veya yetersiz 2D profil tespit edilirse özel DimpleKeyHardwareError fırlat.

🧪 FAZ 1 TEST Kriteri (tests/test_faz1_vision.py):
OpenCV ile RAM üzerinde sentetik bir görüntü (85.60mm oranlı dikdörtgen referans kart + 5 dişli anahtar silüeti) oluştur.

vision_pipeline fonksiyonuna byte dizisi olarak gönder.

Ölçek katsayısı k'nın doğru hesaplandığını, 5 çukurun SciPy ile bulunduğunu, RAW_MODE ve YALE-5 modlarının çalıştığını ve işlem sonunda matrisin sıfırlandığını (img[:] == 0) test et. Testi pytest ile çalıştır; geçerse FAZ 2'ye geç.

FAZ 2: BİÇİMSEL DİLLER, MACS DFA OTOMATI VE G-CODE DERLEYİCİ (compiler_dfa.py & report_generator.py)
Regex & MACS DFA Otomatı:

Python re ile bitting formatını (^[1-9](-[1-9]){4,5}$) doğrula.

MACS_DFA sınıfı yaz: Komşu iki diş farkı 4'ü aşarsa (|d_i - d_{i+1}| > 4) CNC bıçağı yan dişi bozacağı için durumu q_reject yap ve üretimi reddet (|3 - 1| = 2 <= 4 GEÇERLİ, |1 - 7| = 6 > 4 GEÇERSİZ).

CNC G-Code Derleyicisi (GCodeCompiler):

Hem standart Bitting kodunu hem de RAW_MODE milimetrik derinliklerini .gcode komutlarına (G21, G90, G00 X0.0 Y0.0, G01 X... Y-... F120, M30) derleyen sınıfı yaz.

2D Vektör Çizim ve PDF Kesim Kartı (report_generator.py):

Matplotlib ile gerçek fotoğraf yerine kasada gösterilecek güvenli 2D vektör çizimini (Base64 PNG) üret.

ReportLab ile içinde 2D çizim, bitting/ham derinlik tablosu, MACS DFA durumu ve G-Code satırları bulunan indirilebilir PDF Kesim Kartı üret.

🧪 FAZ 2 TEST Kriteri (tests/test_faz2_compiler.py):
3-1-4-2-5 girdisinin DFA'dan True, 1-8-2-9-1 girdisinin False döndüğünü doğrula.

Üretilen .gcode metninde G21 ve G01 koordinatlarının bulunduğunu, ReportLab çıktısının %PDF başlığıyla geçerli bir PDF byte dizisi ürettiğini test et. Testi pytest ile çalıştır; geçerse FAZ 3'e geç.

FAZ 3: VERİTABANI MİMARİSİ VE ÇİFT KATMANLI KRİPTOGRAFİ (database.py, models.py, security.py)
SQLite & SQLAlchemy ORM (1-to-Many):

Ham SQL kullanmadan User ve KeyVault ORM modellerini kur.

Bcrypt & AES-256 & JWT (security.py):

Kullanıcı şifrelerini Bcrypt ile tek yönlü hash'le ve doğrula.

Anahtar bitting kodlarını ve milimetrik derinlikleri cryptography (AES-256) ile çift yönlü şifrele (encrypt_data / decrypt_data). Veritabanında şifresiz (plain-text) hiçbir anahtar verisi tutma.

Oturum yönetimi için JWT üretme ve doğrulama fonksiyonlarını yaz.

🧪 FAZ 3 TEST Kriteri (tests/test_faz3_security_db.py):
Test veritabanında bir kullanıcı oluştur, parolasının düz metin olmadığını ve Bcrypt ile doğrulandığını test et.

3-1-4-2-5 bitting kodunu AES-256 ile şifreleyip DB'ye kaydet, DB'deki ham sütunun 3-1-4-2-5 içermediğini, ancak decrypt_data çağrıldığında birebir 3-1-4-2-5 olarak geri çözüldüğünü doğrula. Testi pytest ile çalıştır; geçerse FAZ 4'e geç.

FAZ 4: FASTAPI ASENKRON SUNUCU MİMARİSİ (main.py, routers/)
/api/auth/register, /api/auth/login

/api/keys/scan-and-save (In-Memory fotoğraf analizi, RAM sıfırlama, AES-256 kayıt, 2D vektör çizim döndürme)

/api/keys/my-vault (JWT korumalı kasa listesi)

/api/keys/{key_id}/export-gcode ve /api/keys/{key_id}/export-pdf uç noktalarını tamamla.

🧪 FAZ 4 TEST Kriteri (tests/test_faz4_api.py):
FastAPI TestClient kullanarak uçtan uca senaryoyu test et: Kullanıcı kaydı -> Login olup JWT alma -> Sentetik anahtar fotoğrafını /scan-and-save uç noktasına gönderme -> /my-vault ile kasadan çekme -> .gcode ve .pdf dosyalarını indirme (HTTP 200 kontrolü). Tüm testleri çalıştır; geçerse FAZ 5'e geç.

FAZ 5: FLUTTER MOBİL UYGULAMASI, DOCKER VE FİNAL TESTİ
mobile_app/ altında pubspec.yaml (camera, local_auth, flutter_secure_storage, share_plus, http) ve 4 ekranın (login_lock_screen.dart, camera_scan_screen.dart, vault_list_screen.dart, key_detail_export_screen.dart) tam Dart kodlarını eksiksiz oluştur.

Dockerfile ve docker-compose.yml dosyalarını oluştur.

Tüm test süitini (pytest backend/tests/) baştan sona son kez çalıştır. Hepsi PASSED olduğunda BUILD_STATUS.md dosyasına tüm fazların başarıyla tamamlandığını ve sistemin hazır olduğunu belirten final raporunu yaz.