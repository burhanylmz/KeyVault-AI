# KeyVault-AI

**KeyVault-AI**, ISO/IEC 7810 referans kart kalibrasyonu, 3x3 homografi, SciPy optik profilometri, MACS Deterministik Sonlu Otomatı (DFA), CNC G-Code derleyicisi ve çift katmanlı kriptografik dijital kasa (Bcrypt + AES-256-GCM + JWT) sunan uçtan uca bir anahtar analiz ve arşivleme platformudur.

---

## Mimari Genel Bakış

```text
KeyVault/
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
```

---

## Temel Özellikler

- **In-Memory Görüntü İşleme ve RAM Sıfırlama:** Yüklenen fotoğraflar diske yazılmadan doğrudan RAM üzerinde işlenir ve işlem sonunda (`finally`) piksel matrisi sıfırlanır (`img[:] = 0` + `gc.collect()`).
- **ISO/IEC 7810 Kalibrasyon ve Homografi:** `85.60 mm x 53.98 mm` referans kart tespiti, 3x3 perspektif düzeltme ve `k = 85.60 / card_pixel_width` ölçek hesabı.
- **Esnek Profil Analizi (`YALE-5` & `RAW_MODE`):** Standart bitting eşleştirme, kapalı kaynak profiller için otomatik `RAW_MODE` ve bilyalı anahtarlar için `DimpleKeyHardwareError`.
- **MACS DFA Otomatı ve CNC G-Code Derleyici:** Komşu diş farkı kontrolü ($|d_i - d_{i+1}| \le 4$) ve ISO CNC `.gcode` (`G21`, `G90`, `G00`, `G01`, `M30`) üretimi.
- **2D Vektör Çizim & PDF Kesim Kartı:** Matplotlib Base64 PNG önizleme ve ReportLab indirilebilir PDF kesim kartı.
- **Çift Katmanlı Güvenlik:** Bcrypt parola hash'leme, AES-256-GCM şifreli veritabanı sütunları, JWT oturum yönetimi ve mobilde biyometrik/PIN doğrulama.

---

## Kurulum ve Çalıştırma

### 1. Backend (FastAPI)

```powershell
cd backend
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- Sağlık Kontrolü: `http://127.0.0.1:8000/health`

### 2. Docker ile Çalıştırma

```powershell
docker-compose up --build
```

### 3. Otomatik Testler (`pytest`)

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend/tests/ -v
```

### 4. Flutter Uygulaması (Chrome, Emülatör, Tablet)

```powershell
cd mobile_app
flutter pub get
flutter run -d chrome   # veya Android Emülatör / Fiziksel Cihaz için: flutter run
```
