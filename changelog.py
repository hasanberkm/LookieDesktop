"""Sürüm geçmişi: güncellemeden sonraki "Yenilikler" penceresi ve Hakkında'daki
sürüm geçmişi bunu gösterir. Yeni sürümde en üste bir kayıt ekleyin
(APP_VERSION ile aynı sürüm numarası)."""

CHANGES = [
    ("1.0.1", "19.11.2026", {
        "tr": ["Hakkında penceresinde uygulamanın kısa bir açıklaması gösteriliyor.",
               "Güncelleme ayarının açıklaması sadeleştirildi."],
        "en": ["The About window shows a short description of the app.",
               "The description of the update setting is simpler."],
    }),
    ("1.0.0", "19.11.2026", {
        "tr": ["İlk sürüm: Bluetooth bağlantısı, canlı görünüm ve cihaz ayarlarını çalışırken değiştirme.",
               "Profil sekmesi: en fazla 3 kullanıcı için ayrı cihaz ayarları, isteğe bağlı şifre.",
               "Pil göstergesi, düşük pil uyarısı ve sistem tepsisi.",
               "Uygulama ve firmware güncellemeleri; güncellemeden sonra yenilikler "
               "gösterilir, Hakkında'dan sürüm geçmişi açılır."],
        "en": ["First release: Bluetooth connection, live view and changing the device settings while it runs.",
               "Profile tab: separate device settings for up to 3 users, optionally password protected.",
               "Battery indicator, low battery warning and system tray.",
               "App and firmware updates; what is new is shown after an update, and the "
               "version history opens from About."],
    }),
]
