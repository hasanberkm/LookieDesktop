"""Sürüm geçmişi: güncellemeden sonraki "Yenilikler" penceresi ve Hakkında'daki
sürüm geçmişi bunu gösterir. Yeni sürümde en üste bir kayıt ekleyin
(APP_VERSION ile aynı sürüm numarası)."""

CHANGES = [
    ("1.1.4", "19.11.2026", {
        "tr": ["Güncellemeden sonraki ilk açılışta yenilikler ve sürüm bilgisi gösteriliyor.",
               "Hakkında penceresinde uygulama sürümüne tıklayınca sürüm geçmişi açılıyor."],
        "en": ["After an update, the first start shows what is new and the version information.",
               "Clicking the app version in the About window opens the version history."],
    }),
    ("1.1.3", "19.11.2026", {
        "tr": ["İşlev değişikliği yok; güncelleme akışını denemek için yayınlandı."],
        "en": ["No functional changes; released to test the update flow."],
    }),
    ("1.1.2", "19.11.2026", {
        "tr": ["Sistem tepsisindeyken güncelleme indirildiğinde uygulamanın donması düzeltildi. "
               "Yeniden başlatma sorusu artık bildirimde Sonra ve Yeniden başlat düğmeleriyle geliyor.",
               "Pencere gizliyken açılan uyarılar artık önce pencereyi geri getiriyor."],
        "en": ["Fixed the app freezing when an update finished downloading while it was in the system tray. "
               "The restart question now comes as a notification with Later and Restart buttons.",
               "Alerts that open while the window is hidden now bring the window back first."],
    }),
    ("1.1.1", "19.11.2026", {
        "tr": ["Güncellemeden sonra yeniden açılırken çıkan \"Failed to load Python DLL\" hatası düzeltildi."],
        "en": ["Fixed the \"Failed to load Python DLL\" error when the app reopened after an update."],
    }),
    ("1.1.0", "19.11.2026", {
        "tr": ["Profil sekmesi: en fazla 3 kullanıcı için ayrı cihaz ayarları.",
               "+ Yeni profil, varsayılan değerlerle yeni bir profil açar.",
               "Profilimi şifrele: şifreli profilde kaydetmek, yeniden adlandırmak ve silmek için şifre sorulur."],
        "en": ["Profile tab: separate device settings for up to 3 users.",
               "+ New profile opens a new profile with the default values.",
               "Protect my profile with a password: saving, renaming and deleting a protected profile asks for "
               "the password."],
    }),
    ("1.0.0", "19.11.2026", {
        "tr": ["İlk sürüm: Bluetooth bağlantısı, canlı görünüm ve cihaz ayarları.",
               "Pil göstergesi, düşük pil uyarısı ve sistem tepsisi.",
               "Uygulama ve firmware güncellemeleri GitHub üzerinden."],
        "en": ["First release: Bluetooth connection, live view and device settings.",
               "Battery indicator, low battery warning and system tray.",
               "App and firmware updates through GitHub."],
    }),
]
