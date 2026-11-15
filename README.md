# KeyVault-AI: Görüntü İşleme Tabanlı CNC Anahtar Kodu Üreten Dijital Kasa Sistemi

**KeyVault-AI**, akıllı telefon kamerasından alınan anahtar ve ISO/IEC 7810 referans kart görüntüsünü işleyerek milimetrik diş derinliklerini çıkaran, fiziksel yedeğe ihtiyaç duymadan doğrudan CNC kesim kodu (`.gcode`) ve teknik kesim kartı (`PDF`) üreten, çift katmanlı kriptografik güvenlik yapısına sahip uçtan uca bir yazılım ekosistemidir.

---

## 🎯 Projenin Amacı ve Çözdüğü Problem
* **Klasik Kopyalama Sorunu:** Klasik kopyalama süreçleri tamamen fiziksel anahtara bağımlıdır; anahtar kaybolduğunda veya başka bir konumda unutulduğunda kilit göbeğinin kırılması kaçınılmazdır.
* **KeyVault-AI Çözümü:** Anahtarlarınızı şifreli bir dijital kasada güvenle saklamanızı ve seyahatte ya da acil durumlarda fiziksel numuneye ihtiyaç duymadan herhangi bir çilingirde 30 saniyede yeniden ürettirmenizi sağlar.

---

## 📂 Mimari Genel Bakış

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
