KeyVault-AI: Görüntü İşleme Tabanlı CNC Anahtar Kodu Üreten Dijital Kasa SistemiKeyVault-AI, akıllı telefon kamerasından alınan anahtar ve ISO/IEC 7810 referans kart görüntüsünü işleyerek milimetrik diş derinliklerini çıkaran, fiziksel yedeğe ihtiyaç duymadan doğrudan CNC kesim kodu (.gcode) ve teknik kesim kartı (PDF) üreten, çift katmanlı kriptografik (Bcrypt + AES-256-GCM) güvenlik altyapısına sahip uçtan uca bir yazılım ekosistemidir.📌 Projenin Amacı ve Çözdüğü ProblemKlasik kopyalama süreçleri tamamen fiziksel anahtara bağımlıdır; anahtar kaybolduğunda veya farklı bir konumda unuttulduğunda kilit göbeğinin kırılması kaçınılmazdır. KeyVault-AI; anahtarlarınızı şifreli bir dijital kasada güvenle saklamanızı ve seyahatte ya da acil durumlarda fiziksel numuneye ihtiyaç duymadan herhangi bir çilingirde 30 saniyede yeniden ürettirmenizi sağlar.🏗️ Mimari Genel BakışKeyVault-AI/
├── backend/                    # FastAPI + OpenCV + SciPy + SQLAlchemy + ReportLab
│   ├── app/
│   │   ├── main.py             # FastAPI giriş noktası ve CORS yapılandırması
│   │   ├── config.py           # AES-256 ve JWT yapılandırması
│   │   ├── database.py         # SQLite + SQLAlchemy ORM bağlantısı
│   │   ├── models.py           # User & KeyVault (1-to-Many) ORM modelleri
│   │   ├── schemas.py          # Pydantic doğrulama şemaları
│   │   ├── security.py         # Bcrypt, AES-256-GCM ve PyJWT servisi
│   │   ├── vision_pipeline.py  # In-Memory okuma, 3x3 Homografi, SciPy çukur ölçümü
│   │   ├── compiler_dfa.py     # Regex, MACS DFA Otomatı ve GCodeCompiler
│   │   ├── report_generator.py # Matplotlib 2D Vektör Çizimi + ReportLab PDF Kartı
│   │   └── routers/            # /api/auth/* ve /api/keys/* uç noktaları
│   ├── tests/                  # Faz 1 - Faz 5 otomatik pytest test süiti
│   ├── requirements.txt
│   └── Dockerfile
├── mobile_app/                 # Flutter (Android, iOS, Web, Windows)
│   ├── pubspec.yaml
│   └── lib/
│       ├── main.dart
│       ├── services/           # Dinamik URL/Port destekli ApiService & Biyometrik AuthStorage
│       └── screens/            # Giriş, Ana Menü, Kamera Tarama, Dijital Kasa, Detay & İndirme
└── docker-compose.yml
🚀 Temel Özellikler ve Mühendislik YaklaşımlarıIn-Memory Görüntü İşleme ve RAM Sıfırlama (Sıfır İz Politikası):Yüklenen anahtar fotoğrafları diske (save()) ASLA kaydedilmez. Doğrudan RAM'de (Byte Buffer) işlenir.İşlem bittiğinde finally: bloğu ile piksel matrisi sıfırlanır (img[:] = 0) ve gc.collect() ile kalıcı bellek izi (Data Remanence) engellenir.ISO/IEC 7810 Kalibrasyon ve 3x3 Homografi:Standart ID-1 referans kartı (85.60 mm × 53.98 mm) baz alınarak kamera açısı ve perspektif 90° dikleştirilir.$k = 85.60 / \text{card\_pixel\_width}$ formülüyle 1 pikselin kaç milimetre olduğu 0.1 mm hassasiyetle hesaplanır.Esnek Profil Analizi (YALE-5 & RAW_MODE):Standart Yale profillerinde bitting tablosu eşleştirmesi yapılırken; kapalı kaynak (ticari sır) profillerde sistem çökmez, otomatik olarak RAW_MODE (Ham Ölçüm Modu)'na geçerek milimetrik ham derinlikleri iletir.Z ekseni kısıtı olan bilyalı anahtarlarda ise DimpleKeyHardwareError mekanizması devreye girer.MACS Deterministik Sonlu Otomatı (DFA) ve CNC G-Code Derleyicisi:Komşu diş farkı kuralı ($\vert{}d_i - d_{i+1}\vert{} \le 4$) bir Sonlu Durum Otomatı ile denetlenerek CNC bıçağının kırılması engellenir.Onaylanan şifreler standart ISO CNC komutlarına (G21, G90, G00, G01, M30) derlenir.2D Vektör Çizim ve PDF Teknik Kesim Kartı:Gerçek fotoğraf saklanmadığı için Matplotlib ile güvenli 2D vektör şeması üretilir; ReportLab ile çilingire iletilmeye hazır PDF kesim kartı oluşturulur.Çift Katmanlı Kriptografi ve Güvenlik:Kullanıcı parolaları Bcrypt ile hash'lenir.Anahtar koordinatları ve bitting şifreleri veritabanında AES-256-GCM ile şifreli tutulur; mobilde biyometrik (FaceID/Parmak İzi) / PIN ve JWT ile korunur.🛠️ Kurulum ve Çalıştırma Rehberi1. Backend (FastAPI) Sunucusunu BaşlatmaProje ana dizinindeyken terminalde sırasıyla şu komutları çalıştırın:cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Swagger UI Arayüzü: http://127.0.0.1:8000/docsSağlık Kontrolü: http://127.0.0.1:8000/health2. Otomatik Testleri Çalıştırma (Faz 1 – Faz 5)Sistemdeki tüm birim testlerini koşturmak için:cd C:\Users\BURHAN\Desktop\KeyVault
.\backend\venv\Scripts\python.exe -m pytest backend/tests/ -v
3. Docker ile Çalıştırma (Alternatif)Docker Desktop açıkken tek komutla tüm ekosistemi ayağa kaldırın:docker-compose up --build
4. Flutter Mobil Uygulamasını ÇalıştırmaMobil istemciyi dilediğiniz hedef platformda başlatın:cd mobile_app
flutter pub get

# A. Google Chrome'da (Web) Çalıştırmak İçin:
flutter run -d chrome

# B. Android Emülatörde Çalıştırmak İçin:
flutter run

# C. Fiziksel Cihazda (Honor Tablet / A32) Çalıştırmak İçin:
flutter devices   # Cihaz ID'sini öğrenin
flutter run -d <CIHAZ_ID>
