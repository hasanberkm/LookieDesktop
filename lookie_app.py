"""Lookie masaüstü uygulaması.

Cihaza Bluetooth üzerinden bağlanır (gamepad bağlantısının yanındaki ikinci
servis), canlı kafa açılarını gösterir ve ayarları cihaz çalışırken değiştirip
flash'a kaydeder. Cihazın Windows'ta eşleştirilmiş olması yeterlidir; ayrı bir
eşleştirme gerekmez.

Cihaz tarafındaki karşılığı: AppLink.cpp, Settings.cpp, HeadTracker.cpp
(handleCommand). UUID'ler ve telemetri biçimi oradakilerle aynı olmalı.
"""

import asyncio
import json
import locale
import math
import os
import queue
import struct
import sys
import threading
import tkinter as tk

import profiles
import updater
import uuid
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFilter, ImageGrab, ImageTk

from help_texts import DETAILS

APP_VERSION = "1.1.1"

SVC_UUID = uuid.UUID("6e4c0001-7a3b-4c1e-9f2d-4c6f6f6b6965")
TEL_UUID = uuid.UUID("6e4c0002-7a3b-4c1e-9f2d-4c6f6f6b6965")
CFG_UUID = uuid.UUID("6e4c0003-7a3b-4c1e-9f2d-4c6f6f6b6965")
CTL_UUID = uuid.UUID("6e4c0004-7a3b-4c1e-9f2d-4c6f6f6b6965")
STALE_GATT_ERROR = -2147024874  # 0x80070016: "Aygıt komutu algılayamıyor" (eski GATT önbelleği)
OTA_CTL_UUID = uuid.UUID("6e4c0005-7a3b-4c1e-9f2d-4c6f6f6b6965")  # firmware güncellemesi
OTA_DAT_UUID = uuid.UUID("6e4c0006-7a3b-4c1e-9f2d-4c6f6f6b6965")
TEL_FORMAT = "<hhhhhhBB"  # AppLink.h: Telemetry
TEL_FORMAT_V1 = "<hhhhhhB"  # pil alanı olmayan eski firmware
FLAG_CENTERED, FLAG_ADJUSTING, FLAG_AUTOCENTER, FLAG_DIRTY = 1, 2, 4, 8
FLAG_CHARGING, FLAG_USB = 16, 32
BATTERY_UNKNOWN = 0xFF
# Pil göstergesi testi (Ayarlar > Pil > "Pil animasyon testi", ya da
# LOOKIE_BATTERY_DEMO=1 ile açılışta): yüzde 100'den 0'a birer birer azalır
# (renk geçişleri ve %10 altı uyarısı görünür), 0'da bir süre şarj animasyonu
# oynar, sonra baştan başlar. Cihazın gerçek pil durumu bu sırada gösterilmez.
# Pil gerilimi ölçülmeye başlayana kadar görselleri denemek için.
# Hız: LOOKIE_BATTERY_DEMO_MS (adım başına ms, varsayılan 150).
BATTERY_DEMO = os.environ.get("LOOKIE_BATTERY_DEMO") == "1"
try:
    BATTERY_DEMO_MS = max(20, int(os.environ.get("LOOKIE_BATTERY_DEMO_MS", "150")))
except ValueError:
    BATTERY_DEMO_MS = 150
# Eski adla eşleştirilmiş cihazlar da bulunsun.
DEVICE_NAMES = ("lookie", "headtracker")

TEAL = "#14B8A6"
TEAL_DARK = "#0F766E"
TEAL_HOVER = "#2DD4BF"
PITCH_COLOR = "#F59E0B"
# Pencere düğmeleri üzerine gelince renklenir: kapat kırmızı, tam ekran sarı,
# simge durumuna küçült turkuaz; zemin aynı rengin açık tonu.
CLOSE_COLOR = "#EF4444"
MAX_COLOR = "#EAB308"
HOVER_TINT = {False: 0.10, True: 0.17}  # zemin renk yoğunluğu: açık tema, koyu tema


def tint(color, bg, k):
    """color'ı bg zeminine k oranında karıştırır (0 = zemin, 1 = renk)."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(y + (x - y) * k) for x, y in zip(a, b))


# --------------------------------------------------------------------------
# Dil
# --------------------------------------------------------------------------
TEXT = {
    "tr": {
        "title": "Lookie",
        "tab_app": "Ayarlar",
        "appearance": "Görünüm",
        "theme": "Tema",
        "theme_opts": ("Sistem", "Açık", "Koyu"),
        "lang": "Dil",
        "lang_opts": ("Sistem", "Türkçe", "English"),
        "window": "Pencere",
        "topmost": "Her zaman üstte",
        "topmost_h": "Oyun oynarken uygulama penceresi diğer pencerelerin üstünde kalır.",
        "confirm_close": "Kapatırken kaydedilmemiş değişiklikleri sor",
        "confirm_close_h": "Cihazda kaydedilmemiş ayar varken uygulamayı kapatırsanız bir uyarı gösterilir.",
        "blur": "Uyarılarda arka planı bulanıklaştır",
        "blur_h": "Bir uyarı açıldığında uygulama penceresi bulanıklaşır, böylece uyarı öne çıkar.",
        "sensor": "Sensör",
        "import": "Sensördeki ayarları içe aktar",
        "import_h": "Cihazdaki bütün ayarları ve yukarı-aşağı görüşü okuyup uygulamaya aktarır. Cihazın ayar butonuyla ya da seri porttan yapılan değişiklikleri uygulamada görmek için kullanın.",
        "imported": "Ayarlar sensörden içe aktarıldı ({time}).",
        "not_connected": "Cihaz bağlı değil.",
        "device_name": "Cihaz adı",
        "firmware": "Firmware",
        "app_version": "Uygulama sürümü",
        "searching": "Cihaz aranıyor…",
        "not_paired": "Lookie eşleştirilmemiş. Önce Windows Bluetooth ayarlarından eşleştirin.",
        "offline": "Bağlı değil",
        "stale_cache": "Windows cihazın eski Bluetooth bilgilerini kullanıyor. Bluetooth ayarlarından Lookie'yi kaldırıp yeniden eşleştirin.",
        "old_fw": "Cihaz bulundu ama firmware bu uygulamayı desteklemiyor. Firmware'i güncelleyin.",
        "connected": "Bağlı",
        "busy": "Cihaz meşgul (kalibrasyon)…",
        "bat_charging": "Şarj oluyor",
        "bat_unknown": "Pil ölçülmüyor",
        "battery": "Pil",
        "low_bat_alert": "Pil azalınca uyarı penceresi göster",
        "low_bat_alert_h": "Pil %10'un altına düşünce, uygulama öndeyse şarja takmanızı söyleyen bir uyarı penceresi açılır. Uygulama arka plandaysa, sistem tepsisindeyse ya da bu seçenek kapalıysa ekranın köşesinde bir bildirim çıkar.",
        "tray": "Küçültünce sistem tepsisine gizle",
        "tray_h": "Küçült düğmesi uygulamayı görev çubuğundan kaldırıp saatin yanındaki simgelere gizler. Simgeye tıklayınca uygulama açılır; sağ tıklayınca pil durumu, Büyüt ve Çıkış görünür.",
        "tray_show": "Büyüt",
        "tray_quit": "Çıkış",
        "tray_bat": "Pil: {s}",
        "tray_offline": "Cihaz bağlı değil",
        "upd_section": "Güncellemeler",
        "auto_update": "Güncellemeleri otomatik denetle",
        "auto_update_h": "Açılışta ve 6 saatte bir GitHub'daki son yayın denetlenir. Yeni sürüm varsa yüklemek isteyip istemediğiniz sorulur.",
        "check_now": "Güncellemeleri denetle",
        "upd_checking": "Denetleniyor…",
        "upd_uptodate": "Her şey güncel (son denetim {time}).",
        "upd_found": "Yeni sürüm var (son denetim {time}).",
        "upd_error": "Denetlenemedi: {err}",
        "upd_uptodate_t": "Her şey güncel",
        "upd_uptodate_m": "Uygulama {app}{fw} ve bunlar yayınlanan en son sürümler.",
        "upd_fw_part": ", firmware {fw}",
        "fw_avail_t": "Sensörünüzün yeni bir sürümü yayınlandı",
        "fw_avail": "Firmware {new} yayınlandı (cihazdaki: {cur}). Şimdi yüklensin mi? Yükleme yaklaşık bir dakika sürer, bu sırada kafa takibi durur.",
        "fw_need_usb": "Firmware {new} yayınlandı, ama cihazdaki sürüm ({cur}) Bluetooth güncellemesini desteklemiyor. Bu sürümü bir kez USB ile yükleyin; sonraki güncellemeler buradan yapılabilir.",
        "app_avail_t": "Lookie'nin yeni bir sürümü yayınlandı",
        "app_avail": "Uygulama {new} yayınlandı (kullandığınız: {cur}). Şimdi yüklensin mi?",
        "btn_install": "Yükle",
        "btn_skip": "Şimdilik atla",
        "btn_hide": "Gizle",
        "btn_restart": "Yeniden başlat",
        "btn_later": "Sonra",
        "dl_title_firmware": "Firmware güncellemesi",
        "dl_title_app": "Uygulama güncellemesi",
        "dl_downloading": "İndiriliyor… %{p}",
        "dl_sizes": "{done} / {total}",
        "dl_flashing": "Cihaza yükleniyor… %{p}",
        "dl_flash_hint": "Cihazı kapatmayın ve menzilde tutun.",
        "dl_failed_t": "Güncelleme yapılamadı",
        "dl_need_device": "Firmware'i yüklemek için cihaz bağlı olmalı.",
        "fw_done_t": "Firmware güncellendi",
        "fw_done": "Cihaz yeni sürümle ({v}) yeniden başlıyor.",
        "app_ready_t": "Güncelleme hazır",
        "app_ready": "Lookie {v} indirildi. Uygulama kapanıp yeni sürümle yeniden açılacak. \"Sonra\" derseniz uygulamayı kapattığınızda kurulur.",
        "app_manual": "Lookie {v} indirildi: {path}. Uygulama kaynak koddan çalıştığı için kendini değiştiremez.",
        "bat_demo": "Pil animasyon testi",
        "bat_demo_h": "Pil göstergesini cihaz olmadan dener: yüzde 100'den 0'a azalır, %10'un altında düşük pil uyarısı çıkar, sonra şarj animasyonu oynar ve baştan başlar. Açıkken cihazın gerçek pil durumu gösterilmez.",
        "low_bat_t": "Pil azaldı",
        "low_bat": "Lookie'nin pili %{p}. Kapanmadan önce şarja takın.",
        "about": "Hakkında",
        "about_t": "Lookie hakkında",
        "live": "Canlı görünüm",
        "head_yaw": "Baş, sağ-sol",
        "view_yaw": "Oyundaki bakış",
        "pitch": "Baş, yukarı-aşağı",
        "roll": "Baş, yatırma",
        "autoyaw": "Koltuk telafisi",
        "pitch_axis": "Yukarı-aşağı ekseni",
        "head": "Baş",
        "view": "Bakış",
        "updown": "Yukarı-aşağı",
        "sign_hint": "Pozitif: sağa, yukarı, sağa yatırma",
        "recenter": "Ortala",
        "gyrocal": "Gyro kalibrasyonu",
        "tab_yaw": "Sağ-sol",
        "tab_pitch": "Yukarı-aşağı",
        "tab_chair": "Koltuk telafisi",
        "tab_smooth": "Yumuşatma",
        "ylin": "Bire bir bölge",
        "yblend": "Geçiş genişliği",
        "ygain": "Uzak hassasiyet",
        "ylin_h": "Merkezin iki yanında görüşün kafayı bire bir takip ettiği açı.",
        "yblend_h": "Hassasiyetin yumuşakça arttığı baş dönüşü aralığı.",
        "ygain_h": "Geçişten sonra her derece baş dönüşünün oyunda kaç derece bakış ürettiği. 1 eğriyi kapatır.",
        "curve": "Baş dönüşü → oyundaki bakış",
        "prng": "Hassasiyet aralığı",
        "prng_h": "Tam eksen için gereken baş eğme açısı. Büyük değer = daha az hassas.",
        "poff": "Düz bakış görüşü",
        "poff_h": "Düz bakarken gönderilen eksen değeri. Negatif değer görüşü yukarı kaldırır.",
        "pdz": "Ölü bölge",
        "pdz_h": "Bu açının içindeki baş eğmeleri yok sayılır.",
        "ac": "Koltuk telafisini kullan",
        "ac_h": "Kafa merkeze yakın ve sakinken merkezi yavaşça baktığınız yöne çeker; dönen koltuğun yarattığı kaymayı giderir.",
        "acw": "Çalışma penceresi",
        "acw_h": "Yalnızca kafa merkezin bu kadar yakınındayken çalışır. En kısa yan bakışınızdan küçük olmalı.",
        "act": "Telafi süresi",
        "act_h": "Küçük değer = daha güçlü telafi, ama pencere içinde tutulan bakış da merkeze daha hızlı kayar.",
        "acd": "Sakinlik sınırı",
        "acd_h": "Kafanın sakin sayıldığı en yüksek dönüş hızı.",
        "acm": "Sakinlik süresi",
        "acm_h": "Telafi başlamadan önce kafanın sakin kalması gereken süre.",
        "smc": "Dururken yumuşatma",
        "smc_h": "Küçük değer = kafa dururken daha sakin görüntü, biraz daha gecikme.",
        "smb": "Hareket tepkisi",
        "smb_h": "Büyük değer = hızlı dönüşlerde daha az gecikme.",
        "adz": "Sağ-sol ölü bölgesi",
        "adz_h": "Merkezdeki küçük titremeyi sıfırda tutar.",
        "rsm": "Ortalama gecikmesi",
        "rsm_h": "Merkez, ortalama butonu bırakıldıktan bu kadar sonra alınır.",
        "tab_profile": "Profil",
        "prof_section": "Profiller",
        "prof_hint": "Her profil cihaz ayarlarının ayrı bir kopyasıdır; en fazla 3 profil oluşturulabilir. Bir profil seçilince ayarları cihaza yüklenir. Ayarları değiştirip Kaydet'e basınca değişiklikler hem cihaza hem etkin profile kaydedilir.",
        "profile_n": "Profil {n}",
        "prof_new": "Yeni profil",
        "prof_full": "En fazla 3 profil oluşturulabilir.",
        "prof_lock": "Profilimi şifrele",
        "prof_locked": "Şifreli",
        "prof_active": "Etkin",
        "prof_rename": "Yeniden adlandır",
        "prof_delete": "Sil",
        "prof_offline": "Cihaz bağlanınca seçili profil cihaza yüklenir.",
        "prof_lock_h": "Şifreli bir profilin ayarlarını kaydetmek, adını değiştirmek, profili silmek ya da şifreyi kaldırmak için şifre sorulur. Şifre unutulursa geri alınamaz.",
        "pw_set_t": "Profili şifrele",
        "pw_set_m": "“{name}” profilinde değişiklik kaydedilirken bu şifre sorulacak.",
        "pw_field": "Şifre",
        "pw_again": "Şifre (tekrar)",
        "pw_short": "Şifre en az 4 karakter olmalı.",
        "pw_mismatch": "Şifreler aynı değil.",
        "pw_ask_t": "Şifre gerekli",
        "pw_ask_m": "“{name}” şifreli. Devam etmek için şifreyi girin.",
        "pw_wrong": "Şifre yanlış.",
        "name_t": "Profili yeniden adlandır",
        "name_field": "Profil adı",
        "name_empty": "Ad boş olamaz.",
        "name_taken": "Bu adda bir profil zaten var.",
        "prof_del_t": "Profil silinsin mi?",
        "prof_del_m": "“{name}” ve kayıtlı ayarları silinecek. Bu işlem geri alınamaz.",
        "prof_switch_t": "Kaydedilmemiş değişiklikler var",
        "prof_switch_m": "“{name}” profiline geçilince kaydedilmemiş değişiklikler kaybolacak.",
        "btn_switch": "Profile geç",
        "btn_delete": "Sil",
        "btn_lock": "Şifrele",
        "btn_continue": "Devam",
        "btn_save_name": "Kaydet",
        "save": "Kaydet",
        "revert": "Geri al",
        "defaults": "Varsayılanlar",
        "unsaved": "Kaydedilmemiş değişiklikler var.",
        "saved": "Ayarlar cihazda kayıtlı.",
        "gyro_q_t": "Gyro kalibrasyonu başlatılsın mı?",
        "gyro_q": "Cihazı masa gibi sabit bir yere koyun ve kalibrasyon bitene kadar dokunmayın. Kalibrasyon 2–10 saniye sürer.",
        "gyro_run_t": "Kalibrasyon yapılıyor",
        "gyro_run": "Cihazı hareket ettirmeyin. Kalibrasyon bitince bu pencere kendiliğinden kapanır.",
        "gyro_ok_t": "Kalibrasyon tamamlandı",
        "gyro_ok": "Gyro kalibrasyonu başarıyla tamamlandı ve cihaza kaydedildi. Cihaz yeniden ortalandı.",
        "gyro_moved_t": "Cihaz hareket etti",
        "gyro_moved": "Kalibrasyon sırasında cihaz hareket etti. En sabit ölçüm kaydedildi, ama görüş zamanla kayabilir. Cihazı masa gibi sabit bir yere koyup kalibrasyonu tekrarlayın.",
        "gyro_done": "Kalibrasyon tamamlandı ve cihaza kaydedildi.",
        "gyro_timeout_t": "Yanıt alınamadı",
        "gyro_timeout": "Cihaz kalibrasyonun bittiğini bildirmedi. Bağlantıyı kontrol edip tekrar deneyin.",
        "defaults_q_t": "Varsayılanlara dönülsün mü?",
        "close_q_t": "Kaydedilmemiş değişiklikler var",
        "btn_start": "Başlat",
        "btn_cancel": "Vazgeç",
        "btn_ok": "Tamam",
        "btn_retry": "Tekrar dene",
        "btn_reset": "Varsayılanlara dön",
        "btn_quit": "Yine de çık",
        "btn_exit": "Çıkış yap",
        "quit_q_t": "Çıkış yapılsın mı?",
        "quit_q": "Lookie uygulaması kapanır. Cihaz oyunlarda kafa takibine devam eder; uygulama yalnızca ayarlar için gerekir.",
        "defaults_q": "Bütün ayarlar config.h'teki varsayılan değerlere döner (yukarı-aşağı görüş dahil). Kaydet'e basana kadar cihazın flash'ındaki ayarlar değişmez.",
        "close_q": "Cihazda kaydedilmemiş ayarlar var. Cihaz yeniden başlatılınca kaybolacaklar.",
        "deg": "°",
        "deg_s": "°/sn",
        "sec": "sn",
        "ms": "ms",
        "hz": "Hz",
    },
    "en": {
        "title": "Lookie",
        "tab_app": "Settings",
        "appearance": "Appearance",
        "theme": "Theme",
        "theme_opts": ("System", "Light", "Dark"),
        "lang": "Language",
        "lang_opts": ("System", "Türkçe", "English"),
        "window": "Window",
        "topmost": "Always on top",
        "topmost_h": "The app window stays above other windows while you play.",
        "confirm_close": "Ask about unsaved changes when closing",
        "confirm_close_h": "A warning is shown if you close the app while the device has unsaved settings.",
        "blur": "Blur the background behind alerts",
        "blur_h": "When an alert opens, the app window is blurred so that the alert stands out.",
        "sensor": "Sensor",
        "import": "Import settings from the sensor",
        "import_h": "Reads every setting and the up-down view from the device and loads them into the app. Use it to see changes made with the device's adjust button or over the serial port.",
        "imported": "Settings imported from the sensor ({time}).",
        "not_connected": "The device is not connected.",
        "device_name": "Device name",
        "firmware": "Firmware",
        "app_version": "App version",
        "searching": "Looking for the device…",
        "not_paired": "Lookie is not paired. Pair it in the Windows Bluetooth settings first.",
        "offline": "Not connected",
        "stale_cache": "Windows is using outdated Bluetooth data for the device. Remove Lookie in Bluetooth settings and pair it again.",
        "old_fw": "The device was found, but its firmware does not support this app. Update the firmware.",
        "connected": "Connected",
        "busy": "Device busy (calibrating)…",
        "bat_charging": "Charging",
        "bat_unknown": "Battery not measured",
        "battery": "Battery",
        "low_bat_alert": "Show a warning dialog on low battery",
        "low_bat_alert_h": "When the battery drops below 10% and the app is in front, a dialog asks you to plug in the charger. When the app is in the background, in the system tray or this option is off, a notification appears in the corner of the screen.",
        "tray": "Minimize to the system tray",
        "tray_h": "The minimize button removes the app from the taskbar and hides it among the icons next to the clock. Click the icon to open the app; right-click it for the battery status, Show and Quit.",
        "tray_show": "Show",
        "tray_quit": "Quit",
        "tray_bat": "Battery: {s}",
        "tray_offline": "Device not connected",
        "upd_section": "Updates",
        "auto_update": "Check for updates automatically",
        "auto_update_h": "The latest release on GitHub is checked at startup and every 6 hours. If there is a new version, you are asked whether to install it.",
        "check_now": "Check for updates",
        "upd_checking": "Checking…",
        "upd_uptodate": "Everything is up to date (last check {time}).",
        "upd_found": "A new version is available (last check {time}).",
        "upd_error": "Could not check: {err}",
        "upd_uptodate_t": "Everything is up to date",
        "upd_uptodate_m": "App {app}{fw} are the latest released versions.",
        "upd_fw_part": " and firmware {fw}",
        "fw_avail_t": "A new version for your sensor is available",
        "fw_avail": "Firmware {new} has been released (on the device: {cur}). Install it now? It takes about a minute; head tracking pauses meanwhile.",
        "fw_need_usb": "Firmware {new} has been released, but the firmware on the device ({cur}) cannot update over Bluetooth. Install this version once over USB; later updates can be done from here.",
        "app_avail_t": "A new version of Lookie is available",
        "app_avail": "App {new} has been released (you have: {cur}). Install it now?",
        "btn_install": "Install",
        "btn_skip": "Skip for now",
        "btn_hide": "Hide",
        "btn_restart": "Restart",
        "btn_later": "Later",
        "dl_title_firmware": "Firmware update",
        "dl_title_app": "App update",
        "dl_downloading": "Downloading… {p}%",
        "dl_sizes": "{done} / {total}",
        "dl_flashing": "Installing on the device… {p}%",
        "dl_flash_hint": "Keep the device on and in range.",
        "dl_failed_t": "The update failed",
        "dl_need_device": "The device must be connected to install firmware.",
        "fw_done_t": "Firmware updated",
        "fw_done": "The device is restarting with the new version ({v}).",
        "app_ready_t": "Update ready",
        "app_ready": "Lookie {v} has been downloaded. The app will close and reopen with the new version. If you choose \"Later\", it is installed when you close the app.",
        "app_manual": "Lookie {v} has been downloaded: {path}. The app runs from source and cannot replace itself.",
        "bat_demo": "Battery animation test",
        "bat_demo_h": "Tries the battery indicator without the device: it counts down from 100% to 0, shows the low battery warning below 10%, then plays the charging animation and starts over. While on, the device's real battery state is not shown.",
        "low_bat_t": "Battery low",
        "low_bat": "Lookie's battery is at {p}%. Plug in the charger before it turns off.",
        "about": "About",
        "about_t": "About Lookie",
        "live": "Live view",
        "head_yaw": "Head, left-right",
        "view_yaw": "View in game",
        "pitch": "Head, up-down",
        "roll": "Head, tilt",
        "autoyaw": "Chair compensation",
        "pitch_axis": "Up-down axis",
        "head": "Head",
        "view": "View",
        "updown": "Up-down",
        "sign_hint": "Positive: right, up, tilt right",
        "recenter": "Recenter",
        "gyrocal": "Gyro calibration",
        "tab_yaw": "Left-right",
        "tab_pitch": "Up-down",
        "tab_chair": "Chair compensation",
        "tab_smooth": "Smoothing",
        "ylin": "One-to-one range",
        "yblend": "Transition width",
        "ygain": "Far sensitivity",
        "ylin_h": "Angle on either side of the center in which the view follows the head one to one.",
        "yblend_h": "Range of head turn over which the sensitivity rises smoothly.",
        "ygain_h": "Beyond the transition, degrees of view per degree of head turn. 1 turns the curve off.",
        "curve": "Head turn → view in game",
        "prng": "Sensitivity range",
        "prng_h": "Head nod needed for full axis deflection. Larger = less sensitive.",
        "poff": "Straight-ahead view",
        "poff_h": "Axis value sent while looking straight ahead. Negative values raise the view.",
        "pdz": "Deadzone",
        "pdz_h": "Nods within this angle are ignored.",
        "ac": "Use chair compensation",
        "ac_h": "While the head rests calm near the center, slowly pulls the center toward where you look; cancels the drift of a swivel chair.",
        "acw": "Working window",
        "acw_h": "Only works while the head is this close to the center. Keep it below your shortest glances.",
        "act": "Compensation time",
        "act_h": "Smaller = stronger compensation, but a look held inside the window drifts to the center faster.",
        "acd": "Calm limit",
        "acd_h": "Highest rotation speed at which the head counts as calm.",
        "acm": "Calm time",
        "acm_h": "How long the head must stay calm before compensation starts.",
        "smc": "Smoothing at rest",
        "smc_h": "Smaller = calmer view at rest, a little more lag.",
        "smb": "Motion response",
        "smb_h": "Larger = less lag on fast turns.",
        "adz": "Left-right deadzone",
        "adz_h": "Keeps small jitter at the center at zero.",
        "rsm": "Recenter delay",
        "rsm_h": "The center is captured this long after the recenter button is released.",
        "tab_profile": "Profile",
        "prof_section": "Profiles",
        "prof_hint": "Each profile is a separate copy of the device settings; up to 3 profiles can be created. Selecting a profile loads its settings onto the device. When you change settings and press Save, the changes are saved both on the device and in the active profile.",
        "profile_n": "Profile {n}",
        "prof_new": "New profile",
        "prof_full": "Up to 3 profiles can be created.",
        "prof_lock": "Protect my profile with a password",
        "prof_locked": "Protected",
        "prof_active": "Active",
        "prof_rename": "Rename",
        "prof_delete": "Delete",
        "prof_offline": "The selected profile is loaded onto the device when it connects.",
        "prof_lock_h": "Saving the settings of a protected profile, renaming it, deleting it or removing the password asks for the password. A forgotten password cannot be recovered.",
        "pw_set_t": "Protect profile",
        "pw_set_m": "This password is asked when changes to “{name}” are saved.",
        "pw_field": "Password",
        "pw_again": "Password (again)",
        "pw_short": "The password must have at least 4 characters.",
        "pw_mismatch": "The passwords do not match.",
        "pw_ask_t": "Password required",
        "pw_ask_m": "“{name}” is protected. Enter the password to continue.",
        "pw_wrong": "Wrong password.",
        "name_t": "Rename profile",
        "name_field": "Profile name",
        "name_empty": "The name cannot be empty.",
        "name_taken": "A profile with this name already exists.",
        "prof_del_t": "Delete the profile?",
        "prof_del_m": "“{name}” and its saved settings will be deleted. This cannot be undone.",
        "prof_switch_t": "There are unsaved changes",
        "prof_switch_m": "Unsaved changes are lost when you switch to “{name}”.",
        "btn_switch": "Switch profile",
        "btn_delete": "Delete",
        "btn_lock": "Protect",
        "btn_continue": "Continue",
        "btn_save_name": "Save",
        "save": "Save",
        "revert": "Revert",
        "defaults": "Defaults",
        "unsaved": "There are unsaved changes.",
        "saved": "Settings are saved on the device.",
        "gyro_q_t": "Start gyro calibration?",
        "gyro_q": "Put the device on a still surface such as a desk and do not touch it until the calibration finishes. It takes 2–10 seconds.",
        "gyro_run_t": "Calibrating",
        "gyro_run": "Do not move the device. This window closes by itself when the calibration finishes.",
        "gyro_ok_t": "Calibration complete",
        "gyro_ok": "The gyro calibration finished successfully and was saved on the device. The device has been recentered.",
        "gyro_moved_t": "The device moved",
        "gyro_moved": "The device moved during the calibration. The stillest measurement was saved, but the view may drift over time. Put the device on a still surface such as a desk and calibrate again.",
        "gyro_done": "The calibration finished and was saved on the device.",
        "gyro_timeout_t": "No response",
        "gyro_timeout": "The device did not report the end of the calibration. Check the connection and try again.",
        "defaults_q_t": "Return to the defaults?",
        "close_q_t": "There are unsaved changes",
        "btn_start": "Start",
        "btn_cancel": "Cancel",
        "btn_ok": "OK",
        "btn_retry": "Try again",
        "btn_reset": "Return to defaults",
        "btn_quit": "Quit anyway",
        "btn_exit": "Quit",
        "quit_q_t": "Quit Lookie?",
        "quit_q": "The Lookie app closes. The device keeps tracking your head in games; the app is only needed for settings.",
        "defaults_q": "All settings return to the defaults in config.h (including the up-down view). The settings in the device's flash do not change until you press Save.",
        "close_q": "The device has unsaved settings. They will be lost when the device restarts.",
        "deg": "°",
        "deg_s": "°/s",
        "sec": "s",
        "ms": "ms",
        "hz": "Hz",
    },
}


def pick_language():
    try:
        lang = locale.getlocale()[0] or ""
        if not lang:
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "tr" if (lid & 0x3FF) == 0x1F else "en"
        return "tr" if lang.lower().startswith(("tr", "turkish")) else "en"
    except Exception:
        return "en"


# Uygulama tercihleri: %APPDATA%\Lookie\settings.json
PREFS_PATH = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Lookie", "settings.json")
DEFAULT_PREFS = {"theme": "system", "lang": "system", "topmost": False, "confirm_close": True, "blur": True,
                 "low_bat_alert": True, "tray": False, "battery_demo": False,
                 "auto_update": True}


def load_prefs():
    prefs = dict(DEFAULT_PREFS)
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        prefs.update({k: v for k, v in data.items() if k in DEFAULT_PREFS})
    except Exception:
        pass
    return prefs


def save_prefs(prefs):
    try:
        os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass


def log_error(where):
    """Beklenmeyen hataları %APPDATA%\\Lookie\\error.log dosyasına yazar."""
    try:
        import time, traceback
        os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
        with open(os.path.join(os.path.dirname(PREFS_PATH), "error.log"), "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {where}\n{traceback.format_exc()}\n")
    except Exception:
        pass


def resolve_language(pref):
    return pref if pref in TEXT else pick_language()


def set_language(lang):
    global LANG, T, HELP
    LANG, T, HELP = lang, TEXT[lang], DETAILS[lang]


PREFS = load_prefs()
LANG = resolve_language(PREFS["lang"])
T = TEXT[LANG]
HELP = DETAILS[LANG]


def windows_dark_mode():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        return False


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# --------------------------------------------------------------------------
# Yazı tipi: Nunito (SIL OFL, fonts/OFL.txt). Yuvarlak uçlu harfleri logodaki
# "Lookie" yazısının yuvarlak çizgileriyle aynı karakterde. Kurulum gerekmez:
# dosyalar yalnızca bu uygulama için (FR_PRIVATE) Windows'a tanıtılır.
# Tk yalnızca normal/kalın ağırlık seçebildiği için ara ağırlıklar ayrı aile
# adıyla gelir ("Nunito SemiBold", "Nunito ExtraBold").
# --------------------------------------------------------------------------
def load_fonts():
    try:
        import ctypes
        folder = resource("fonts")
        added = 0
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(".ttf"):
                added += ctypes.windll.gdi32.AddFontResourceExW(os.path.join(folder, name), 0x10, 0)
        return added > 0
    except Exception:
        return False


HAVE_NUNITO = load_fonts()
FONT = "Nunito" if HAVE_NUNITO else "Segoe UI"                    # arayüz
FONT_SEMI = "Nunito SemiBold" if HAVE_NUNITO else "Segoe UI Semibold"
BRAND_FONT = (("Nunito ExtraBold", 19) if HAVE_NUNITO               # marka yazısı
              else (FONT, 18, "bold"))


# --------------------------------------------------------------------------
# Windows yardımcıları (düşük pil uyarısı)
# --------------------------------------------------------------------------
class TrayIcon:
    """Sistem tepsisi simgesi (pystray, kendi iş parçacığında). Windows'un
    yerel menüsü simge gösteremiyor ve uygulamanın temasına uymuyor; bu yüzden
    sağ tık, uygulamanın kendi çizdiği menüyü açtırır. Tıklamalar arayüze
    `events` kuyruğuyla gider ("tray", "show") / ("tray_menu", (x, y)); Tk'ya
    bu iş parçacığından dokunulmaz."""

    def __init__(self, events):
        import pystray
        from pystray._util import win32 as pw

        class _Icon(pystray.Icon):
            def _run_detached(icon):
                # Arka plan iş parçacığı: pencere beklenmedik biçimde kapansa
                # bile süreci açık tutmasın.
                threading.Thread(target=icon._run, daemon=True).start()

            def _on_notify(icon, wparam, lparam):
                if lparam == 0x0202:    # WM_LBUTTONUP
                    events.put(("tray", "show"))
                elif lparam == 0x0205:  # WM_RBUTTONUP
                    # Tepsiye tıklanınca odağı alma hakkı bu süreçtedir; menü
                    # penceresi odağı alabilsin (dışarı tıklayınca kapanır).
                    pw.SetForegroundWindow(icon._hwnd)
                    pt = wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    events.put(("tray_menu", (pt.x, pt.y)))

        import ctypes
        from ctypes import wintypes
        self.icon = _Icon("Lookie", scaled_icon(64), "Lookie")
        self.icon.run_detached()

    def set_title(self, text):
        try:
            self.icon.title = text
        except Exception:
            pass

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Tek kopya: ikinci kez açılınca açık olanı öne getir ve çık
# --------------------------------------------------------------------------
SHOW_EVENT_NAME = r"Local\LookieApp.Show"
_instance_mutex = None
_show_event = None


def claim_single_instance():
    """Uygulama zaten açıksa ona "göster" sinyali gönderip False döndürür.
    Açık değilse kilidi ve sinyali oluşturup True döndürür."""
    global _instance_mutex, _show_event
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CreateEventW.restype = ctypes.c_void_p
        k32.SetEvent.argtypes = [ctypes.c_void_p]
        _instance_mutex = k32.CreateMutexW(None, False, r"Local\LookieApp.Instance")
        already = k32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        # Otomatik sıfırlanan olay: açık kopya her sinyalde bir kez öne gelir.
        _show_event = k32.CreateEventW(None, False, False, SHOW_EVENT_NAME)
        if already:
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: öne gelme izni ver
            k32.SetEvent(_show_event)
            return False
    except Exception:
        pass
    return True


def show_requested():
    """Başka bir kopya açılmaya çalışıldı mı (sinyal geldiyse bir kez True)."""
    if not _show_event:
        return False
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        return k32.WaitForSingleObject(_show_event, 0) == 0  # WAIT_OBJECT_0
    except Exception:
        return False


def stretch_center(im, width, height):
    """Resmi ortadaki tek satır/sütunu çoğaltarak büyütür (0 = o eksende
    değiştirme). Kenarlar ve köşeler aynen kalır; orta kısmı düz renk olan
    tema parçaları için görüntü birebir aynıdır."""
    w, h = im.size
    if width and width > w:
        cx = w // 2
        out = Image.new(im.mode, (width, h))
        out.paste(im.crop((0, 0, cx, h)), (0, 0))
        out.paste(im.crop((cx, 0, cx + 1, h)).resize((width - w + 1, h)), (cx, 0))
        out.paste(im.crop((cx + 1, 0, w, h)), (width - (w - cx - 1), 0))
        im, w = out, width
    if height and height > h:
        cy = h // 2
        out = Image.new(im.mode, (w, height))
        out.paste(im.crop((0, 0, w, cy)), (0, 0))
        out.paste(im.crop((0, cy, w, cy + 1)).resize((w, height - h + 1)), (0, cy))
        out.paste(im.crop((0, cy + 1, w, h)), (0, height - (h - cy - 1)))
        im = out
    return im


def clear_layered(root):
    """Açılışta pencere saydamlıkla (-alpha) gizlenip gösterilir; bu, Windows'ta
    pencereyi kalıcı olarak katmanlı (WS_EX_LAYERED) yapar ve Tk alpha 1.0'a
    dönünce bunu geri almaz. Katmanlı pencerede alt bileşenler, büyütme gibi
    boyut değişimlerinde bazı ekran kartlarında siyah çizilebiliyor; saydamlık
    artık gerekmediği için özellik kaldırılır."""
    try:
        import ctypes
        u32 = ctypes.windll.user32
        root.update_idletasks()
        hwnd = u32.GetParent(root.winfo_id()) or root.winfo_id()
        GWL_EXSTYLE, WS_EX_LAYERED = -20, 0x80000
        style = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if style & WS_EX_LAYERED:
            u32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)
            u32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
    except Exception:
        pass


def work_area():
    """Görev çubuğu hariç ana ekran alanı (sol, üst, sağ, alt), fiziksel piksel."""
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return 0, 0, 1280, 720


def notice_window_style(win):
    """Bildirim penceresi: odağı çalmasın (WS_EX_NOACTIVATE), görev çubuğunda
    görünmesin (WS_EX_TOOLWINDOW), Windows 11'de köşeleri yuvarlak olsun."""
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = -20, 0x80, 0x08000000
        u32 = ctypes.windll.user32
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, u32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


# --------------------------------------------------------------------------
# Kenar yumuşatmalı çizim
# --------------------------------------------------------------------------
class AAImage:
    """Tkinter'ın çizim alanı daire ve eğik çizgileri kenar yumuşatmadan çizer;
    tırtıklı görünürler. Şekiller burada SS kat büyük bir resme çizilip yüksek
    kaliteyle küçültülür. Koordinatlar mantıksal piksel (ekran ölçeği öncesi)."""

    SS = 4

    def __init__(self, w, h, ui, bg):
        self.pw, self.ph = max(1, round(w * ui)), max(1, round(h * ui))
        self.k = self.pw * self.SS / w
        self.img = Image.new("RGB", (self.pw * self.SS, self.ph * self.SS), bg)
        self.d = ImageDraw.Draw(self.img)

    def _p(self, x, y):
        return (x * self.k, y * self.k)

    def _w(self, width):
        return max(1, round(width * self.k))

    def line(self, pts, color, width, caps=True):
        xy = [self._p(x, y) for x, y in pts]
        self.d.line(xy, fill=color, width=self._w(width), joint="curve")
        if caps:
            r = width * self.k / 2
            for x, y in (xy[0], xy[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=color)

    def dashed(self, a, b, color, width, dash=4.0, gap=3.0):
        (x0, y0), (x1, y1) = a, b
        n = math.hypot(x1 - x0, y1 - y0)
        t = 0.0
        while t < n:
            t2 = min(n, t + dash)
            self.line([(x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n),
                       (x0 + (x1 - x0) * t2 / n, y0 + (y1 - y0) * t2 / n)], color, width, caps=False)
            t = t2 + gap

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=1.0):
        self.d.ellipse((*self._p(x0, y0), *self._p(x1, y1)), fill=fill, outline=outline,
                       width=self._w(width) if outline else 0)

    def circle(self, cx, cy, r, **kw):
        self.ellipse(cx - r, cy - r, cx + r, cy + r, **kw)

    def rrect(self, x0, y0, x1, y1, r, fill):
        self.d.rounded_rectangle((*self._p(x0, y0), *self._p(x1, y1)), radius=r * self.k, fill=fill)

    def photo(self):
        return ImageTk.PhotoImage(self.img.reduce(self.SS))


def scaled_icon(size):
    """Logo simgesini istenen boyuta yüksek kaliteyle küçültür."""
    img = Image.open(resource("icon.png")).convert("RGBA")
    return img.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------------
# Bluetooth (ayrı bir iş parçacığında, Windows'un kendi BLE arayüzüyle)
# --------------------------------------------------------------------------
class DeviceLink(threading.Thread):
    """Eşleştirilmiş Lookie'yi bulur, servise bağlanır, kopunca yeniden dener.

    Arayüze olayları `events` kuyruğuyla iletir:
      ("status", anahtar), ("config", dict), ("telemetry", tuple), ("disconnected", None)
    """

    def __init__(self, events):
        super().__init__(daemon=True)
        self.events = events
        self.loop = None
        self.stop_flag = False
        self._dev = None
        self._svc = None
        self._tel = None
        self._ctl = None
        self._cfg = None
        self._lost = False
        self._misses = 0  # servis/özellik bulunamayan ardışık denemeler
        self._ota_ctl = self._ota_dat = None
        self.ota_cancel = False

    # -- iş parçacığı --------------------------------------------------------
    def run(self):
        import winrt.runtime as rt
        try:
            rt.init_apartment(rt.MTA)
        except Exception:
            pass
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    def call(self, coro_fn, *args):
        """Arayüz iş parçacığından bir BLE işlemi başlatır."""
        if self.loop:
            asyncio.run_coroutine_threadsafe(coro_fn(*args), self.loop)

    async def _main(self):
        while not self.stop_flag:
            if self._ctl is None:
                try:
                    await self._connect()
                except Exception:
                    self._cleanup()
                    # Cihaz yanıt vermeden biten bir deneme: "aranıyor"da kalma.
                    self.events.put(("status", "offline"))
            elif self._lost:
                self._cleanup()
                self.events.put(("disconnected", None))
            await asyncio.sleep(2.0)
        self._cleanup()

    # -- bağlantı ------------------------------------------------------------
    async def _connect(self):
        from winrt.windows.devices.bluetooth import (BluetoothCacheMode,
                                                     BluetoothConnectionStatus,
                                                     BluetoothLEDevice)
        from winrt.windows.devices.bluetooth.genericattributeprofile import (
            GattClientCharacteristicConfigurationDescriptorValue as Cccd,
            GattCommunicationStatus)
        from winrt.windows.devices.enumeration import DeviceInformation

        sel = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
        infos = await DeviceInformation.find_all_async_aqs_filter(sel)
        info = None
        for i in infos:
            if any(n in (i.name or "").lower() for n in DEVICE_NAMES):
                info = i
                break
        if info is None:
            self.events.put(("status", "not_paired"))
            return

        dev = await BluetoothLEDevice.from_id_async(info.id)
        # Windows cihazın eski hizmet listesini önbellekte tutabiliyor: önce
        # önbellekten, bulamazsa cihazdan yeniden sor.
        res = await dev.get_gatt_services_for_uuid_async(SVC_UUID)
        if res.status == GattCommunicationStatus.SUCCESS and not res.services:
            res = await dev.get_gatt_services_for_uuid_async(SVC_UUID, BluetoothCacheMode.UNCACHED)
        if res.status != GattCommunicationStatus.SUCCESS:
            dev.close()
            self.events.put(("status", "offline"))
            return
        if not res.services:
            # Eşleşmiş ama kapalı bir cihaz için Windows hem "bağlı" durumu
            # hem de "başarılı" ama boş bir liste döndürebiliyor; eskiden bu
            # "firmware desteklemiyor" diye gösteriliyordu. Eski firmware ancak
            # cihaz gerçekten yanıt veriyorsa (bütün servisleri önbelleğe
            # bakmadan okunabiliyor ve içlerinde Lookie servisi yoksa) denir.
            old_fw = False
            if dev.connection_status == BluetoothConnectionStatus.CONNECTED:
                try:
                    every = await dev.get_gatt_services_async(BluetoothCacheMode.UNCACHED)
                    old_fw = every.status == GattCommunicationStatus.SUCCESS and len(every.services) > 0
                    for sv in every.services:
                        sv.close()
                except Exception:
                    old_fw = False
            dev.close()
            if old_fw:
                self._miss("old_fw")
            else:
                self._misses = 0
                self.events.put(("status", "offline"))
            return

        svc = res.services[0]
        try:
            chs = await svc.get_characteristics_async(BluetoothCacheMode.UNCACHED)
        except OSError as e:
            svc.close()
            dev.close()
            if getattr(e, "winerror", None) == STALE_GATT_ERROR:
                # Firmware servis tablosunu değiştirdi (ör. yeni özellik eklendi)
                # ama Windows eşleşmenin eski tablosunu kullanıyor ve her sorguyu
                # reddediyor. Bunu temizlemenin bir arayüzü yok: cihaz yeniden
                # eşleştirilmeli.
                self.events.put(("status", "stale_cache"))
                return
            raise
        if chs.status != GattCommunicationStatus.SUCCESS:
            # Servis Windows'un önbelleğinden geldi ama cihaz yanıt vermiyor
            # (kapalı ya da menzil dışında): eski firmware değil, bağlı değil.
            svc.close()
            dev.close()
            self._misses = 0
            self.events.put(("status", "offline"))
            return
        by = {uuid.UUID(str(c.uuid)): c for c in chs.characteristics}
        if not all(u in by for u in (TEL_UUID, CFG_UUID, CTL_UUID)):
            svc.close()
            dev.close()
            self._miss("old_fw")
            return
        self._misses = 0
        tel = by[TEL_UUID]
        # Bildirim tanımlayıcısının tutamacı da önbellekte eski kalabiliyor.
        await tel.get_descriptors_async(BluetoothCacheMode.UNCACHED)

        self._dev, self._svc, self._tel, self._cfg, self._ctl = dev, svc, tel, by[CFG_UUID], by[CTL_UUID]
        # Güncelleme kanalları yalnızca OTA destekli firmware'de (1.2.0+) var.
        self._ota_ctl, self._ota_dat = by.get(OTA_CTL_UUID), by.get(OTA_DAT_UUID)
        self._lost = False

        def on_status(d, _):
            if d.connection_status != BluetoothConnectionStatus.CONNECTED:
                self._lost = True
        self._status_token = dev.add_connection_status_changed(on_status)

        await self._read_config()

        def on_tel(_, args):
            data = self._buf_to_bytes(args.characteristic_value)
            if len(data) >= struct.calcsize(TEL_FORMAT):
                self.events.put(("telemetry", struct.unpack_from(TEL_FORMAT, data)))
            elif len(data) >= struct.calcsize(TEL_FORMAT_V1):
                self.events.put(("telemetry", struct.unpack_from(TEL_FORMAT_V1, data) + (BATTERY_UNKNOWN,)))
        self._tel_token = tel.add_value_changed(on_tel)
        st = await tel.write_client_characteristic_configuration_descriptor_async(Cccd.NOTIFY)
        if st != GattCommunicationStatus.SUCCESS:
            raise RuntimeError("subscribe failed")
        self.events.put(("status", "connected"))

    def _miss(self, status):
        # Windows'un önbelleği ilk denemelerde eksik liste verebiliyor; uyarıyı
        # ancak üst üste birkaç başarısızlıktan sonra göster.
        self._misses += 1
        self.events.put(("status", status if self._misses >= 3 else "searching"))

    def _cleanup(self):
        for obj, attr in ((self._tel, "_tel_token"), (self._dev, "_status_token")):
            tok = getattr(self, attr, None)
            if obj is not None and tok is not None:
                try:
                    (obj.remove_value_changed if attr == "_tel_token" else obj.remove_connection_status_changed)(tok)
                except Exception:
                    pass
            setattr(self, attr, None)
        for obj in (self._svc, self._dev):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        self._dev = self._svc = self._tel = self._cfg = self._ctl = None
        self._ota_ctl = self._ota_dat = None

    @staticmethod
    def _buf_to_bytes(buf):
        from winrt.windows.storage.streams import DataReader
        reader = DataReader.from_buffer(buf)
        out = bytearray(buf.length)
        reader.read_bytes(out)
        return bytes(out)

    # -- işlemler -----------------------------------------------------------
    async def _read_config(self):
        from winrt.windows.devices.bluetooth import BluetoothCacheMode
        if self._cfg is None:
            return
        try:
            r = await self._cfg.read_value_with_cache_mode_async(BluetoothCacheMode.UNCACHED)
            self.events.put(("config", json.loads(self._buf_to_bytes(r.value).decode())))
        except Exception:
            self._lost = True

    async def read_config(self):
        await self._read_config()

    # -- firmware güncellemesi ------------------------------------------------
    def ota_supported(self):
        return self._ota_ctl is not None and self._ota_dat is not None

    async def ota(self, path, sha256, size):
        """Firmware'i cihaza gönderir (protokol: OtaUpdate.h). Olaylar:
        ("ota_progress", (gönderilen, toplam)), ("ota_done", None),
        ("ota_failed", neden)."""
        from winrt.windows.devices.bluetooth import BluetoothCacheMode
        from winrt.windows.devices.bluetooth.genericattributeprofile import (
            GattCommunicationStatus, GattSession, GattWriteOption)
        from winrt.windows.storage.streams import DataWriter

        async def write(ch, payload):
            w = DataWriter()
            w.write_bytes(payload)
            st = await ch.write_value_with_option_async(w.detach_buffer(), GattWriteOption.WRITE_WITH_RESPONSE)
            if st != GattCommunicationStatus.SUCCESS:
                raise RuntimeError("cihaza yazılamadı")

        self.ota_cancel = False
        try:
            if not self.ota_supported():
                raise RuntimeError("cihazdaki firmware Bluetooth güncellemesini desteklemiyor")
            with open(path, "rb") as f:
                data = f.read()
            if size and len(data) != size:
                raise RuntimeError("dosya boyutu tutmuyor")
            # Parça boyutu: Windows'un bu bağlantıda kabul ettiği en büyük paket
            # (cihaz 517'ye kadar ister); özellik en fazla 512 bayt alır.
            chunk = 180
            try:
                session = await GattSession.from_device_id_async(self._dev.bluetooth_device_id)
                chunk = max(20, min(512, session.max_pdu_size - 3))
            except Exception:
                pass
            ctl, dat = self._ota_ctl, self._ota_dat
            await write(ctl, f"begin {len(data)} {sha256}".encode())
            total, sent, last = len(data), 0, -1
            while sent < total:
                if self.ota_cancel:
                    try:
                        await write(ctl, b"abort")
                    except Exception:
                        pass
                    raise RuntimeError("iptal edildi")
                part = data[sent:sent + chunk]
                await write(dat, part)
                sent += len(part)
                pct = sent * 100 // total
                if pct != last:
                    last = pct
                    self.events.put(("ota_progress", (sent, total)))
            await write(ctl, b"end")
            await asyncio.sleep(0.3)
            r = await ctl.read_value_with_cache_mode_async(BluetoothCacheMode.UNCACHED)
            state = self._buf_to_bytes(r.value).decode(errors="replace").split(",")
            if state[0] != "done":
                raise RuntimeError("cihaz firmware'i doğrulayamadı (" + (state[3] if len(state) > 3 else "?") + ")")
            self.events.put(("ota_done", None))
        except Exception as e:
            self.events.put(("ota_failed", str(e) or e.__class__.__name__))

    async def send(self, command, reread=False):
        from winrt.windows.devices.bluetooth.genericattributeprofile import GattWriteOption
        from winrt.windows.storage.streams import DataWriter
        if self._ctl is None:
            return
        try:
            w = DataWriter()
            w.write_bytes(command.encode())
            await self._ctl.write_value_with_option_async(w.detach_buffer(), GattWriteOption.WRITE_WITH_RESPONSE)
        except Exception:
            self._lost = True
            return
        if reread:
            await asyncio.sleep(0.15)
            await self._read_config()

    async def send_many(self, commands, reread=False):
        """Komutları sırayla gönderir (ayrı call()'lar sırayı korumaz)."""
        for c in commands:
            await self.send(c)
        if reread:
            await asyncio.sleep(0.15)
            await self._read_config()


# --------------------------------------------------------------------------
# Ayar tanımları
# --------------------------------------------------------------------------
# anahtar, sekme, min, max, adım, ölçek ("lin" / "log"), birim, ondalık
SETTINGS = [
    ("ylin", "tab_yaw", 0, 45, 0.5, "lin", "deg", 1),
    ("yblend", "tab_yaw", 0, 45, 0.5, "lin", "deg", 1),
    ("ygain", "tab_yaw", 1, 12, 0.1, "lin", "", 1),
    ("prng", "tab_pitch", 30, 30000, 0, "log", "deg", 0),
    ("poff", "tab_pitch", -0.5, 0.5, 0.005, "lin", "", 3),
    ("pdz", "tab_pitch", 0, 30, 0.5, "lin", "deg", 1),
    ("ac", "tab_chair", 0, 1, 1, "bool", "", 0),
    ("acw", "tab_chair", 1, 30, 0.5, "lin", "deg", 1),
    ("act", "tab_chair", 2, 120, 1, "lin", "sec", 0),
    ("acd", "tab_chair", 1, 30, 0.5, "lin", "deg_s", 1),
    ("acm", "tab_chair", 0, 10000, 100, "lin", "ms", 0),
    ("smc", "tab_smooth", 0.05, 10, 0.05, "lin", "hz", 2),
    ("smb", "tab_smooth", 0, 1, 0.005, "lin", "", 3),
    ("adz", "tab_smooth", 0, 5, 0.1, "lin", "deg", 1),
    ("rsm", "tab_smooth", 0, 2000, 50, "lin", "ms", 0),
]


def yaw_curve(h, lin, blend, gain):
    a = abs(h)
    if a <= lin:
        v = a
    elif a <= lin + blend:
        d = a - lin
        v = lin + d + (gain - 1) * d * d / (2 * blend)
    else:
        v = lin + blend + (gain - 1) * blend / 2 + gain * (a - lin - blend)
    return v if h >= 0 else -v


# --------------------------------------------------------------------------
# Arayüz
# --------------------------------------------------------------------------
class App:
    def __init__(self, root, splash=None, frame=None):
        self.root = root
        self.splash = splash   # açılış animasyonu (varsa)
        self.frame = frame     # Windows başlık çubuğu yerine uygulamanın kendi başlığı (varsa)
        self.win_btns = {}
        self.events = queue.Queue()
        self.link = DeviceLink(self.events)
        self.values = {}       # anahtar -> değer (cihazdaki son bilinen)
        self.widgets = {}      # anahtar -> (değişken, etiket, ölçek)
        self.pending = {}      # gönderilmeyi bekleyen değişiklikler
        self.send_job = None
        self.suppress = False
        self.connected = False
        self.dirty = False
        self.yaw_range = 180.0
        self.tel = None
        self.tel_age = 0
        self.help_win = None   # açık yardım penceresi
        self.help_key = None
        self.drop_win = None   # açık açılır liste
        self.drop_box = None
        self.gyro_win = None   # kalibrasyon sürerken açık bekleme penceresi
        self.overlays = []     # uyarıların arkasındaki bulanık katmanlar
        self.last_cfg = None   # cihazdan okunan son ayarlar
        self.status_key = "searching"
        self.import_pending = False
        self.bat = None        # (yüzde, şarjda mı, USB'de mi); None = gösterme
        self.bat_phase = 0.0   # şarj animasyonunun konumu (0..1)
        self.bat_job = None
        self.bat_demo_i = 0
        self.bat_demo_job = None
        self.real_bat = None     # cihazdan gelen son pil durumu (test açıkken de izlenir)
        self.low_warned = False  # bu düşüşte uyarıldı mı (şarj ya da %15 ile sıfırlanır)
        self.notice_win = None
        self.tray = None         # sistem tepsisi simgesi (ayar açıksa)
        self.tray_menu = None    # açık tepsi menüsü
        # Güncelleme: son okunan yayın bilgisi, bu oturumda sorulan/atlanan
        # sürümler, süren iş (indirme / cihaza yükleme) ve ilerleme penceresi.
        self.upd_manifest = None
        self.upd_asked = set()
        self.upd_busy = None
        self.upd_win = None
        self.upd_note = None  # ilerleme gösteren bildirim kartı
        self.upd_cancel = False
        self.upd_status_text = ""
        self.pending_app_update = None
        # Profiller: etkin profil cihaza bu bağlantıda eşitlendi mi, sıradaki
        # okuma (varsayılanlar yüklendikten sonra) profile alınacak mı.
        self.store = profiles.ProfileStore(first_name=T["profile_n"].format(n=1))
        self.prof_synced = False
        self.prof_capture = False
        self.prof_page = None

        root.title(T["title"])
        root.minsize(900, 600)
        # Ekran ölçeği (%100 = 1.0); çizimler fiziksel piksel boyutunda üretilir.
        self.ui = max(1.0, root.winfo_fpixels("1i") / 96.0)
        try:
            self.icons = [ImageTk.PhotoImage(scaled_icon(n)) for n in (16, 24, 32, 48, 64, 256)]
            root.iconphoto(True, *self.icons)
        except Exception:
            self.icons = []
        self._apply_theme()
        self._build()
        if PREFS["topmost"]:
            root.attributes("-topmost", True)
        self.link.start()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind_all("<Button-1>", self._click_anywhere, add="+")
        root.bind_all("<MouseWheel>", self._wheel, add="+")
        root.bind_all("<Escape>", lambda _e: (self._close_help(), self._close_dropdown()), add="+")
        # Uygulamadan çıkılınca (Alt+Tab, simge durumu) yardım öbür pencerelerin
        # üstünde kalmasın.
        root.bind("<FocusOut>", lambda e: (self._close_help(), self._close_dropdown()) if e.widget is root else None, add="+")
        root.bind("<Unmap>", lambda e: (self._close_help(), self._close_dropdown()) if e.widget is root else None, add="+")
        # Pencere taşınır ya da boyutlanırsa yardımı kapat (alt bileşenlerin
        # Configure olayları da buraya geldiği için yalnızca ana pencereye bak).
        root.bind("<Configure>", lambda e: (self._close_help(), self._close_dropdown()) if e.widget is root else None, add="+")
        root.bind("<Configure>", lambda e: self._update_caption() if e.widget is root else None, add="+")
        # Simge durumundan geri gelince de başlık alanını yenile.
        root.bind("<Map>", lambda e: self._update_caption() if e.widget is root else None, add="+")
        root.after(50, self._poll)
        self._update_tray()
        root.after(5000, lambda: self._check_updates(manual=False))
        # Görev çubuğundan ya da Win+Aşağı ile küçültülünce de tepsiye gizle.
        root.bind("<Unmap>", lambda e: root.after(0, self._maybe_hide_to_tray) if e.widget is root else None, add="+")
        root.after(1000, self._tick)
        if self._demo_on():
            self.bat_demo_job = root.after(500, self._battery_demo)

    def _apply_theme(self):
        theme = PREFS["theme"]
        self.dark = windows_dark_mode() if theme == "system" else theme == "dark"
        try:
            import sv_ttk
            sv_ttk.set_theme("dark" if self.dark else "light")
        except Exception:
            pass
        self._apply_fonts()
        self._apply_accent()
        self.bg = "#1c1c1c" if self.dark else "#fafafa"
        self.fg = "#e6e6e6" if self.dark else "#1f2937"
        self.muted = "#9ca3af" if self.dark else "#6b7280"
        self.grid_c = "#3a3a3a" if self.dark else "#e5e7eb"
        if self.frame:
            try:
                self.frame.set_cover_color(self.bg)
            except Exception:
                pass
        self._style_widgets()
        self._title_bar(self.dark)

    def _apply_accent(self):
        """Temanın mavi vurgu rengini (onay kutuları, anahtar, kaydırıcılar,
        açılır listeler, Kaydet düğmesi) logonun turkuazına çevirir.

        sv_ttk bu öğeleri bir resim sayfasından (spritesheet) keserek çizer;
        mavi resmin içindedir. Sayfadaki mavi pikseller turkuaza boyanır ve
        her öğenin resmine yeniden kopyalanır. Bir pikselin doygunluğu ve
        parlaklığı temanın referans mavisine oranlanarak korunur; böylece
        üzerine gelme / basılı tonları ve yumuşak kenarlar da doğru kalır."""
        style = ttk.Style(self.root)
        theme = style.theme_use()
        name = {"sun-valley-dark": "dark", "sun-valley-light": "light"}.get(theme)
        if name is None:
            return
        done = getattr(self, "_accent_done", set())
        self._accent_done = done
        if name not in done:
            try:
                import colorsys, re
                import sv_ttk
                folder = os.path.join(os.path.dirname(sv_ttk.__file__), "theme")
                ref = {"dark": "#57c8ff", "light": "#005fb8"}[name]
                rh, rs, rv = colorsys.rgb_to_hsv(*(int(ref[i:i + 2], 16) / 255 for i in (1, 3, 5)))
                th, ts, tv = colorsys.rgb_to_hsv(*(int(TEAL[i:i + 2], 16) / 255 for i in (1, 3, 5)))
                sheet = Image.open(os.path.join(folder, f"spritesheet_{name}.png")).convert("RGBA")
                px = sheet.load()
                cache = {}
                for y in range(sheet.height):
                    for x in range(sheet.width):
                        r, g, b, a = px[x, y]
                        if a == 0:
                            continue
                        key = (r, g, b)
                        out = cache.get(key)
                        if out is None:
                            h, sat, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                            if sat > 0.08 and 0.5 <= h <= 0.72:  # mavi aile
                                nr, ng, nb = colorsys.hsv_to_rgb(th, min(1.0, ts * sat / rs),
                                                                 min(1.0, tv * v / rv))
                                out = (round(nr * 255), round(ng * 255), round(nb * 255))
                            else:
                                out = key
                            cache[key] = out
                        if out != key:
                            px[x, y] = (*out, a)
                photo = ImageTk.PhotoImage(sheet, master=self.root)
                with open(os.path.join(folder, f"sprites_{name}.tcl"), encoding="utf-8") as f:
                    info = re.findall(r"^\s*([\w-]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", f.read(), re.M)
                for sprite, x, y, w, h in info:
                    x, y, w, h = int(x), int(y), int(w), int(h)
                    img = self.root.tk.call("set", f"ttk::theme::sv_{name}::I({sprite})")
                    self.root.tk.call(img, "copy", str(photo), "-from", x, y, x + w, y + h,
                                      "-to", 0, 0, "-compositingrule", "set")
                self._fast_backgrounds(name, sheet, {s[0]: tuple(map(int, s[1:])) for s in info})
                done.add(name)
            except Exception:
                log_error("accent")
        # Resim dışındaki vurgu renkleri (stil ayarları tema başına).
        sel = TEAL_DARK if name == "dark" else TEAL
        # Sekmeye tıklayınca çıkan kesikli odak çerçevesini kaldır: sekme
        # yerleşiminden Notebook.focus öğesi çıkarılır (etiket doğrudan
        # dolgunun içine yerleşir).
        try:
            layout = self.root.tk.eval("ttk::style layout TNotebook.Tab")
            if "Notebook.focus" in layout:
                self.root.tk.call("ttk::style", "layout", "TNotebook.Tab",
                                  "Notebook.tab -sticky nswe -children {Notebook.padding -side top -sticky nswe "
                                  "-children {Notebook.label -side top -sticky {}}}")
        except tk.TclError:
            pass
        style.map("TCombobox", selectbackground=[("readonly hover", sel), ("readonly focus", sel)],
                  selectforeground=[("readonly hover", "#ffffff"), ("readonly focus", "#ffffff")])

    def _fast_backgrounds(self, name, sheet, boxes):
        """Büyük alanlara gerilen tema parçalarını hızlandırır.

        Tk bir resim öğesini büyütürken resmin ortasını alanı dolduracak kadar
        tek tek kopyalar: tam ekranda sekme zemini ~1700, her kaydırıcı ~125
        kopya; büyütmede arayüz yarım saniye boyunca yarım çizili (siyah
        kutular) kalıyordu. Parçaların ortası düz renk olduğu için, ortası
        çoğaltılarak büyütülmüş bir kopyayla yeni öğeler oluşturulur ve
        yerleşimlerde temanınkilerin yerine konur. -width/-height orijinal
        boyutu verir; yoksa öğe büyük resmin boyutunu ister ve pencere
        ekrandan taşar."""
        specs = (  # parça, temadaki öğe, büyütme (en, boy), öğe seçenekleri, kullanan stiller
            ("notebook-border", "Notebook.border", (1200, 1200), ("-border", 5, "-padding", 5), ("TNotebook",)),
            ("card", "Labelframe.border", (1200, 1200), ("-border", 5, "-padding", 4, "-sticky", "nsew"),
             ("TLabelframe",)),
            ("slider-trough-hor", "Horizontal.Scale.trough", (1200, 0),
             ("-border", 5, "-padding", 0, "-sticky", "ew"), ("Horizontal.TScale",)),
            ("slider-trough-vert", "Vertical.Scale.trough", (0, 1200),
             ("-border", 5, "-padding", 0, "-sticky", "ns"), ("Vertical.TScale",)),
            ("scrollbar-trough-hor", "Horizontal.Scrollbar.trough", (1200, 0),
             ("-sticky", "ew", "-border", "6 0"), ("Horizontal.TScrollbar",)),
            ("scrollbar-trough-vert", "Vertical.Scrollbar.trough", (0, 1200),
             ("-sticky", "ns", "-border", "0 6"), ("Vertical.TScrollbar",)),
        )
        tk_ = self.root.tk
        self._accent_photos = getattr(self, "_accent_photos", [])
        for sprite, element, grow, opts, styles in specs:
            try:
                x, y, w, h = boxes[sprite]
                big = stretch_center(sheet.crop((x, y, x + w, y + h)), *grow)
                photo = ImageTk.PhotoImage(big, master=self.root)
                self._accent_photos.append(photo)
                new = f"Lk{name}.{element}"
                tk_.call("ttk::style", "element", "create", new, "image", str(photo), *opts,
                         "-width", w, "-height", h)
                for style in styles:
                    layout = tk_.eval(f"ttk::style layout {style}")  # ham Tcl metni
                    tk_.call("ttk::style", "layout", style, layout.replace(element, new))
            except Exception:
                log_error("fast backgrounds")

    def _apply_fonts(self):
        """Temanın ve Tk'nın adlandırılmış yazı tiplerini Nunito'ya çevirir;
        böylece ttk bileşenleri (sekmeler, düğmeler, çerçeve başlıkları) da
        aynı yazıyı kullanır."""
        if not HAVE_NUNITO:
            return
        from tkinter import font as tkfont
        semi = {"SunValleyBodyStrongFont", "SunValleySubtitleFont", "SunValleyTitleFont",
                "SunValleyTitleLargeFont", "SunValleyDisplayFont"}
        for name in tkfont.names(self.root):
            if name.startswith("Tk") or name.startswith("SunValley"):
                try:
                    tkfont.nametofont(name, root=self.root).configure(family=FONT_SEMI if name in semi else FONT)
                except tk.TclError:
                    pass

    def _style_widgets(self):
        """Logo renginde düğme stili ve temaya uyan açılır listeler."""
        style = ttk.Style(self.root)
        u = self.ui
        # Düğme zemini: yuvarlak köşeli, kenar yumuşatmalı resimler (ortası
        # esneyerek düğme boyutuna uyar).
        def face(color, outline=None):
            img = Image.new("RGBA", (round(24 * u) * 4, round(24 * u) * 4), (0, 0, 0, 0))
            ImageDraw.Draw(img).rounded_rectangle((0, 0, img.width - 1, img.height - 1),
                                                  radius=round(5 * u) * 4, fill=color, outline=outline,
                                                  width=max(4, round(1.3 * u * 4)) if outline else 0)
            return ImageTk.PhotoImage(img.reduce(4))
        # Öğe her tema için bir kez tanımlanır; resimleri o tema boyunca
        # yaşamalı, yoksa temalar arasında geçerken düğme çizilemez.
        name = "TealDark.button" if self.dark else "TealLight.button"
        self._teal_faces = getattr(self, "_teal_faces", {})
        if name not in self._teal_faces:
            disabled = "#3a3a3a" if self.dark else "#d1d5db"
            faces = [face(TEAL), face(TEAL_HOVER), face(TEAL_DARK), face(disabled)]
            self._teal_faces[name] = faces
            try:
                style.element_create(name, "image", faces[0], ("disabled", faces[3]), ("pressed", faces[2]),
                                     ("active", faces[1]), border=round(8 * u), sticky="nsew")
            except tk.TclError:
                pass
        style.layout("Teal.TButton", [(name, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})])
        style.configure("Teal.TButton", foreground="#ffffff", anchor="center",
                        padding=(round(12 * u), round(6 * u)), font=(FONT, 10, "bold"))
        style.map("Teal.TButton", foreground=[("disabled", "#9ca3af" if self.dark else "#ffffff")])

        # İkincil düğme: logo renginde çerçeve ve yazı, üzerine gelince hafif
        # logo renginde zemin. Ölçüleri Teal.TButton ile aynı; yan yana
        # durduklarında boyları eşit olur.
        name = "TealOutlineDark.button" if self.dark else "TealOutlineLight.button"
        if name not in self._teal_faces:
            r, g, b = (int(TEAL[i:i + 2], 16) for i in (1, 3, 5))
            edge = TEAL if self.dark else "#5fc9bb"
            off = "#3a3a3a" if self.dark else "#d1d5db"
            faces = [face((r, g, b, 0), edge), face((r, g, b, 34), TEAL), face((r, g, b, 64), TEAL),
                     face((r, g, b, 0), off)]
            self._teal_faces[name] = faces
            try:
                style.element_create(name, "image", faces[0], ("disabled", faces[3]), ("pressed", faces[2]),
                                     ("active", faces[1]), border=round(8 * u), sticky="nsew")
            except tk.TclError:
                pass
        style.layout("TealOutline.TButton", [(name, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})])
        ink = TEAL_HOVER if self.dark else TEAL_DARK
        style.configure("TealOutline.TButton", foreground=ink, anchor="center",
                        padding=(round(12 * u), round(6 * u)), font=(FONT, 10, "bold"))
        style.map("TealOutline.TButton", foreground=[("disabled", "#6b7280" if self.dark else "#9ca3af")])

        # Hayalet düğme (Hakkında gibi ikincil işler): çerçevesiz, üzerine
        # gelince hafif zemin; yazı soluk griden normal renge geçer.
        name = "GhostDark.button" if self.dark else "GhostLight.button"
        if name not in self._teal_faces:
            tone = (255, 255, 255) if self.dark else (15, 23, 42)
            faces = [face((*tone, 0)), face((*tone, 16 if self.dark else 12)),
                     face((*tone, 28 if self.dark else 22)), face((*tone, 0))]
            self._teal_faces[name] = faces
            try:
                style.element_create(name, "image", faces[0], ("disabled", faces[3]), ("pressed", faces[2]),
                                     ("active", faces[1]), border=round(8 * u), sticky="nsew")
            except tk.TclError:
                pass
        style.layout("Ghost.TButton", [(name, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": ""})]})]})])
        muted = "#9ca3af" if self.dark else "#6b7280"
        ink = "#e6e6e6" if self.dark else "#1f2937"
        style.configure("Ghost.TButton", foreground=muted, anchor="center",
                        padding=(round(10 * u), round(5 * u)), font=(FONT, 10))
        style.map("Ghost.TButton", foreground=[("active", ink), ("pressed", ink)])


    def _title_bar(self, dark):
        # Windows 10 (20H1+) ve 11: başlık çubuğunu da temaya uydur.
        try:
            import ctypes
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            on = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
        except Exception:
            pass

    # -- pencere düğmeleri ----------------------------------------------------
    def _build_window_buttons(self, head):
        """Windows'un başlık çubuğu yerine başlığın sağındaki simge durumuna
        küçült, büyüt ve kapat düğmeleri."""
        box = ttk.Frame(head)
        box.pack(side="right")
        self.win_btns = {}
        actions = {
            "min": self._minimize,
            "max": lambda: self.root.state("normal" if self.root.state() == "zoomed" else "zoomed"),
            "close": self._on_close,
        }
        for kind in ("min", "max", "close"):
            c = tk.Canvas(box, width=round(40 * self.ui), height=round(32 * self.ui),
                          highlightthickness=0, bg=self.bg, cursor="arrow")
            c.pack(side="left", padx=(2, 0))
            c.hover = False
            c.bind("<Enter>", lambda _e, c=c, k=kind: self._hover_window_button(c, k, True))
            c.bind("<Leave>", lambda _e, c=c, k=kind: self._hover_window_button(c, k, False))

            def release(e, c=c, k=kind):
                if 0 <= e.x < c.winfo_width() and 0 <= e.y < c.winfo_height():
                    actions[k]()
            c.bind("<ButtonRelease-1>", release)
            self.win_btns[kind] = c
            self._draw_window_button(kind)
        self._max_state = self.frame.zoomed()

    def _bind_drag(self, widget):
        """Başlıktaki bileşenler pencereyi sürüklesin. Tk'da her bileşen ayrı bir
        alt penceredir; Windows başlık alanı testini (WM_NCHITTEST) o alt
        pencereye sorduğu için ana pencerenin başlık ayarı oraya ulaşmaz.
        Sürükleyince Windows'un kendi taşıması başlar (ekran kenarına
        yaslama dahil); çift tıklama büyütür/küçültür."""
        if widget in self.win_btns.values():
            return
        widget.bind("<ButtonPress-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._drag_motion, add="+")
        widget.bind("<ButtonRelease-1>", self._end_drag, add="+")
        widget.bind("<Double-Button-1>", self._toggle_max, add="+")
        for child in widget.winfo_children():
            self._bind_drag(child)

    def _start_drag(self, e):
        self._drag_from = (e.x_root, e.y_root)

    def _drag_motion(self, e):
        """Fare basılıyken birkaç piksel kayınca Windows'un sürüklemesini başlatır.
        Basma anında başlatılmaz: kısa bir tıklamada düğme bırakılmış olur ve
        Windows pencereyi bir sonraki tıklamaya kadar fareye yapışık bırakır."""
        start = getattr(self, "_drag_from", None)
        if start is None or abs(e.x_root - start[0]) + abs(e.y_root - start[1]) < 4:
            return
        self._drag_from = None
        try:
            import ctypes
            from ctypes import wintypes
            u32 = ctypes.windll.user32
            if not u32.GetAsyncKeyState(0x01) & 0x8000:  # sol düğme artık basılı değil
                return
            # SendMessage DEĞİL: sürükleme döngüsü bu Python geri çağrısının
            # içinde dönerse Tk'nın zamanlayıcıları Python'a yeniden girer ve
            # süreç çöker (GIL). Kuyruğa bırakılınca döngü Tk'nın normal olay
            # akışında, kenardan boyutlandırma gibi çalışır.
            pt = wintypes.POINT()
            u32.GetCursorPos(ctypes.byref(pt))
            u32.ReleaseCapture()
            u32.PostMessageW(wintypes.HWND(self.frame.hwnd), 0x00A1, 2,  # WM_NCLBUTTONDOWN, HTCAPTION
                             (pt.x & 0xFFFF) | ((pt.y & 0xFFFF) << 16))
        except Exception:
            pass

    def _end_drag(self, _e=None):
        self._drag_from = None

    def _toggle_max(self, _e=None):
        self.root.state("normal" if self.root.state() == "zoomed" else "zoomed")

    def _hover_window_button(self, c, kind, on):
        c.hover = on
        self._draw_window_button(kind)

    def _draw_window_button(self, kind):
        c = self.win_btns.get(kind)
        if c is None:
            return
        img = AAImage(40, 32, self.ui, self.bg)
        color = self.fg
        if c.hover:  # simge kendi renginde, zemin aynı rengin açık tonunda
            color = {"close": CLOSE_COLOR, "max": MAX_COLOR}.get(kind, TEAL)
            img.rrect(0, 0, 40, 32, 6, tint(color, self.bg, HOVER_TINT[self.dark]))
        w = 1.3
        if kind == "min":
            img.line([(15, 16.5), (25, 16.5)], color, w, caps=False)
        elif kind == "max":
            if self.frame and self.frame.zoomed():
                img.line([(15, 13), (23, 13), (23, 21), (15, 21), (15, 13)], color, w, caps=False)
                img.line([(17, 13), (17, 11), (25, 11), (25, 19), (23, 19)], color, w, caps=False)
            else:
                img.line([(15, 11), (25, 11), (25, 21), (15, 21), (15, 11)], color, w, caps=False)
        else:
            img.line([(15, 11), (25, 21)], color, w)
            img.line([(25, 11), (15, 21)], color, w)
        c.photo = img.photo()
        c.delete("all")
        c.create_image(0, 0, image=c.photo, anchor="nw")

    def _uncover(self):
        """Boyut değişiminden sonra: bekleyen yerleşimi ve çizimi bitir, sonra
        örtüyü kısa bir geçişle söndür (bkz. winchrome.CustomFrame)."""
        try:
            self.root.update_idletasks()
        except tk.TclError:
            return

        def fade(a):
            self.frame.cover_alpha(a)
            if a > 0:
                self.root.after(15, fade, max(0, a - 40))
            else:
                self._uncovering = False

        def start():
            # Tk asıl çizimi olay döngüsünde gelen çizim mesajlarıyla yapar;
            # bu bekleme o mesajların işlenmesine zaman tanır.
            try:
                self.root.update_idletasks()
            except tk.TclError:
                return
            fade(215)
        self.root.after(150, start)

    def _update_caption(self):
        """Başlık alanını (sürüklenebilen yer) ve düğmelerin yerini Windows'a
        bildirir; büyütme durumu değiştiyse büyüt düğmesinin simgesini yeniler."""
        if not self.frame or not self.win_btns:
            return
        try:
            ox, oy = self.root.winfo_rootx(), self.root.winfo_rooty()
            head = self.head
            bottom = head.winfo_rooty() - oy + head.winfo_height() + round(6 * self.ui)
            rects = []
            for c in self.win_btns.values():
                x, y = c.winfo_rootx() - ox, c.winfo_rooty() - oy
                rects.append((x, y, x + c.winfo_width(), y + c.winfo_height()))
            self.frame.set_caption(bottom, rects)
            z = self.frame.zoomed()
            if z != getattr(self, "_max_state", None):
                self._max_state = z
                self._draw_window_button("max")
        except tk.TclError:
            pass

    # -- yerleşim -----------------------------------------------------------
    def _build(self):
        outer = self.outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x")
        try:
            self.head_logo = ImageTk.PhotoImage(scaled_icon(round(40 * self.ui)))
            ttk.Label(head, image=self.head_logo).pack(side="left", padx=(0, 10))
        except Exception:
            self.head_logo = None
        ttk.Label(head, text="Lookie", font=BRAND_FONT).pack(side="left")
        self.head = head
        if self.frame:
            self._build_window_buttons(head)
            head.bind("<Configure>", lambda _e: self._update_caption(), add="+")
        self.status_dot = tk.Canvas(head, width=round(12 * self.ui), height=round(12 * self.ui),
                                    highlightthickness=0, bg=self.bg)
        self.status_dot.pack(side="left", padx=(16, 6))
        self.status_label = ttk.Label(head, text=T["searching"])
        self.status_label.pack(side="left")
        # Pil göstergesi: "Bağlı" yazısının hemen yanında.
        self.bat_canvas = tk.Canvas(head, width=round(30 * self.ui), height=round(16 * self.ui),
                                    highlightthickness=0, bg=self.bg)
        self.bat_canvas.pack(side="left", padx=(14, 5))
        self.bat_label = ttk.Label(head, text="", foreground=self.muted)
        self.bat_label.pack(side="left")
        # Gizlenmiş bir güncellemenin ilerlemesi; tıklayınca pencere geri gelir.
        self.upd_head = ttk.Label(head, text="", foreground=TEAL, cursor="hand2", font=(FONT, 10, "bold"))
        self.upd_head.pack(side="left", padx=(14, 0))
        self.upd_head.bind("<Button-1>", lambda _e: self._show_progress())
        self._set_status("searching")
        self._draw_battery()
        if self.frame:
            self._bind_drag(head)
            in_head = lambda e: e.y < head.winfo_y() + head.winfo_height()
            outer.bind("<ButtonPress-1>", lambda e: self._start_drag(e) if in_head(e) else None, add="+")
            outer.bind("<B1-Motion>", self._drag_motion, add="+")
            outer.bind("<ButtonRelease-1>", self._end_drag, add="+")
            outer.bind("<Double-Button-1>", lambda e: self._toggle_max(e) if in_head(e) else None, add="+")

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True, pady=(14, 0))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Sol: canlı görünüm
        left = ttk.LabelFrame(body, text=T["live"], padding=12)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        self.dial = tk.Canvas(left, width=round(310 * self.ui), height=round(260 * self.ui),
                              highlightthickness=0, bg=self.bg)
        self.dial.pack()
        legend = ttk.Frame(left)
        legend.pack(pady=(4, 8))
        self._legend(legend, self.muted, T["head"])
        self._legend(legend, TEAL, T["view"])
        self._legend(legend, PITCH_COLOR, T["updown"])
        grid = ttk.Frame(left)
        grid.pack(fill="x")
        self.readouts = {}
        for i, key in enumerate(("head_yaw", "view_yaw", "pitch", "roll", "autoyaw", "pitch_axis")):
            ttk.Label(grid, text=T[key], foreground=self.muted).grid(row=i, column=0, sticky="w", pady=1)
            lbl = ttk.Label(grid, text="–", font=(FONT, 10, "bold"))
            lbl.grid(row=i, column=1, sticky="e", padx=(16, 0))
            self.readouts[key] = lbl
        grid.columnconfigure(1, weight=1)
        ttk.Label(left, text=T["sign_hint"], foreground=self.muted,
                  font=(FONT, 8)).pack(anchor="w", pady=(4, 0))
        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(12, 0))
        self.btn_recenter = ttk.Button(btns, text=T["recenter"], style="Teal.TButton",
                                       command=lambda: self.link.call(self.link.send, "recenter"))
        self.btn_recenter.pack(fill="x")
        self.btn_gyro = ttk.Button(btns, text=T["gyrocal"], style="TealOutline.TButton", command=self._gyrocal)
        self.btn_gyro.pack(fill="x", pady=(6, 0))
        # Cihaz bağlı değilken de açılır (bilinmeyen değerler "–").
        self.about_icon = self._info_icon()
        self.btn_about = ttk.Button(btns, text=" " + T["about"], image=self.about_icon, compound="left",
                                    style="Ghost.TButton", command=self._about, cursor="hand2")
        self.btn_about.pack(fill="x", pady=(8, 0))

        # Sağ: ayarlar
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.tabs = ttk.Notebook(right)
        self.tabs.grid(row=0, column=0, sticky="nsew")
        pages = {}
        self.tab_icons = {k: self._tab_icon(k) for k in ("tab_profile", "tab_yaw", "tab_pitch", "tab_chair",
                                                         "tab_smooth", "tab_app")}
        prof_holder, self.prof_page = self._scroll_page(self.tabs)
        self.tabs.add(prof_holder, text=" " + T["tab_profile"], image=self.tab_icons["tab_profile"], compound="left")
        self._build_profile_tab()
        for tab in ("tab_yaw", "tab_pitch", "tab_chair", "tab_smooth"):
            holder, page = self._scroll_page(self.tabs)
            page.columnconfigure(1, weight=1)
            self.tabs.add(holder, text=" " + T[tab], image=self.tab_icons[tab], compound="left")
            pages[tab] = page
        rows = {k: 0 for k in pages}
        for spec in SETTINGS:
            key, tab = spec[0], spec[1]
            rows[tab] = self._setting_row(pages[tab], rows[tab], *spec)
        app_holder, app_page = self._scroll_page(self.tabs)
        self.tabs.add(app_holder, text=" " + T["tab_app"], image=self.tab_icons["tab_app"], compound="left")
        self._build_app_tab(app_page)
        cv = ttk.Frame(pages["tab_yaw"])
        cv.grid(row=rows["tab_yaw"], column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Label(cv, text=T["curve"], foreground=self.muted).pack(anchor="w")
        self.curve = tk.Canvas(cv, width=round(440 * self.ui), height=round(170 * self.ui),
                               highlightthickness=0, bg=self.bg)
        self.curve.bind("<Configure>", lambda _e: self._draw_curve())
        self.curve.pack(fill="x", pady=(4, 0))

        foot = ttk.Frame(right)
        foot.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.dirty_label = ttk.Label(foot, text="", foreground=self.muted)
        self.dirty_label.pack(side="left")
        self.btn_save = ttk.Button(foot, text=T["save"], style="Accent.TButton", command=self._save)
        self.btn_save.pack(side="right")
        self.btn_revert = ttk.Button(foot, text=T["revert"],
                                     command=lambda: self.link.call(self.link.send, "revert", True))
        self.btn_revert.pack(side="right", padx=6)
        self.btn_defaults = ttk.Button(foot, text=T["defaults"], command=self._defaults)
        self.btn_defaults.pack(side="right")
        self._set_enabled(False)
        self._draw_dial()
        self._draw_curve()
        # Pencere, içeriğin sığmadığı boyuta küçültülemesin (yoksa sol paneldeki
        # alt düğmeler görünmez olur).
        if self.splash:
            self.splash.lift()  # açılışta yeni kurulan arayüz katmanın altında kalsın
        self.root.update_idletasks()
        # Sekmeler kaydırılabildiği için yüksekliği artık sol panel belirler;
        # yine de ekrandan (görev çubuğu hariç) büyük olmasın.
        _l, top, _r, bottom = work_area()
        self.root.minsize(max(900, self.root.winfo_reqwidth()),
                          min(max(560, self.root.winfo_reqheight()), bottom - top - round(40 * self.ui)))

    # -- kaydırılabilir sekme ---------------------------------------------------
    def _scroll_page(self, parent):
        """Sekme sayfası: içerik sığmazsa sağda kaydırma çubuğu çıkar. Sayfanın
        yüksekliği pencerenin en küçük boyunu artık belirlemez. (dış, iç)
        döndürür; içerik iç çerçeveye yerleşir."""
        outer = ttk.Frame(parent)
        canvas = tk.Canvas(outer, highlightthickness=0, bd=0, bg=self.bg, height=round(260 * self.ui))
        bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        canvas.scrollable = True
        inner = ttk.Frame(canvas, padding=14)
        item = canvas.create_window(0, 0, window=inner, anchor="nw")
        state = {"bar": False}

        def sync(_e=None):
            try:
                want = inner.winfo_reqwidth()
                if int(canvas.cget("width")) != want:
                    canvas.configure(width=want)
                cw, ch = canvas.winfo_width(), canvas.winfo_height()
                canvas.itemconfigure(item, width=max(cw, 1))
                h = inner.winfo_reqheight()
                canvas.configure(scrollregion=(0, 0, cw, max(h, ch)))
                need = h > ch + 1 and ch > 1
                if need != state["bar"]:
                    state["bar"] = need
                    if need:
                        bar.pack(side="right", fill="y", before=canvas)
                    else:
                        bar.pack_forget()
                        canvas.yview_moveto(0)
            except tk.TclError:
                pass
        inner.bind("<Configure>", sync, add="+")
        canvas.bind("<Configure>", sync, add="+")
        return outer, inner

    def _wheel(self, e):
        """Fare tekerleği, imlecin altındaki kaydırılabilir sekmeyi kaydırır."""
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except (tk.TclError, KeyError):
            return
        while w is not None:
            if getattr(w, "scrollable", False):
                top, bottom = w.yview()
                if top > 0 or bottom < 1:
                    w.yview_scroll(-1 if e.delta > 0 else 1, "units")
                return
            w = w.master

    # -- uygulama ayarları sekmesi ----------------------------------------------
    def _build_app_tab(self, page):
        page.columnconfigure(1, weight=1)
        row = 0

        def section(title):
            nonlocal row
            ttk.Label(page, text=title, font=(FONT, 11, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(0 if row == 0 else 14, 6))
            row += 1

        def hint(text):
            nonlocal row
            ttk.Label(page, text=text, foreground=self.muted, wraplength=460, justify="left").grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
            row += 1

        section(T["appearance"])
        ttk.Label(page, text=T["theme"]).grid(row=row, column=0, sticky="w", pady=3)
        themes = ("system", "light", "dark")
        self.theme_box = ttk.Combobox(page, values=T["theme_opts"], state="readonly", width=18)
        self.theme_box.current(themes.index(PREFS["theme"]) if PREFS["theme"] in themes else 0)
        self.theme_box.grid(row=row, column=1, sticky="w", padx=12, pady=3)
        self._dropdown(self.theme_box)
        self.theme_box.bind("<<ComboboxSelected>>",
                            lambda _e: self._set_pref("theme", themes[self.theme_box.current()], rebuild=True))
        row += 1
        ttk.Label(page, text=T["lang"]).grid(row=row, column=0, sticky="w", pady=3)
        langs = ("system", "tr", "en")
        self.lang_box = ttk.Combobox(page, values=T["lang_opts"], state="readonly", width=18)
        self.lang_box.current(langs.index(PREFS["lang"]) if PREFS["lang"] in langs else 0)
        self.lang_box.grid(row=row, column=1, sticky="w", padx=12, pady=3)
        self._dropdown(self.lang_box)
        self.lang_box.bind("<<ComboboxSelected>>",
                           lambda _e: self._set_pref("lang", langs[self.lang_box.current()], rebuild=True))
        row += 1

        section(T["window"])
        self.topmost_var = tk.IntVar(value=1 if PREFS["topmost"] else 0)
        ttk.Checkbutton(page, text=T["topmost"], variable=self.topmost_var,
                        command=lambda: self._set_pref("topmost", bool(self.topmost_var.get()))).grid(
            row=row, column=0, columnspan=3, sticky="w")
        row += 1
        hint(T["topmost_h"])
        self.confirm_var = tk.IntVar(value=1 if PREFS["confirm_close"] else 0)
        ttk.Checkbutton(page, text=T["confirm_close"], variable=self.confirm_var,
                        command=lambda: self._set_pref("confirm_close", bool(self.confirm_var.get()))).grid(
            row=row, column=0, columnspan=3, sticky="w")
        row += 1
        hint(T["confirm_close_h"])
        self.blur_var = tk.IntVar(value=1 if PREFS["blur"] else 0)
        ttk.Checkbutton(page, text=T["blur"], variable=self.blur_var,
                        command=lambda: self._set_pref("blur", bool(self.blur_var.get()))).grid(
            row=row, column=0, columnspan=3, sticky="w")
        row += 1
        hint(T["blur_h"])
        self.tray_var = tk.IntVar(value=1 if PREFS["tray"] else 0)
        ttk.Checkbutton(page, text=T["tray"], variable=self.tray_var,
                        command=lambda: (self._set_pref("tray", bool(self.tray_var.get())), self._update_tray())).grid(
            row=row, column=0, columnspan=3, sticky="w")
        row += 1
        hint(T["tray_h"])

        section(T["battery"])
        self.lowbat_var = tk.IntVar(value=1 if PREFS["low_bat_alert"] else 0)
        ttk.Checkbutton(page, text=T["low_bat_alert"], variable=self.lowbat_var,
                        command=lambda: self._set_pref("low_bat_alert", bool(self.lowbat_var.get()))).grid(
            row=row, column=0, columnspan=3, sticky="w")
        row += 1
        hint(T["low_bat_alert_h"])
        self.demo_var = tk.IntVar(value=1 if self._demo_on() else 0)
        self.demo_switch = ttk.Checkbutton(page, text=T["bat_demo"], variable=self.demo_var, style="Switch.TCheckbutton",
                        command=lambda: self._set_battery_demo(bool(self.demo_var.get())))
        self.demo_switch.grid(row=row, column=0, columnspan=3, sticky="w", pady=(4, 0))
        row += 1
        hint(T["bat_demo_h"])

        section(T["upd_section"])
        self.autoupd_var = tk.IntVar(value=1 if PREFS["auto_update"] else 0)
        ttk.Checkbutton(page, text=T["auto_update"], variable=self.autoupd_var,
                        command=lambda: self._set_pref("auto_update", bool(self.autoupd_var.get()))).grid(
            row=row, column=0, columnspan=3, sticky="w")
        row += 1
        hint(T["auto_update_h"])
        self.btn_check = ttk.Button(page, text=T["check_now"], command=lambda: self._check_updates(manual=True))
        self.btn_check.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 4))
        row += 1
        self.upd_status = ttk.Label(page, text=self.upd_status_text, foreground=self.muted)
        self.upd_status.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 8))
        row += 1

        section(T["sensor"])
        self.btn_import = ttk.Button(page, text=T["import"], command=self._import)
        self.btn_import.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 4))
        row += 1
        hint(T["import_h"])
        self.import_label = ttk.Label(page, text="", foreground=self.muted)
        self.import_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 8))
        row += 1

    # -- profiller ----------------------------------------------------------------
    @staticmethod
    def _cfg_values(cfg):
        merged = dict(cfg.get("s", {}))
        merged["prng"] = cfg.get("prng")
        merged["poff"] = cfg.get("poff")
        keys = {spec[0] for spec in SETTINGS}
        return {k: float(v) for k, v in merged.items() if k in keys and isinstance(v, (int, float))}

    def _current_values(self):
        return {spec[0]: float(self.values[spec[0]]) for spec in SETTINGS if spec[0] in self.values}

    def _profile_on_config(self, cfg):
        """Cihazdan okunan ayarlar geldikçe: varsayılanlarla yeni açılan profil
        bu değerleri alır; bağlantıdaki ilk okumada etkin profil cihaza
        eşitlenir (cihazda başka değerler varsa profil yüklenir)."""
        p = self.store.active
        current = self._cfg_values(cfg)
        if self.prof_capture:
            self.prof_capture = False
            p.values, p.fresh = current, False
            self.store.save()
            self._build_profile_tab()
            return
        if self.prof_synced:
            return
        self.prof_synced = True
        if p.values is None and not p.fresh:
            # İlk profil: cihazdaki mevcut ayarlarla başlar.
            p.values = current
            self.store.save()
            self._build_profile_tab()
        elif p.values is None or not profiles.same_values(p.values, current) or cfg.get("dirty"):
            self._push_profile(p)
        self._update_dirty()

    def _push_profile(self, p):
        """Profilin değerlerini cihaza gönderir ve cihaza kaydeder. Değeri
        olmayan yeni profil cihazın varsayılanlarıyla başlar."""
        if not self.connected:
            self.prof_synced = False  # bağlanınca yüklenir
            return
        if self.send_job is not None:
            self.root.after_cancel(self.send_job)
            self.send_job = None
        self.pending.clear()
        if p.values is None:
            cmds = ["defaults", "save"]
            self.prof_capture = True
        else:
            cmds = [f"{k}={v:g}" for k, v in p.values.items()] + ["save"]
        self.prof_synced = True
        self.link.call(self.link.send_many, cmds, True)

    def _activate_profile(self, pid):
        p = self.store.get(pid)
        if p is None or pid == self.store.active_id:
            self._build_profile_tab()
            return
        if self.connected and self.dirty:
            if self._dialog(T["prof_switch_t"], T["prof_switch_m"].format(name=p.name), "warning",
                            (("btn_cancel", "secondary"), ("btn_switch", "primary"))) != "btn_switch":
                self._build_profile_tab()
                return
        self.store.active_id = pid
        self.store.save()
        self._push_profile(p)
        self._build_profile_tab()
        self._update_dirty()

    def _new_profile(self):
        p = self.store.add(self.store.next_name(T["profile_n"]))
        if p is not None:
            self._activate_profile(p.id)

    def _rename_profile(self, p):
        if p.locked and not self._ask_password(p):
            return

        def check(vals):
            name = vals[0].strip()
            if not name:
                return T["name_empty"]
            if any(o.name.lower() == name.lower() for o in self.store.profiles if o is not p):
                return T["name_taken"]
            return None
        vals = self._ask_fields(T["name_t"], None, ((T["name_field"], None, p.name),), check, "btn_save_name")
        if vals:
            p.name = vals[0].strip()[:32]
            self.store.save()
            self._build_profile_tab()
            self._update_dirty()

    def _delete_profile(self, p):
        if p.locked and not self._ask_password(p):
            return
        if self._dialog(T["prof_del_t"], T["prof_del_m"].format(name=p.name), "warning",
                        (("btn_cancel", "secondary"), ("btn_delete", "primary"))) != "btn_delete":
            return
        was_active = p.id == self.store.active_id
        if self.store.remove(p.id) and was_active:
            self._push_profile(self.store.active)
        self._build_profile_tab()
        self._update_dirty()

    def _toggle_lock(self, p, var):
        if var.get():
            def check(vals):
                if len(vals[0]) < 4:
                    return T["pw_short"]
                if vals[0] != vals[1]:
                    return T["pw_mismatch"]
                return None
            vals = self._ask_fields(T["pw_set_t"], T["pw_set_m"].format(name=p.name),
                                    ((T["pw_field"], "•", ""), (T["pw_again"], "•", "")), check, "btn_lock")
            if vals:
                p.set_password(vals[0])
                self.store.save()
        elif self._ask_password(p):
            p.lock = None
            self.store.save()
        self._build_profile_tab()

    def _ask_password(self, p):
        if not p.locked:
            return True
        vals = self._ask_fields(T["pw_ask_t"], T["pw_ask_m"].format(name=p.name), ((T["pw_field"], "•", ""),),
                                lambda v: None if p.check_password(v[0]) else T["pw_wrong"], "btn_continue")
        return vals is not None

    def _ask_fields(self, title, message, fields, validate, ok_key):
        """Yazı alanlı uyarı. fields: (etiket, gizleme karakteri ya da None,
        başlangıç). validate(değerler) hata metni ya da None döndürür; hata
        varsa pencere açık kalır. Girilen değerleri ya da None döndürür."""
        u = self.ui
        out = {}

        def build(body, finish):
            ttk.Label(body, text=title, font=(FONT, 13, "bold")).grid(row=0, column=0, sticky="w",
                                                                     padx=(0, round(28 * u)))
            r = 1
            if message:
                ttk.Label(body, text=message, foreground=self.muted, wraplength=round(340 * u),
                          justify="left").grid(row=r, column=0, sticky="w", pady=(round(6 * u), 0))
                r += 1
            entries = []
            for label, show, initial in fields:
                ttk.Label(body, text=label).grid(row=r, column=0, sticky="w", pady=(round(12 * u), round(4 * u)))
                e = ttk.Entry(body, show=show or "", width=34)
                e.insert(0, initial)
                e.grid(row=r + 1, column=0, sticky="ew")
                entries.append(e)
                r += 2
            err = ttk.Label(body, text="", foreground=CLOSE_COLOR)
            err.grid(row=r, column=0, sticky="w", pady=(round(8 * u), 0))
            row = ttk.Frame(body)
            row.grid(row=r + 1, column=0, sticky="e", pady=(round(14 * u), 0))

            def submit(_e=None):
                vals = [e.get() for e in entries]
                problem = validate(vals)
                if problem:
                    err.config(text=problem)
                    return
                out["vals"] = vals
                finish(ok_key)
            width = max(len(T["btn_cancel"]), len(T[ok_key])) + 4
            ttk.Button(row, text=T[ok_key], style="Teal.TButton", width=width, command=submit).pack(side="right")
            ttk.Button(row, text=T["btn_cancel"], style="TealOutline.TButton", width=width,
                       command=lambda: finish(None)).pack(side="right", padx=(0, round(8 * u)))
            for e in entries:
                e.bind("<Return>", submit)
            entries[0].after(60, lambda: (entries[0].focus_set(), entries[0].select_range(0, "end")))
            return None
        return out.get("vals") if self._modal(build) == ok_key else None

    def _build_profile_tab(self):
        page = self.prof_page
        if page is None:
            return
        try:
            for w in page.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        u = self.ui
        page.columnconfigure(0, weight=1)
        ttk.Label(page, text=T["prof_section"], font=(FONT, 11, "bold")).grid(row=0, column=0, sticky="w",
                                                                            pady=(0, 6))
        ttk.Label(page, text=T["prof_hint"], foreground=self.muted, wraplength=460, justify="left").grid(
            row=1, column=0, sticky="w", pady=(0, 10))
        self.prof_var = tk.StringVar(value=self.store.active_id)
        r = 2
        for i, p in enumerate(self.store.profiles):
            if i:
                ttk.Separator(page).grid(row=r, column=0, sticky="ew", pady=round(8 * u))
                r += 1
            active = p.id == self.store.active_id
            top = ttk.Frame(page)
            top.grid(row=r, column=0, sticky="ew")
            ttk.Radiobutton(top, text=p.name, value=p.id, variable=self.prof_var,
                            command=lambda pid=p.id: self._activate_profile(pid)).pack(side="left")
            if active:
                ttk.Label(top, text=T["prof_active"], foreground=TEAL, font=(FONT, 9, "bold")).pack(
                    side="left", padx=(10, 0))
            if p.locked:
                ttk.Label(top, text="🔒 " + T["prof_locked"], foreground=self.muted, font=(FONT, 9)).pack(
                    side="left", padx=(10, 0))
            if len(self.store.profiles) > 1:
                ttk.Button(top, text=T["prof_delete"], style="Ghost.TButton", cursor="hand2",
                           command=lambda q=p: self._delete_profile(q)).pack(side="right")
            ttk.Button(top, text=T["prof_rename"], style="Ghost.TButton", cursor="hand2",
                       command=lambda q=p: self._rename_profile(q)).pack(side="right", padx=(0, 4))
            r += 1
            var = tk.IntVar(value=1 if p.locked else 0)
            ttk.Checkbutton(page, text=T["prof_lock"], variable=var,
                            command=lambda q=p, v=var: self._toggle_lock(q, v)).grid(
                row=r, column=0, sticky="w", padx=(round(26 * u), 0), pady=(round(4 * u), 0))
            r += 1
        bottom = ttk.Frame(page)
        bottom.grid(row=r, column=0, sticky="w", pady=(round(16 * u), 0))
        add = ttk.Button(bottom, text="+  " + T["prof_new"], style="TealOutline.TButton", command=self._new_profile)
        add.pack(side="left")
        if not self.store.can_add():
            add.state(["disabled"])
            ttk.Label(bottom, text=T["prof_full"], foreground=self.muted).pack(side="left", padx=(12, 0))
        r += 1
        ttk.Label(page, text=T["prof_lock_h"], foreground=self.muted, wraplength=460, justify="left",
                  font=(FONT, 9)).grid(row=r, column=0, sticky="w", pady=(round(14 * u), 0))
        r += 1
        if not self.connected:
            ttk.Label(page, text=T["prof_offline"], foreground=self.muted, wraplength=460, justify="left",
                      font=(FONT, 9)).grid(row=r, column=0, sticky="w", pady=(round(6 * u), 0))

    # -- açılır liste ------------------------------------------------------------
    def _dropdown(self, box):
        """Combobox'ın kendi açılır listesi Tk'nin eski görünümlü listesidir;
        onun yerine temaya uyan, boşluklu bir liste açar."""
        def open_list(_e=None):
            if str(box.cget("state")) == "disabled":
                return "break"
            if self.drop_win is not None and self.drop_box is box:
                self._close_dropdown()
                return "break"
            self._close_dropdown()
            self._close_help()
            bg = "#2b2b2b" if self.dark else "#ffffff"
            hover = "#383838" if self.dark else "#f0f0f0"
            border = "#4a4a4a" if self.dark else "#d1d5db"
            win = tk.Toplevel(self.root)
            win.withdraw()
            win.overrideredirect(True)
            win.transient(self.root)
            win.configure(bg=border)
            body = tk.Frame(win, bg=bg, padx=round(4 * self.ui), pady=round(4 * self.ui))
            body.pack(fill="both", expand=True, padx=1, pady=1)
            current = box.current()
            for idx, text in enumerate(box.cget("values")):
                sel = idx == current
                row = tk.Frame(body, bg=TEAL if sel else bg, cursor="hand2")
                row.pack(fill="x")
                lbl = tk.Label(row, text=text, bg=row.cget("bg"), fg="#ffffff" if sel else self.fg,
                               font=(FONT, 10, "bold" if sel else "normal"), anchor="w",
                               padx=round(10 * self.ui), pady=round(5 * self.ui))
                lbl.pack(fill="x")
                def choose(_e, i=idx):
                    self._close_dropdown()
                    if box.current() != i:
                        box.current(i)
                        box.event_generate("<<ComboboxSelected>>")
                def enter(_e, r=row, l=lbl, s=sel):
                    if not s:
                        r.config(bg=hover); l.config(bg=hover)
                def leave(_e, r=row, l=lbl, s=sel):
                    if not s:
                        r.config(bg=bg); l.config(bg=bg)
                for w in (row, lbl):
                    w.bind("<Button-1>", choose)
                    w.bind("<Enter>", enter)
                    w.bind("<Leave>", leave)
                    w.dropdown_item = True
            win.update_idletasks()
            w = max(box.winfo_width(), win.winfo_reqwidth())
            h = win.winfo_reqheight()
            x, y = box.winfo_rootx(), box.winfo_rooty() + box.winfo_height() + 2
            if y + h > win.winfo_screenheight() - 40:
                y = box.winfo_rooty() - h - 2
            win.attributes("-topmost", True)
            win.geometry(f"{w}x{h}+{x}+{y}")
            win.deiconify()
            win.lift()
            self.drop_win, self.drop_box = win, box
            return "break"
        box.bind("<Button-1>", open_list)
        for key in ("<Down>", "<Alt-Down>", "<space>", "<Return>"):
            box.bind(key, open_list)
        box.dropdown_field = True

    def _close_dropdown(self):
        if self.drop_win is not None:
            try:
                self.drop_win.destroy()
            except tk.TclError:
                pass
        self.drop_win = self.drop_box = None

    # -- uyarı pencereleri ----------------------------------------------------------
    # -- uyarı pencereleri --------------------------------------------------------
    def _modal(self, build, closable=True, busy=False):
        """Modern uyarı kabuğu: Windows başlık çubuğu yerine kenarlıksız, ince
        çerçeveli ve (Windows 11'de) yuvarlak köşeli bir kart; sağ üstte ✕,
        açılırken kısa bir belirme ve kayma. build(body, finish) içeriği kurar,
        varsa (düğme, anahtar) olarak varsayılan düğmeyi döndürür. Seçilen
        anahtarı döndürür (Esc/✕ = None). busy=True ise beklemeden pencereyi
        döndürür (dışarıdan destroy ile kapatılır)."""
        self._close_help()
        self._close_dropdown()
        u = self.ui
        overlay = self._blur_overlay() if PREFS["blur"] else None
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.transient(self.root)
        win.bind("<Destroy>", lambda e: self._drop_overlay(overlay) if e.widget is win else None, add="+")
        border = "#3a3a3a" if self.dark else "#d9dde3"
        win.configure(bg=border)
        card = tk.Frame(win, bg=self.bg)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        body = ttk.Frame(card, padding=(round(26 * u), round(24 * u), round(26 * u), round(22 * u)))
        body.pack(fill="both", expand=True)
        result = {"value": None}

        def finish(value):
            result["value"] = value
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        primary = build(body, finish)
        if closable and not busy:
            # Pencerenin kendi düğmeleriyle aynı çizim: kenar yumuşatmalı ✕,
            # üzerine gelince yuvarlak köşeli zemin.
            size = 28
            x = tk.Canvas(card, width=round(size * u), height=round(size * u), highlightthickness=0,
                          bg=self.bg, cursor="hand2")

            def paint(hover):
                img = AAImage(size, size, u, self.bg)
                if hover:
                    img.rrect(0, 0, size, size, 6, tint(CLOSE_COLOR, self.bg, HOVER_TINT[self.dark]))
                color = CLOSE_COLOR if hover else self.muted
                img.line([(9.5, 9.5), (18.5, 18.5)], color, 1.3)
                img.line([(18.5, 9.5), (9.5, 18.5)], color, 1.3)
                x.photo = img.photo()
                x.delete("all")
                x.create_image(0, 0, image=x.photo, anchor="nw")
            paint(False)
            x.place(relx=1.0, x=-round(10 * u), y=round(10 * u), anchor="ne")
            x.bind("<Enter>", lambda _e: paint(True))
            x.bind("<Leave>", lambda _e: paint(False))

            def release(e):
                if 0 <= e.x < x.winfo_width() and 0 <= e.y < x.winfo_height():
                    finish(None)
            x.bind("<ButtonRelease-1>", release)

        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x0 = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y0 = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 3
        x0, y0 = max(0, x0), max(0, y0)
        rise = round(10 * u)
        win.geometry(f"{w}x{h}+{x0}+{y0 + rise}")
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = u32.GetParent(win.winfo_id()) or win.winfo_id()
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            # Kenarlıksız pencerede Tk'nın transient bağı Windows'a ulaşmıyor:
            # ana pencere "her zaman üstte" iken uyarının önüne geçip tıklamayı
            # yutuyordu. Sahibi ana pencere yapılınca uyarı hep onun üstünde
            # kalır (başka uygulamaların üstünde değil).
            owner = u32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            u32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            u32.SetWindowLongPtrW(hwnd, -8, owner)  # GWLP_HWNDPARENT
        except Exception:
            pass
        try:
            win.attributes("-alpha", 0.0)
            # Ana pencere "her zaman üstte" ise uyarı da öyle olmalı; yoksa
            # sonradan açılan uyarı onun altında kalır.
            win.attributes("-topmost", bool(self.root.attributes("-topmost")))
        except tk.TclError:
            pass
        win.deiconify()
        win.lift()
        win.focus_force()
        win.grab_set()

        def appear(i, steps=8):
            try:
                t = i / steps
                ease = 1 - (1 - t) ** 3
                win.attributes("-alpha", ease)
                win.geometry(f"+{x0}+{y0 + round(rise * (1 - ease))}")
                if i < steps:
                    win.after(15, appear, i + 1)
            except tk.TclError:
                pass
        appear(1)

        if busy:
            return win
        win.bind("<Escape>", lambda _e: finish(None))
        if primary:
            primary[0].focus_set()
            win.bind("<Return>", lambda _e: finish(primary[1]))
        self.root.wait_window(win)
        return result["value"]

    def _dialog(self, title, message, kind="info", buttons=(("btn_ok", "primary"),), busy=False):
        """Temaya uygun uyarı. buttons: (metin anahtarı, "primary" ya da
        "secondary"). Basılan düğmenin anahtarını döndürür (Esc/kapatma = None).
        busy=True ise beklemeden pencereyi döndürür."""
        u = self.ui

        def build(body, finish):
            icon = tk.Canvas(body, width=round(44 * u), height=round(44 * u), highlightthickness=0, bg=self.bg)
            icon.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, round(16 * u)))
            ttk.Label(body, text=title, font=(FONT, 13, "bold"), wraplength=round(330 * u),
                      justify="left").grid(row=0, column=1, sticky="w", padx=(0, round(22 * u)))
            ttk.Label(body, text=message, foreground=self.muted, wraplength=round(340 * u),
                      justify="left").grid(row=1, column=1, sticky="w", pady=(round(6 * u), 0))
            if kind == "busy":
                self._spin(icon, 0)
            else:
                self._dialog_icon(icon, kind)
            primary = None
            if buttons:
                row = ttk.Frame(body)
                row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(round(22 * u), 0))
                # Bütün düğmeler aynı boyda ve aynı genişlikte olsun.
                width = max(len(T[key]) for key, _ in buttons) + 4
                for key, role in reversed(buttons):
                    b = ttk.Button(row, text=T[key], width=width,
                                   style="Teal.TButton" if role == "primary" else "TealOutline.TButton",
                                   command=lambda k=key: finish(k))
                    b.pack(side="right", padx=(round(8 * u), 0))
                    if role == "primary":
                        primary = (b, key)
            return primary
        return self._modal(build, closable=bool(buttons), busy=busy)

    def _tab_icon(self, kind):
        """Sekme simgeleri: 16 px, saydam zemin, aynı çizgi kalınlığı (fonta bağlı değil)."""
        color = self.fg
        n = max(1, round(16 * self.ui))
        k = n * 4 / 16
        im = Image.new("RGBA", (n * 4, n * 4), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        w = max(1, round(1.5 * k))

        def line(pts):
            d.line([(x * k, y * k) for x, y in pts], fill=color, width=w, joint="curve")
            r = w / 2
            for x, y in (pts[0], pts[-1]):
                d.ellipse((x * k - r, y * k - r, x * k + r, y * k + r), fill=color)

        if kind == "tab_yaw":      # yatay çift ok
            line([(2.5, 8), (13.5, 8)])
            line([(5, 5.5), (2.5, 8), (5, 10.5)])
            line([(11, 5.5), (13.5, 8), (11, 10.5)])
        elif kind == "tab_pitch":  # dikey çift ok
            line([(8, 2.5), (8, 13.5)])
            line([(5.5, 5), (8, 2.5), (10.5, 5)])
            line([(5.5, 11), (8, 13.5), (10.5, 11)])
        elif kind == "tab_chair":  # dönen ofis koltuğu: sırtlık, oturak, orta ayak, taban
            d.rounded_rectangle((5 * k, 1.8 * k, 11 * k, 7.2 * k), radius=1.6 * k, outline=color, width=w)
            line([(3.5, 9.5), (12.5, 9.5)])
            line([(8, 9.5), (8, 13)])
            line([(4.8, 13.6), (11.2, 13.6)])
        elif kind == "tab_profile":  # kişi: baş ve omuzlar
            r = 2.8 * k
            d.ellipse((8 * k - r, 5.2 * k - r, 8 * k + r, 5.2 * k + r), outline=color, width=w)
            d.arc((2.8 * k, 9.6 * k, 13.2 * k, 19.6 * k), 180, 360, fill=color, width=w)
        elif kind == "tab_smooth":  # yumuşak dalga
            pts = [(2 + i * 12 / 24, 8 - 3.2 * math.sin(i / 24 * 2 * math.pi)) for i in range(25)]
            line(pts)
        else:                      # ayarlar: üç kaydırıcı
            for y, kx in ((4, 10.5), (8, 5.5), (12, 9)):
                line([(2.5, y), (13.5, y)])
                r = 1.9 * k
                d.ellipse((kx * k - r, y * k - r, kx * k + r, y * k + r), fill=color)
                r2 = 0.9 * k
                d.ellipse((kx * k - r2, y * k - r2, kx * k + r2, y * k + r2), fill=(0, 0, 0, 0))
        return ImageTk.PhotoImage(im.resize((n, n), Image.LANCZOS))

    def _info_icon(self):
        """Hakkında düğmesindeki küçük ⓘ simgesi (çizilmiş: her fontta aynı görünür)."""
        # Saydam zemin: üzerine gelince düğmenin hafif zemini simgenin arkasında da görünsün.
        color = "#9ca3af" if self.dark else "#6b7280"
        n = max(1, round(16 * self.ui))
        k = n * 4 / 16
        im = Image.new("RGBA", (n * 4, n * 4), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((1.4 * k, 1.4 * k, 14.6 * k, 14.6 * k), outline=color, width=max(1, round(1.4 * k)))
        d.rounded_rectangle((7.2 * k, 6.8 * k, 8.8 * k, 11.8 * k), radius=0.8 * k, fill=color)
        d.ellipse((7.05 * k, 4.0 * k, 8.95 * k, 5.9 * k), fill=color)
        return ImageTk.PhotoImage(im.resize((n, n), Image.LANCZOS))

    def _about(self):
        """Hakkında: ortada logo ve marka yazısı, altında yuvarlak köşeli bir
        panelde cihaz adı, firmware ve uygulama sürümü."""
        u = self.ui
        cfg = self.last_cfg or {}
        rows = ((T["device_name"], cfg.get("name") or "–"),
                (T["firmware"], cfg.get("fw") or "–"),
                (T["app_version"], APP_VERSION))

        def build(body, finish):
            body.configure(padding=(round(28 * u), round(26 * u), round(28 * u), round(24 * u)))
            logo = tk.Canvas(body, width=round(64 * u), height=round(64 * u), highlightthickness=0, bg=self.bg)
            logo.photo = ImageTk.PhotoImage(scaled_icon(round(64 * u)))
            logo.create_image(0, 0, image=logo.photo, anchor="nw")
            logo.pack()
            ttk.Label(body, text="Lookie", font=BRAND_FONT).pack(pady=(round(10 * u), 0))
            ttk.Label(body, text=T["about_t"], foreground=self.muted).pack(pady=(round(2 * u), round(16 * u)))

            # Bilgi paneli: yumuşak zeminli, satırlar ince çizgilerle ayrılmış.
            pw, rh = 300, 38
            ph = rh * len(rows)
            panel_bg = "#262626" if self.dark else "#f1f3f5"
            line = "#333333" if self.dark else "#e3e6ea"
            img = AAImage(pw, ph, u, self.bg)
            img.rrect(0, 0, pw, ph, 10, panel_bg)
            for i in range(1, len(rows)):
                img.line([(14, i * rh), (pw - 14, i * rh)], line, 1, caps=False)
            panel = tk.Canvas(body, width=round(pw * u), height=round(ph * u), highlightthickness=0, bg=self.bg)
            panel.photo = img.photo()
            panel.create_image(0, 0, image=panel.photo, anchor="nw")
            for i, (label, value) in enumerate(rows):
                cy = (i * rh + rh / 2) * u
                panel.create_text(16 * u, cy, text=label, anchor="w", fill=self.muted, font=(FONT, 10))
                panel.create_text((pw - 16) * u, cy, text=value, anchor="e", fill=self.fg, font=(FONT_SEMI, 10))
            panel.pack()

            ok = ttk.Button(body, text=T["btn_ok"], style="Teal.TButton", command=lambda: finish("btn_ok"))
            ok.pack(fill="x", pady=(round(20 * u), 0))
            return ok, "btn_ok"
        self._modal(build)

    def _dialog_icon(self, canvas, kind):
        """Yumuşak renkli daire üstünde renkli işaret (düz dolgu yerine)."""
        color = {"warning": PITCH_COLOR, "error": "#EF4444"}.get(kind, TEAL)
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        br, bg_, bb = (int(self.bg[i:i + 2], 16) for i in (1, 3, 5))
        k = 0.22 if self.dark else 0.16  # dairenin renk yoğunluğu
        tint = "#%02x%02x%02x" % (round(br + (r - br) * k), round(bg_ + (g - bg_) * k), round(bb + (b - bb) * k))
        img = AAImage(44, 44, self.ui, self.bg)
        img.circle(22, 22, 21, fill=tint)
        if kind == "success":
            img.line([(14, 22.5), (19.5, 28), (30, 16.5)], color, 3.2)
        elif kind in ("warning", "error"):
            img.line([(22, 13), (22, 25)], color, 3.4)
            img.circle(22, 31, 2.2, fill=color)
        canvas.photo = img.photo()
        canvas.create_image(0, 0, image=canvas.photo, anchor="nw")
        if kind not in ("success", "warning", "error"):  # soru / bilgi
            canvas.create_text(22 * self.ui, 22.5 * self.ui, text="?" if kind == "question" else "i",
                               fill=color, font=(FONT, 15, "bold"))

    def _spin(self, canvas, angle):
        # Bekleme simgesi: halka üzerinde dönen turkuaz yay.
        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        img = AAImage(44, 44, self.ui, self.bg)
        img.circle(22, 22, 17, outline=self.grid_c, width=4)
        k = img.k
        img.d.arc((5 * k, 5 * k, 39 * k, 39 * k), start=angle, end=angle + 100, fill=TEAL, width=round(4 * k))
        canvas.photo = img.photo()
        canvas.delete("all")
        canvas.create_image(0, 0, image=canvas.photo, anchor="nw")
        canvas.after(40, lambda: self._spin(canvas, (angle + 12) % 360))

    def _title_bar_of(self, win, dark):
        try:
            import ctypes
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            on = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
        except Exception:
            pass

    # -- gyro kalibrasyonu --------------------------------------------------------
    def _gyrocal(self):
        if self._dialog(T["gyro_q_t"], T["gyro_q"], "question",
                        (("btn_cancel", "secondary"), ("btn_start", "primary"))) != "btn_start":
            return
        self.gyro_before = (self.last_cfg or {}).get("gcal")
        self.gyro_started = __import__("time").monotonic()
        self.gyro_win = self._dialog(T["gyro_run_t"], T["gyro_run"], "busy", buttons=(), busy=True)
        self.link.call(self.link.send, "gyrocal")
        self.root.after(1200, self._gyro_poll)

    def _gyro_poll(self):
        # Cihaz kalibrasyon boyunca ana döngüde bekler ama Bluetooth okumalarına
        # cevap vermeye devam eder; bitince "gcal" sayacı artar.
        if self.gyro_win is None:
            return
        if __import__("time").monotonic() - self.gyro_started > 20:
            self._gyro_finish(None)
            return
        self.link.call(self.link.read_config)
        self.root.after(700, self._gyro_poll)

    def _gyro_check(self, cfg):
        if self.gyro_win is None:
            return
        if "gcal" not in cfg:
            # Eski firmware sonucu bildirmez: telemetri geri gelince bitti say.
            if self.tel_age == 0 and __import__("time").monotonic() - self.gyro_started > 2.5:
                self._gyro_finish("old")
            return
        if cfg["gcal"] != self.gyro_before:
            self._gyro_finish("ok" if cfg.get("gok") else "moved")

    def _gyro_finish(self, outcome):
        win, self.gyro_win = self.gyro_win, None
        if win is not None:
            try:
                win.grab_release()
                win.destroy()
            except tk.TclError:
                pass
        self._set_status("connected" if self.connected else self.status_key)
        if outcome == "ok":
            self._dialog(T["gyro_ok_t"], T["gyro_ok"], "success")
        elif outcome == "moved":
            if self._dialog(T["gyro_moved_t"], T["gyro_moved"], "warning",
                            (("btn_ok", "secondary"), ("btn_retry", "primary"))) == "btn_retry":
                self._gyrocal()
        elif outcome == "old":
            self._dialog(T["gyro_ok_t"], T["gyro_done"], "success")
        else:
            self._dialog(T["gyro_timeout_t"], T["gyro_timeout"], "error")

    def _blur_overlay(self):
        """Uyarı açıkken uygulamanın üstüne, pencerenin bulanıklaştırılmış ve
        hafifçe karartılmış bir görüntüsünü koyar. Ayrı bir pencere değil, ana
        pencerenin içinde her şeyin üstüne yerleşen bir etiket: ayrı pencere,
        uygulama öndeyken ana pencerenin arkasında kalıyordu."""
        try:
            root = self.root
            root.update_idletasks()
            x, y, w, h = root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()
            shot = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).convert("RGB")
            # Küçültüp bulanıklaştırmak hem hızlı hem yumuşak sonuç verir.
            small = shot.resize((max(1, w // 4), max(1, h // 4)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.6))
            img = small.resize((w, h), Image.BICUBIC)
            img = Image.blend(img, Image.new("RGB", img.size, self.bg), 0.25)
            ov = tk.Label(root, borderwidth=0, highlightthickness=0)
            ov.photo = ImageTk.PhotoImage(img)
            ov.blurred, ov.sharp = img, shot  # kaldırırken netleştirmek için
            ov.configure(image=ov.photo)
            ov.place(x=0, y=0, relwidth=1, relheight=1)
            ov.lift()
            self.overlays.append(ov)
            return ov
        except Exception:
            log_error("blur overlay")
            return None

    def _drop_overlay(self, ov):
        """Bulanık katmanı kaldırır. Katman doğrudan silinirse altındaki
        bölümler (kadran, sekmeler, düğmeler) Windows'ta sırayla yeniden
        çizilir ve görüntü parça parça netleşir. Bunun yerine katmanın kendisi
        kısa sürede pencerenin net görüntüsüne geçer; katman ancak ondan sonra
        kalkar ve altındaki çizimler net görüntünün üstüne fark edilmeden gelir."""
        if ov is None:
            return
        steps = 6

        def step(i):
            try:
                if i < steps:
                    ov.photo.paste(Image.blend(ov.blurred, ov.sharp, (i + 1) / steps))
                    ov.after(16, step, i + 1)
                    return
                ov.destroy()
            except (tk.TclError, AttributeError, ValueError):
                try:
                    ov.destroy()
                except tk.TclError:
                    pass
            if ov in self.overlays:
                self.overlays.remove(ov)

        step(0)

    def _set_pref(self, key, value, rebuild=False):
        if PREFS.get(key) == value:
            return
        PREFS[key] = value
        save_prefs(PREFS)
        if key == "topmost":
            self.root.attributes("-topmost", bool(value))
        if key == "lang":
            set_language(resolve_language(value))
            self.root.title(T["title"])
        if rebuild:
            # Tema ve dil bütün bileşenleri etkiler: arayüzü yeniden kur.
            self.root.after(10, self._rebuild)

    def _rebuild(self):
        self._close_help()
        self._close_dropdown()
        tab = self.tabs.index("current") if hasattr(self, "tabs") else 0
        self.outer.destroy()
        self.widgets = {}
        if hasattr(self, "help_rings"):
            del self.help_rings
        self._apply_theme()
        self._build()
        if self.last_cfg:
            self._apply_config(self.last_cfg)
        self._set_enabled(self.connected)
        self._set_status(self.status_key)
        self._draw_battery()
        if self.tel is not None:
            self._show_telemetry(self.tel)
        self.tabs.select(tab)

    def _import(self):
        if not self.connected:
            self.import_label.config(text=T["not_connected"])
            return
        # Bekleyen gönderimleri iptal et: cihazdaki değerler esas alınır.
        if self.send_job is not None:
            self.root.after_cancel(self.send_job)
            self.send_job = None
        self.pending.clear()
        self.import_pending = True
        self.link.call(self.link.read_config)

    def _legend(self, parent, color, text):
        c = tk.Canvas(parent, width=round(18 * self.ui), height=round(10 * self.ui),
                      highlightthickness=0, bg=self.bg)
        img = AAImage(18, 10, self.ui, self.bg)
        img.line([(3, 5), (15, 5)], color, 3)
        c.img = img.photo()
        c.create_image(0, 0, image=c.img, anchor="nw")
        c.pack(side="left")
        ttk.Label(parent, text=text, foreground=self.muted).pack(side="left", padx=(2, 12))

    def _setting_row(self, page, row, key, tab, lo, hi, step, scale, unit, decimals):
        if scale == "bool":
            var = tk.IntVar(value=0)
            head = ttk.Frame(page)
            head.grid(row=row, column=0, columnspan=3, sticky="w", pady=(4, 0))
            ttk.Checkbutton(head, text=T[key], variable=var,
                            command=lambda k=key, v=var: self._changed(k, float(v.get()))).pack(side="left")
            self._help_icon(head, key).pack(side="left", padx=(6, 0))
            ttk.Label(page, text=T[key + "_h"], foreground=self.muted, wraplength=460,
                      justify="left").grid(row=row + 1, column=0, columnspan=3, sticky="w", pady=(0, 10))
            self.widgets[key] = (var, None, None, scale, lo, hi, step, unit, decimals)
            return row + 2
        head = ttk.Frame(page)
        head.grid(row=row, column=0, sticky="w", pady=(4, 0))
        ttk.Label(head, text=T[key]).pack(side="left")
        self._help_icon(head, key).pack(side="left", padx=(6, 0))
        var = tk.DoubleVar(value=0)
        if scale == "log":
            s = ttk.Scale(page, from_=math.log10(lo), to=math.log10(hi), variable=var,
                          command=lambda _=None, k=key: self._slid(k))
        else:
            s = ttk.Scale(page, from_=lo, to=hi, variable=var, command=lambda _=None, k=key: self._slid(k))
        s.grid(row=row, column=1, sticky="ew", padx=12, pady=(4, 0))
        val = ttk.Label(page, text="–", width=10, anchor="e", font=(FONT, 10, "bold"))
        val.grid(row=row, column=2, sticky="e", pady=(4, 0))
        ttk.Label(page, text=T[key + "_h"], foreground=self.muted, wraplength=460,
                  justify="left").grid(row=row + 1, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.widgets[key] = (var, val, s, scale, lo, hi, step, unit, decimals)
        return row + 2

    # -- yardım penceresi ----------------------------------------------------
    def _help_icon(self, parent, key):
        """Ayar adının yanındaki "?" simgesi; tıklayınca ayrıntılı açıklama açılır."""
        u = self.ui
        c = tk.Canvas(parent, width=round(18 * u), height=round(18 * u), highlightthickness=0,
                      bg=self.bg, cursor="hand2")
        if not hasattr(self, "help_rings"):
            self.help_rings = {}
            for color in (self.muted, TEAL):
                img = AAImage(18, 18, u, self.bg)
                img.circle(9, 9, 7, outline=color, width=1.4)
                self.help_rings[color] = img.photo()
        ring = c.create_image(0, 0, image=self.help_rings[self.muted], anchor="nw")
        mark = c.create_text(9 * u, 9.5 * u, text="?", fill=self.muted, font=(FONT, 8, "bold"))
        def paint(color):
            c.itemconfig(ring, image=self.help_rings[color])
            c.itemconfig(mark, fill=color)
        c.bind("<Enter>", lambda _e: paint(TEAL))
        c.bind("<Leave>", lambda _e: paint(TEAL if self.help_key == key else self.muted))
        c.bind("<Button-1>", lambda _e: self._toggle_help(key, c))
        c.help_icon = True
        return c

    def _toggle_help(self, key, anchor):
        if self.help_key == key:
            self._close_help()
            return
        self._close_help()
        bg = "#2b2b2b" if self.dark else "#ffffff"
        border = "#4a4a4a" if self.dark else "#d1d5db"
        win = tk.Toplevel(self.root)
        win.withdraw()  # içerik ve konum hazır olunca göster
        win.overrideredirect(True)
        win.transient(self.root)
        win.configure(bg=border)
        body = tk.Frame(win, bg=bg, padx=14, pady=12)
        body.pack(padx=1, pady=1)
        tk.Label(body, text=T[key], bg=bg, fg=self.fg, font=(FONT, 10, "bold"),
                 anchor="w", justify="left").pack(fill="x")
        tk.Label(body, text=HELP.get(key, T.get(key + "_h", "")), bg=bg, fg=self.fg,
                 font=(FONT, 9), wraplength=360, justify="left", anchor="w").pack(fill="x", pady=(6, 0))
        win.update_idletasks()
        # İkonun altına yerleştir; pencereden ve ekrandan taşmasın.
        x = anchor.winfo_rootx() - 12
        y = anchor.winfo_rooty() + anchor.winfo_height() + 6
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        right = min(self.root.winfo_rootx() + self.root.winfo_width(), win.winfo_screenwidth()) - 8
        x = max(8, min(x, right - w))
        if y + h > win.winfo_screenheight() - 40:
            y = anchor.winfo_rooty() - h - 6
        # Kenarlıksız pencere Windows'ta ana pencerenin arkasında kalabiliyor.
        win.attributes("-topmost", True)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.deiconify()
        win.lift()
        self.help_win, self.help_key, self.help_anchor = win, key, anchor

    def _close_help(self):
        if self.help_win is not None:
            try:
                self.help_win.destroy()
            except tk.TclError:
                pass
            anchor = getattr(self, "help_anchor", None)
            self.help_win = self.help_key = None
            if anchor is not None:
                try:
                    anchor.event_generate("<Leave>")
                except tk.TclError:
                    pass

    def _click_anywhere(self, event):
        # Açılır liste ya da yardım penceresi açıkken başka bir yere tıklanınca
        # kapat (kendi alanları hariç).
        w = event.widget
        if self.drop_win is not None and not getattr(w, "dropdown_item", False) \
                and not getattr(w, "dropdown_field", False):
            self._close_dropdown()
        if self.help_win is None:
            return
        if getattr(w, "help_icon", False):
            return
        try:
            if str(w).startswith(str(self.help_win)):
                return
        except tk.TclError:
            pass
        self._close_help()

    # -- değer işleme -------------------------------------------------------
    def _slider_value(self, key):
        var, _, _, scale, lo, hi, step, _, _ = self.widgets[key]
        x = var.get()
        v = 10 ** x if scale == "log" else x
        if scale == "log":
            v = round(v, 2 if v < 100 else 0)
        elif step:
            v = round(round(v / step) * step, 6)
        return min(max(v, lo), hi)

    def _fmt(self, key, v):
        _, _, _, _, _, _, _, unit, decimals = self.widgets[key]
        text = f"{v:.{decimals}f}"
        if unit == "deg":
            return text + T["deg"]
        return f"{text} {T[unit]}" if unit else text

    def _slid(self, key):
        if self.suppress:
            return
        v = self._slider_value(key)
        self.widgets[key][1].config(text=self._fmt(key, v))
        self._changed(key, v)

    def _changed(self, key, v):
        if self.suppress or self.values.get(key) == v:
            return
        self.values[key] = v
        self.pending[key] = v
        self.dirty = True
        self._update_dirty()
        if key in ("ylin", "yblend", "ygain"):
            self._draw_curve()
        if self.send_job is None:
            self.send_job = self.root.after(120, self._flush)

    def _flush(self):
        self.send_job = None
        for k, v in list(self.pending.items()):
            self.link.call(self.link.send, f"{k}={v:g}")
        self.pending.clear()

    def _apply_config(self, cfg):
        self.last_cfg = cfg
        self.suppress = True
        try:
            merged = dict(cfg.get("s", {}))
            merged["prng"] = cfg.get("prng")
            merged["poff"] = cfg.get("poff")
            for key, (var, val, _, scale, *_rest) in self.widgets.items():
                v = merged.get(key)
                if v is None:
                    continue
                self.values[key] = v
                if scale == "bool":
                    var.set(int(v))
                else:
                    var.set(math.log10(max(v, 1e-6)) if scale == "log" else v)
                    val.config(text=self._fmt(key, v))
            self.yaw_range = float(cfg.get("yrange", 180))
            self.dirty = bool(cfg.get("dirty", 0))
        finally:
            self.suppress = False
        self._update_dirty()
        self._draw_curve()

    def _update_dirty(self):
        text = ""
        if self.connected:
            text = f"{self.store.active.name} · " + (T["unsaved"] if self.dirty else T["saved"])
        self.dirty_label.config(text=text)
        self.btn_save.state(["!disabled"] if (self.connected and self.dirty) else ["disabled"])

    def _set_enabled(self, on):
        for w in (self.btn_recenter, self.btn_gyro, self.btn_revert, self.btn_defaults, self.btn_import):
            w.state(["!disabled"] if on else ["disabled"])
        for key, (var, val, s, scale, *_rest) in self.widgets.items():
            if s is not None:
                s.state(["!disabled"] if on else ["disabled"])
        self._update_dirty()

    # -- komutlar -----------------------------------------------------------
    def _save(self):
        """Cihaza kaydeder ve değerleri etkin profile yazar (şifreliyse sorar)."""
        p = self.store.active
        if p.locked and not self._ask_password(p):
            return
        self._flush()
        self.link.call(self.link.send, "save", True)
        p.values = self._current_values()
        p.fresh = False
        self.store.save()

    def _defaults(self):
        if self._dialog(T["defaults_q_t"], T["defaults_q"], "question",
                        (("btn_cancel", "secondary"), ("btn_reset", "primary"))) == "btn_reset":
            self.link.call(self.link.send, "defaults", True)

    def _on_close(self):
        """Çıkmadan önce sorar. Kaydedilmemiş ayar varsa (ve bu uyarı açıksa)
        onun uyarısı, yoksa çıkış onayı gösterilir; ikisi art arda çıkmaz."""
        if self._hidden():
            self._show_window()  # soru penceresi görünsün (tepsiden çıkışta)
        if PREFS["confirm_close"] and self.connected and self.dirty:
            ask = (T["close_q_t"], T["close_q"], "warning", "btn_quit")
        else:
            ask = (T["quit_q_t"], T["quit_q"], "question", "btn_exit")
        if self._dialog(ask[0], ask[1], ask[2], (("btn_cancel", "secondary"), (ask[3], "primary"))) != ask[3]:
            return
        self._shutdown()

    def _shutdown(self, relaunch=False):
        if self.pending_app_update:
            try:
                updater.install_app(self.pending_app_update, relaunch=relaunch)
            except Exception:
                log_error("install app")
        self.link.stop_flag = True
        if self.tray:
            self.tray.stop()
            self.tray = None
        self.closed = True
        self.root.destroy()

    # -- güncellemeler ----------------------------------------------------------
    # Yayınlar GitHub Releases'tan okunur (bkz. updater.py). Akış: denetim ->
    # teklif (öndeyse uyarı, değilse bildirim) -> indirme (gizlenebilir
    # ilerleme penceresi) -> firmware ise cihaza Bluetooth ile yükleme,
    # uygulama ise yeniden başlatıp exe'yi değiştirme.
    def _check_updates(self, manual):
        if not manual:
            # Otomatik denetim 6 saatte bir tekrarlar (ayar kapalıysa atlanır).
            self.root.after(6 * 3600 * 1000, lambda: self._check_updates(manual=False))
            if not PREFS["auto_update"]:
                return
        else:
            # Elle denetimde daha önce "Şimdilik atla" denenler yeniden sorulur.
            self.upd_asked.clear()
        self._set_upd_status(T["upd_checking"])
        if hasattr(self, "btn_check"):
            try:
                self.btn_check.state(["disabled"])
            except tk.TclError:
                pass

        def work():
            try:
                self.events.put(("upd_manifest", (updater.fetch_manifest(), manual)))
            except Exception as e:
                self.events.put(("upd_error", (str(e) or e.__class__.__name__, manual)))
        threading.Thread(target=work, daemon=True).start()

    def _set_upd_status(self, text):
        self.upd_status_text = text
        try:
            self.upd_status.config(text=text)
        except (AttributeError, tk.TclError):
            pass

    def _on_update_event(self, kind, data):
        import time
        if kind in ("upd_manifest", "upd_error"):
            try:
                self.btn_check.state(["!disabled"])
            except (AttributeError, tk.TclError):
                pass
        if kind == "upd_manifest":
            manifest, manual = data
            self.upd_manifest = manifest
            found = bool(self._available_updates())
            self._set_upd_status(T["upd_found" if found else "upd_uptodate"].format(time=time.strftime("%H:%M")))
            self.root.after(0, lambda: self._offer_updates(manual))
        elif kind == "upd_error":
            err, manual = data
            self._set_upd_status(T["upd_error"].format(err=err))
            if manual:
                self.root.after(0, lambda: self._dialog(T["dl_failed_t"], T["upd_error"].format(err=err), "error"))
        elif kind == "upd_progress":
            k, done, total = data
            self._progress("download", done, total)
        elif kind == "upd_done":
            k, path, info = data
            self._downloaded(k, path, info)
        elif kind == "upd_failed":
            k, err = data
            self._update_failed(err)
        elif kind == "ota_progress":
            sent, total = data
            self._progress("flash", sent, total)
        elif kind == "ota_done":
            info = (self.upd_busy or {}).get("info") or {}
            self._finish_update()
            msg = T["fw_done"].format(v=info.get("version", "?"))
            self.root.after(0, lambda: self._tell(T["fw_done_t"], msg, "success"))
        elif kind == "ota_failed":
            self._update_failed(data)

    def _available_updates(self):
        """[(tür, bilgi, uyarı anahtarı)] — yayındaki sürümler kullanılanlardan yeniyse."""
        m = self.upd_manifest or {}
        out = []
        cfg = self.last_cfg or {}
        fw = m.get("firmware")
        if fw and cfg.get("fw") and updater.is_newer(fw["version"], cfg["fw"]):
            out.append(("firmware", fw, "fw_avail" if cfg.get("ota") else "fw_need_usb"))
        app = m.get("app")
        if app and updater.is_newer(app["version"], APP_VERSION):
            out.append(("app", app, "app_avail"))
        return out

    def _offer_updates(self, manual):
        if self.upd_busy or getattr(self, "closed", False):
            return
        offers = [o for o in self._available_updates() if (o[0], o[1]["version"]) not in self.upd_asked]
        if not offers:
            if manual and self.upd_manifest is not None:
                cfg = self.last_cfg or {}
                fw = T["upd_fw_part"].format(fw=cfg["fw"]) if cfg.get("fw") else ""
                self._dialog(T["upd_uptodate_t"], T["upd_uptodate_m"].format(app=APP_VERSION, fw=fw), "success")
            return
        kind, info, key = offers[0]
        self.upd_asked.add((kind, info["version"]))
        cur = (self.last_cfg or {}).get("fw", "?") if kind == "firmware" else APP_VERSION
        title = T["fw_avail_t" if kind == "firmware" else "app_avail_t"]
        msg = T[key].format(new=info["version"], cur=cur)
        can_install = key != "fw_need_usb"

        def ask():
            if not can_install:
                self._dialog(title, msg, "info")
            elif self._dialog(title, msg, "info", (("btn_skip", "secondary"), ("btn_install", "primary"))) == "btn_install":
                self._start_update(kind, info)
            # Sıradaki teklif (ör. firmware'den sonra uygulama).
            self.root.after(300, lambda: self._offer_updates(False))

        if self._app_in_front():
            self.root.after(0, ask)
        elif not can_install:
            self._notify(title, msg, on_click=ask)
        else:
            # Arka planda: bildirimin kendisinde Yükle / Şimdilik atla. Yükle
            # bildirimi kapatmaz, kart ilerleme görünümüne döner.
            def skip():
                self._close_notice()
                self.root.after(300, lambda: self._offer_updates(False))
            self._notify(title, msg, on_click=ask, timeout=None,
                         actions=((T["btn_skip"], "TealOutline.TButton", skip),
                                  (T["btn_install"], "Teal.TButton",
                                   lambda: self._start_update(kind, info, in_notice=True))))

    def _start_update(self, kind, info, in_notice=False):
        if self.upd_busy:
            self._show_progress()
            return
        if kind == "firmware" and not (self.connected and self.link.ota_supported()):
            self._tell(T["dl_failed_t"], T["dl_need_device"], "warning")
            return
        self.upd_busy = {"kind": kind, "info": info, "phase": "download", "done": 0, "total": info.get("size", 0)}
        self.upd_cancel = False
        if in_notice and self.notice_win is not None:
            self._notice_progress()
        else:
            self._show_progress()

        def work():
            try:
                path = updater.download(info, progress=lambda d, t: self.events.put(("upd_progress", (kind, d, t))),
                                        cancel=lambda: self.upd_cancel)
                self.events.put(("upd_done", (kind, path, info)))
            except Exception as e:
                self.events.put(("upd_failed", (kind, str(e) or e.__class__.__name__)))
        threading.Thread(target=work, daemon=True).start()

    def _downloaded(self, kind, path, info):
        if not self.upd_busy:
            return
        if kind == "firmware":
            if not (self.connected and self.link.ota_supported()):
                self._update_failed(T["dl_need_device"])
                return
            sha = info.get("sha256")
            if not sha:
                import hashlib
                with open(path, "rb") as f:
                    sha = hashlib.sha256(f.read()).hexdigest()
            self.upd_busy.update(phase="flash", done=0, total=info.get("size") or os.path.getsize(path))
            self._progress("flash", 0, self.upd_busy["total"])
            self.link.call(self.link.ota, path, sha, info.get("size") or os.path.getsize(path))
            return
        # Uygulama
        self._finish_update()
        v = info["version"]
        if not updater.can_self_update():
            self.root.after(0, lambda: self._dialog(T["app_ready_t"], T["app_manual"].format(v=v, path=path), "info"))
            return
        self.pending_app_update = path

        def ask():
            if self._dialog(T["app_ready_t"], T["app_ready"].format(v=v), "success",
                            (("btn_later", "secondary"), ("btn_restart", "primary"))) == "btn_restart":
                self._shutdown(relaunch=True)
        self.root.after(0, ask)

    def _update_failed(self, err):
        self._finish_update()
        self.root.after(0, lambda: self._tell(T["dl_failed_t"], err, "error"))

    def _finish_update(self):
        self.upd_busy = None
        if self._upd_note() is not None:
            self._close_notice()
        self.upd_note = None
        if self.upd_win is not None:
            try:
                self.upd_win.destroy()
            except tk.TclError:
                pass
            self.upd_win = None
        self._update_head_progress()

    def _tell(self, title, msg, kind):
        """Uygulama öndeyse uyarı, değilse bildirim."""
        if self._app_in_front():
            self._dialog(title, msg, kind)
        else:
            self._notify(title, msg)

    def _cancel_update(self):
        if not self.upd_busy:
            return
        if self.upd_busy["phase"] == "download":
            self.upd_cancel = True
        else:
            self.link.ota_cancel = True

    @staticmethod
    def _size(n):
        return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, round(n / 1024))} KB"

    def _progress(self, phase, done, total):
        if not self.upd_busy:
            return
        self.upd_busy.update(phase=phase, done=done, total=total)
        pct = int(done * 100 / total) if total else 0
        for w in (self.upd_win, self._upd_note()):
            if w is None:
                continue
            try:
                w.bar.configure(value=pct)
                if phase == "download":
                    w.status.config(text=T["dl_downloading"].format(p=pct))
                    w.detail.config(text=T["dl_sizes"].format(done=self._size(done), total=self._size(total)) if total else "")
                else:
                    w.status.config(text=T["dl_flashing"].format(p=pct))
                    w.detail.config(text=T["dl_flash_hint"])
            except tk.TclError:
                pass
        self._update_head_progress()

    def _upd_note(self):
        """İlerleme gösteren bildirim kartı (kapatıldıysa ya da yerine başka
        bildirim geldiyse None)."""
        note = getattr(self, "upd_note", None)
        return note if note is not None and note is self.notice_win else None

    def _notice_progress(self):
        """Açık bildirimi ilerleme görünümüne çevirir: kaybolmaz, ✕ yalnızca
        kartı kapatır (güncelleme arka planda sürer), Vazgeç iptal eder, karta
        tıklamak uygulamayı ilerleme penceresiyle açar."""
        win = self.notice_win
        if win is None or not self.upd_busy:
            return
        u = self.ui
        if win.timer:
            win.after_cancel(win.timer)
            win.timer = None
        kind, info = self.upd_busy["kind"], self.upd_busy["info"]
        win.title_lbl.config(text=T["dl_title_" + kind])
        win.msg.config(text=f"Lookie {info['version']}")
        for c in win.extra.winfo_children():
            c.destroy()
        bg = win.card_bg
        win.status = tk.Label(win.extra, text="", bg=bg, fg=self.fg, font=(FONT, 10), anchor="w")
        win.status.pack(fill="x", pady=(round(10 * u), round(4 * u)))
        win.bar = ttk.Progressbar(win.extra, mode="determinate", maximum=100, length=round(260 * u))
        win.bar.pack(fill="x")
        win.detail = tk.Label(win.extra, text="", bg=bg, fg=self.muted, font=(FONT, 9), anchor="w")
        win.detail.pack(fill="x", pady=(round(4 * u), 0))
        row = tk.Frame(win.extra, bg=bg)
        row.pack(fill="x", pady=(round(10 * u), 0))
        ttk.Button(row, text=T["btn_cancel"], style="TealOutline.TButton", width=10,
                   command=self._cancel_update).pack(side="right")

        def open_progress():
            self._close_notice()
            self._show_window()
            self.root.after(150, self._show_progress)
        win.on_open = open_progress
        self.upd_note = win
        self._place_notice(win)
        b = self.upd_busy
        self._progress(b["phase"], b["done"], b["total"])

    def _update_head_progress(self):
        """Pencere gizliyken başlıkta küçük bir ilerleme yazısı."""
        b = self.upd_busy
        text = ""
        if b and (self.upd_win is None or not self.upd_win.winfo_viewable()):
            pct = int(b["done"] * 100 / b["total"]) if b.get("total") else 0
            text = ("↓ " if b["phase"] == "download" else "⇪ ") + (f"%{pct}" if LANG == "tr" else f"{pct}%")
        try:
            self.upd_head.config(text=text)
        except (AttributeError, tk.TclError):
            pass

    def _show_progress(self):
        """İlerleme penceresi: modal değil (uygulama kullanılabilir kalır), Gizle
        ile kapanır ve indirme arka planda sürer; başlıktaki gösterge geri açar."""
        if not self.upd_busy:
            return
        if self.upd_win is not None:
            try:
                self.upd_win.deiconify()
                self.upd_win.lift()
                self._update_head_progress()
                return
            except tk.TclError:
                self.upd_win = None
        u = self.ui
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        border = "#3a3a3a" if self.dark else "#d9dde3"
        win.configure(bg=border)
        card = tk.Frame(win, bg=self.bg)
        card.pack(fill="both", expand=True, padx=1, pady=1)
        body = ttk.Frame(card, padding=(round(24 * u), round(20 * u), round(24 * u), round(18 * u)))
        body.pack(fill="both", expand=True)
        kind = self.upd_busy["kind"]
        info = self.upd_busy["info"]
        top = ttk.Frame(body)
        top.pack(fill="x")
        logo = tk.Canvas(top, width=round(36 * u), height=round(36 * u), highlightthickness=0, bg=self.bg)
        logo.photo = ImageTk.PhotoImage(scaled_icon(round(36 * u)))
        logo.create_image(0, 0, image=logo.photo, anchor="nw")
        logo.pack(side="left", padx=(0, round(12 * u)))
        titles = ttk.Frame(top)
        titles.pack(side="left", fill="x")
        ttk.Label(titles, text=T["dl_title_" + kind], font=(FONT, 12, "bold")).pack(anchor="w")
        ttk.Label(titles, text=f"Lookie {info['version']}", foreground=self.muted).pack(anchor="w")
        win.status = ttk.Label(body, text="")
        win.status.pack(anchor="w", pady=(round(16 * u), round(6 * u)))
        win.bar = ttk.Progressbar(body, mode="determinate", maximum=100, length=round(340 * u))
        win.bar.pack(fill="x")
        win.detail = ttk.Label(body, text="", foreground=self.muted, font=(FONT, 9))
        win.detail.pack(anchor="w", pady=(round(6 * u), 0))
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(round(16 * u), 0))
        ttk.Button(row, text=T["btn_cancel"], style="TealOutline.TButton", width=12,
                   command=self._cancel_update).pack(side="right")
        ttk.Button(row, text=T["btn_hide"], style="Teal.TButton", width=12,
                   command=lambda: (win.withdraw(), self._update_head_progress())).pack(side="right", padx=(0, round(8 * u)))
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 3
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = u32.GetParent(win.winfo_id()) or win.winfo_id()
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            owner = u32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            u32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            u32.SetWindowLongPtrW(hwnd, -8, owner)
            win.attributes("-topmost", bool(self.root.attributes("-topmost")))
        except Exception:
            pass
        win.deiconify()
        win.lift()
        self.upd_win = win
        b = self.upd_busy
        self._progress(b["phase"], b["done"], b["total"])

    # -- sistem tepsisi -------------------------------------------------------
    def _update_tray(self):
        """Ayara göre tepsi simgesini açar/kapatır."""
        if PREFS["tray"] and self.tray is None:
            try:
                self.tray = TrayIcon(self.events)
                self._update_tray_title()
            except Exception:
                log_error("tray")
                self.tray = None
        elif not PREFS["tray"] and self.tray is not None:
            self.tray.stop()
            self.tray = None
            if self._hidden():
                self._show_window()

    def _open_tray_menu(self, x, y):
        """Tepsi simgesinin sağ tık menüsü: temaya uygun, pil satırında başlıktaki
        pil simgesiyle. İmlecin sol üstünde açılır (Windows tepsi menüleri gibi)."""
        self._close_tray_menu()
        u = self.ui
        dark = self.dark
        card = "#2b2b2b" if dark else "#ffffff"
        border = "#3d3d3d" if dark else "#d1d5db"
        hover = "#3a3a3a" if dark else "#eef2f2"
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=border)
        body = tk.Frame(win, bg=card, padx=round(4 * u), pady=round(4 * u))
        body.pack(fill="both", expand=True, padx=1, pady=1)

        # Pil satırı (tıklanmaz)
        info = tk.Frame(body, bg=card, padx=round(10 * u), pady=round(7 * u))
        info.pack(fill="x")
        icon = tk.Canvas(info, width=round(30 * u), height=round(16 * u), highlightthickness=0, bg=card)
        icon.pack(side="left", padx=(0, round(8 * u)))
        text = tk.Label(info, text="", bg=card, fg=self.muted, font=(FONT, 10))
        text.pack(side="left")
        self.tray_menu = win
        win.bat_icon, win.bat_text, win.card = icon, text, card
        self._draw_tray_menu_battery()

        tk.Frame(body, bg=border, height=1).pack(fill="x", padx=round(6 * u), pady=round(3 * u))

        def item(label, action, bold=False):
            row = tk.Label(body, text=label, bg=card, fg=self.fg, anchor="w", cursor="hand2",
                           font=(FONT, 10, "bold") if bold else (FONT, 10),
                           padx=round(12 * u), pady=round(6 * u))
            row.pack(fill="x")
            row.bind("<Enter>", lambda _e: row.config(bg=hover))
            row.bind("<Leave>", lambda _e: row.config(bg=card))
            row.bind("<ButtonRelease-1>", lambda _e: (self._close_tray_menu(), action()))
        item(T["tray_show"], self._show_window, bold=True)
        item(T["tray_quit"], self._on_close)

        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        w = max(w, round(190 * u))
        left, top, right, bottom = work_area()
        px = min(max(left, x - w), right - w)
        py = min(max(top, y - h), bottom - h)
        win.geometry(f"{w}x{h}+{px}+{py}")
        try:
            import ctypes
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
            GWL_EXSTYLE, WS_EX_TOOLWINDOW = -20, 0x80
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                                ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_TOOLWINDOW)
            pref = ctypes.c_int(2)  # Windows 11: yuvarlak köşe
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        win.deiconify()
        win.lift()
        win.focus_force()
        # Kapanma: Esc, odak gidince (menü odağı almışsa) ya da menünün dışına
        # tıklanınca. Odağı alamadığı durumlar için dış tıklama fare
        # düğmesinin durumundan da izlenir.
        win.had_focus = False
        win.bind("<FocusIn>", lambda _e: setattr(win, "had_focus", True))
        win.bind("<FocusOut>", lambda _e: win.after(80, self._tray_menu_focus_check))
        win.bind("<Escape>", lambda _e: self._close_tray_menu())
        win.after(150, self._tray_menu_watch)

    def _tray_menu_watch(self):
        win = self.tray_menu
        if win is None:
            return
        try:
            import ctypes
            from ctypes import wintypes
            u32 = ctypes.windll.user32
            if any(u32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02)):
                pt = wintypes.POINT()
                u32.GetCursorPos(ctypes.byref(pt))
                x0, y0 = win.winfo_rootx(), win.winfo_rooty()
                if not (x0 <= pt.x < x0 + win.winfo_width() and y0 <= pt.y < y0 + win.winfo_height()):
                    self._close_tray_menu()
                    return
        except (tk.TclError, OSError):
            self._close_tray_menu()
            return
        win.after(60, self._tray_menu_watch)

    def _tray_menu_focus_check(self):
        win = self.tray_menu
        if win is None or not getattr(win, "had_focus", False):
            return
        try:
            f = win.focus_get()
        except (tk.TclError, KeyError):
            f = None
        if f is None or not str(f).startswith(str(win)):
            self._close_tray_menu()

    def _draw_tray_menu_battery(self):
        win = self.tray_menu
        if win is None:
            return
        try:
            bat = self.bat
            pct, charging = (bat[0], bat[1]) if bat else (BATTERY_UNKNOWN, False)
            if bat is None:
                win.bat_icon.pack_forget()  # cihaz bağlı değil: yalnızca yazı
            else:
                if not win.bat_icon.winfo_ismapped():
                    win.bat_icon.pack(side="left", padx=(0, round(8 * self.ui)), before=win.bat_text)
                img = self._battery_image(pct, charging, self.ui, win.card)
                win.bat_icon.photo = img.photo()
                win.bat_icon.delete("all")
                win.bat_icon.create_image(0, 0, image=win.bat_icon.photo, anchor="nw")
            low = bat is not None and not charging and pct != BATTERY_UNKNOWN and pct <= 20
            color = "#F59E0B" if charging else (self._battery_color(pct) if low else self.fg if bat else self.muted)
            win.bat_text.config(text=self._tray_battery_text(), fg=color)
        except tk.TclError:
            self.tray_menu = None

    def _close_tray_menu(self):
        if self.tray_menu is not None:
            try:
                self.tray_menu.destroy()
            except tk.TclError:
                pass
            self.tray_menu = None

    def _tray_battery_text(self):
        # Tepsinin iş parçacığından okunur; yalnızca self.bat'a bakar.
        bat = self.bat
        if bat is None:
            return T["tray_offline"]
        pct, charging, _usb = bat
        if charging:
            return T["tray_bat"].format(s=T["bat_charging"])
        if pct == BATTERY_UNKNOWN:
            return T["bat_unknown"]
        return T["tray_bat"].format(s=f"%{pct}" if LANG == "tr" else f"{pct}%")

    def _update_tray_title(self):
        if self.tray:
            self.tray.set_title("Lookie – " + self._tray_battery_text())

    def _hidden(self):
        try:
            return self.root.state() in ("withdrawn", "iconic")
        except tk.TclError:
            return False

    def _minimize(self):
        if self.tray is not None:
            self._close_help()
            self._close_dropdown()
            self.root.withdraw()
        else:
            self.root.iconify()

    def _maybe_hide_to_tray(self):
        try:
            if self.tray is not None and self.root.state() == "iconic":
                self.root.withdraw()
        except tk.TclError:
            pass

    def _show_window(self):
        root = self.root
        try:
            if root.state() in ("withdrawn", "iconic"):
                root.deiconify()
        except tk.TclError:
            return
        self._bring_to_front()
        root.after(50, self._update_caption)

    def _app_in_front(self):
        """Uygulama görünür ve ön planda mı (odak bizdeyse)?"""
        if self._hidden():
            return False
        try:
            import ctypes
            from ctypes import wintypes
            pid = wintypes.DWORD()
            fg = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            return bool(fg) and pid.value == os.getpid()
        except Exception:
            return True

    # -- olay döngüsü ---------------------------------------------------------
    def _set_status(self, key):
        self.status_key = key
        self.status_label.config(text=T[key])
        color = {"connected": "#22c55e", "busy": "#f59e0b"}.get(key, "#9ca3af")
        img = AAImage(12, 12, self.ui, self.bg)
        img.circle(6, 6, 5, fill=color)
        self.status_img = img.photo()
        self.status_dot.delete("all")
        self.status_dot.create_image(0, 0, image=self.status_img, anchor="nw")

    def _poll(self):
        if show_requested():
            self._show_window()  # uygulama ikinci kez açılmaya çalışıldı
        if self.frame and getattr(self.frame, "cover_on", False) and not getattr(self, "_uncovering", False):
            self._uncovering = True
            self.root.after(20, self._uncover)
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "status":
                    if data == "connected":
                        self.connected = True
                        self._set_enabled(True)
                        self._build_profile_tab()
                    self._set_status(data)
                elif kind == "config":
                    self._apply_config(data)
                    self._profile_on_config(data)
                    # Cihazın firmware sürümü artık biliniyor: yayınla karşılaştır.
                    self.root.after(1500, lambda: self._offer_updates(manual=False))
                    self._gyro_check(data)
                    if self.import_pending:
                        self.import_pending = False
                        import time
                        self.import_label.config(text=T["imported"].format(time=time.strftime("%H:%M:%S")))
                elif kind == "telemetry":
                    self.tel = data
                    self.tel_age = 0
                    self._show_telemetry(data)
                elif kind in ("upd_manifest", "upd_error", "upd_progress", "upd_done", "upd_failed",
                              "ota_progress", "ota_done", "ota_failed"):
                    self._on_update_event(kind, data)
                elif kind == "tray_menu":
                    self._open_tray_menu(*data)
                elif kind == "tray":
                    if data == "show":
                        self._show_window()
                    elif data == "quit":
                        self._on_close()
                        if getattr(self, "closed", False):
                            return
                elif kind == "disconnected":
                    self.connected = False
                    self.prof_synced = False
                    self.prof_capture = False
                    self._build_profile_tab()
                    self.tel = None
                    self._set_enabled(False)
                    self._set_status("searching")
                    self._show_telemetry(None)
                    self.real_bat = None
                    if not self._demo_on():
                        self._set_battery(None)
        except queue.Empty:
            pass
        except Exception:
            # Bir işleyicinin hatası olay döngüsünü durdurmasın: eskiden döngü
            # bir daha kurulmuyor ve arayüz o andan sonra hiçbir olayı
            # işlemiyordu (ör. ilerleme %0'da donuyordu). Kaydet ve devam et.
            log_error("event")
        finally:
            if not getattr(self, "closed", False):
                self.root.after(50, self._poll)

    def _tick(self):
        # Gyro kalibrasyonu sırasında cihaz telemetri göndermez; bunu
        # "meşgul" olarak göster. Telemetri dönünce _show_telemetry düzeltir.
        if self.connected:
            self.tel_age += 1
            if self.tel_age == 3:
                self._set_status("busy")
        self.root.after(1000, self._tick)

    def _show_telemetry(self, t):
        if t is None:
            for lbl in self.readouts.values():
                lbl.config(text="–")
            self._draw_dial()
            return
        hy, hp, hr, vy, ay, pa, flags, bat = t
        self.real_bat = (bat, bool(flags & FLAG_CHARGING), bool(flags & FLAG_USB))
        if not self._demo_on():
            self._set_battery(self.real_bat)
        # Cihazın eksenleri sağ el kuralıyla: + sağ-sol = sola, + yukarı-aşağı =
        # aşağı. Ekranda sağa ve yukarıya bakış pozitif görünsün.
        hy, vy, ay, hp = -hy, -vy, -ay, -hp
        if self.status_label.cget("text") == T["busy"] and self.gyro_win is None:
            # Telemetri geri geldi: durumu ve (değişmiş olabilecek) ayarları yenile.
            self._set_status("connected")
            self.link.call(self.link.read_config)
        self.readouts["head_yaw"].config(text=f"{hy / 100:+.1f}°")
        self.readouts["view_yaw"].config(text=f"{vy / 100:+.1f}°")
        self.readouts["pitch"].config(text=f"{hp / 100:+.1f}°")
        self.readouts["roll"].config(text=f"{hr / 100:+.1f}°")
        self.readouts["autoyaw"].config(text=f"{ay / 100:+.2f}°")
        self.readouts["pitch_axis"].config(text=f"{pa / 10000:+.3f}")
        dev_dirty = bool(flags & FLAG_DIRTY)
        if dev_dirty != self.dirty and not self.pending:
            self.dirty = dev_dirty
            self._update_dirty()
        self._draw_dial(hy / 100, vy / 100, hp / 100)

    # -- pil göstergesi ---------------------------------------------------------
    def _set_battery(self, bat):
        if bat == self.bat:
            return
        self.bat = bat
        self._check_low_battery()
        self._update_tray_title()
        charging = bool(bat and bat[1])
        if charging and self.bat_job is None:
            self.bat_phase = 0.0
            self.bat_job = self.root.after(40, self._battery_anim)
        elif not charging and self.bat_job is not None:
            self.root.after_cancel(self.bat_job)
            self.bat_job = None
        self._draw_battery()

    def _battery_anim(self):
        self.bat_job = None
        if not (self.bat and self.bat[1]):
            return
        # ~1,8 sn'de bir dolar; dolunca kısa bir an dolu bekler, sonra baştan.
        self.bat_phase = (self.bat_phase + 0.04 / 1.8) % 1.25
        self._draw_battery()
        self.bat_job = self.root.after(40, self._battery_anim)

    def _demo_on(self):
        return BATTERY_DEMO or bool(PREFS["battery_demo"])

    def _set_battery_demo(self, on):
        """Ayarlardaki anahtar: testi başlatır ya da durdurup gerçek duruma döner."""
        global BATTERY_DEMO
        BATTERY_DEMO = False  # ortam değişkeniyle açılmış olsa da artık anahtar yönetir
        self._set_pref("battery_demo", on)
        if self.bat_demo_job is not None:
            self.root.after_cancel(self.bat_demo_job)
            self.bat_demo_job = None
        self.low_warned = False
        self._close_notice()
        if on:
            self.bat_demo_i = 0
            self._battery_demo()
        else:
            self._set_battery(self.real_bat if self.connected else None)

    def _battery_demo(self):
        """Pil testi: %100'den 0'a azalır, ardından şarj animasyonu."""
        self.bat_demo_job = None
        if not self._demo_on():
            return
        charge_steps = max(1, 6000 // BATTERY_DEMO_MS)  # ~6 sn şarj animasyonu
        i = self.bat_demo_i % (101 + charge_steps)
        if i <= 100:
            self._set_battery((100 - i, False, False))
        else:
            self._set_battery((BATTERY_UNKNOWN, True, True))
        self.bat_demo_i += 1
        self.bat_demo_job = self.root.after(BATTERY_DEMO_MS, self._battery_demo)

    def _draw_battery(self):
        c = getattr(self, "bat_canvas", None)
        if c is None:
            return
        c.delete("all")
        if self.bat is None:
            c.config(width=1)
            self.bat_label.config(text="")
            return
        c.config(width=round(30 * self.ui))
        pct, charging, _usb = self.bat
        known = pct != BATTERY_UNKNOWN
        img = self._battery_image(pct, charging, self.ui, self.bg)
        if charging:
            self.bat_label.config(text=T["bat_charging"], foreground="#F59E0B")
        elif known:
            self.bat_label.config(text=f"%{pct}" if LANG == "tr" else f"{pct}%",
                                  foreground=self._battery_color(pct) if pct <= 20 else self.fg)
        else:
            self.bat_label.config(text=T["bat_unknown"], foreground=self.muted)
        c.photo = img.photo()
        c.create_image(0, 0, image=c.photo, anchor="nw")
        self._draw_tray_menu_battery()

    @staticmethod
    def _battery_color(pct):
        return "#ef4444" if pct <= 10 else ("#f59e0b" if pct <= 20 else "#22c55e")

    def _battery_image(self, pct, charging, scale, bg):
        """30 x 16 mantıksal piksellik pil simgesi (scale = ekran ölçeği x büyütme)."""
        known = pct != BATTERY_UNKNOWN
        img = AAImage(30, 16, scale, bg)
        edge = self.fg if (known or charging) else self.muted
        # Gövde (çerçeve) ve sağdaki uç.
        img.rrect(1, 2, 26, 14, 3.2, edge)
        img.rrect(2.4, 3.4, 24.6, 12.6, 2.2, bg)
        img.rrect(26.6, 5.5, 28.8, 10.5, 1.0, edge)
        x0, x1 = 3.8, 23.2  # dolgu alanı
        if charging:
            level = min(1.0, self.bat_phase)
            if level > 0.02:
                w = (x1 - x0) * level
                img.rrect(x0, 4.8, x0 + w, 11.2, 1.3, "#F59E0B")
                # Dolgunun önündeki parlak şerit: dolma hissi.
                img.rrect(max(x0, x0 + w - 3.0), 4.8, x0 + w, 11.2, 1.3, "#FBBF24")
            bolt = [(16.6, 2.6), (9.4, 9.0), (13.2, 9.0), (11.4, 13.4), (18.6, 7.0), (14.8, 7.0)]
            img.d.polygon([img._p(x, y) for x, y in bolt], fill="#ffffff" if self.dark else "#1f2937")
        elif known and pct > 0:
            level = min(100, pct) / 100
            img.rrect(x0, 4.8, x0 + max(1.6, (x1 - x0) * level), 11.2, 1.3, self._battery_color(pct))
        return img

    # -- düşük pil uyarısı -----------------------------------------------------
    def _check_low_battery(self):
        if not self.bat:
            return
        pct, charging, _usb = self.bat
        if pct == BATTERY_UNKNOWN:
            return
        if charging or pct >= 15:
            self.low_warned = False  # yeniden kur: bir sonraki düşüşte tekrar uyar
            if self.notice_win is not None and charging:
                self._close_notice()
            return
        if pct < 10 and not self.low_warned:
            self.low_warned = True
            # Olay döngüsünün dışında: uyarı penceresi beklerken (wait_window)
            # telemetri kuyruğu durmasın.
            self.root.after(0, lambda: self._low_battery(pct))

    def _low_battery(self, pct):
        msg = T["low_bat"].format(p=pct)
        # Uyarı penceresi yalnızca uygulama öndeyken: arka plandayken, tepside
        # ya da oyun oynanırken odağı çalmadan köşede bildirim çıkar.
        if PREFS["low_bat_alert"] and self._app_in_front():
            self._dialog(T["low_bat_t"], msg, "warning")
        else:
            self._notify(T["low_bat_t"], msg, pct)

    def _bring_to_front(self):
        """Pencereyi öne getirir. Windows arka plandaki bir uygulamanın odağı
        almasını engeller; o an öndeki pencerenin giriş kuyruğuna kısa süre
        bağlanmak (AttachThreadInput) bu kilidi açar. Eskiden kısa bir Alt
        basışı kullanılıyordu: Alt bırakılınca pencere menü moduna giriyor ve
        hemen ardından açılan uyarı, tıklanana kadar boş görünüyordu."""
        root = self.root
        try:
            if root.state() in ("iconic", "withdrawn"):
                root.deiconify()
            root.lift()
            import ctypes
            from ctypes import wintypes
            u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
            hwnd = wintypes.HWND(u32.GetParent(root.winfo_id()) or root.winfo_id())
            fg = u32.GetForegroundWindow()
            pid = wintypes.DWORD()
            fg_thread = u32.GetWindowThreadProcessId(fg, ctypes.byref(pid)) if fg else 0
            if fg and pid.value == os.getpid():
                return  # zaten öndeyiz
            me = k32.GetCurrentThreadId()
            attached = bool(fg_thread) and fg_thread != me and u32.AttachThreadInput(me, fg_thread, True)
            try:
                u32.BringWindowToTop(hwnd)
                u32.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    u32.AttachThreadInput(me, fg_thread, False)
            root.focus_force()
        except Exception:
            pass

    def _notify(self, title, message, pct=None, on_click=None, actions=None, timeout=10000):
        """Ekranın sağ altında, odağı çalmayan bildirim kartı (timeout ms sonra
        kaybolur, None ise kalır; tıklayınca uygulama öne gelir, varsa on_click
        çağrılır). pct verilirse simge pil, yoksa uygulama logosu. actions:
        ((yazı, ttk stili, işlev), ...) kartın altında düğmeler."""
        self._close_notice()
        u = self.ui
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        border = "#3a3a3a" if self.dark else "#d1d5db"
        # Tema zemini: yuvarlak ttk düğmeleri ve ilerleme çubuğu bu zemine çizilir.
        card_bg = self.bg
        win.configure(bg=border)
        card = tk.Frame(win, bg=card_bg, padx=round(16 * u), pady=round(14 * u))
        card.pack(fill="both", expand=True, padx=1, pady=1)
        icon = tk.Canvas(card, width=round(48 * u), height=round(26 * u), highlightthickness=0, bg=card_bg)
        icon.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, round(12 * u)), pady=(round(2 * u), 0))
        if pct is not None:
            img = self._battery_image(pct, False, u * 1.6, card_bg)
            icon.photo = img.photo()
            icon.create_image(0, 0, image=icon.photo, anchor="nw")
        else:
            icon.configure(width=round(32 * u), height=round(32 * u))
            icon.photo = ImageTk.PhotoImage(scaled_icon(round(32 * u)))
            icon.create_image(0, 0, image=icon.photo, anchor="nw")
        head = tk.Frame(card, bg=card_bg)
        head.grid(row=0, column=1, sticky="ew")
        win.title_lbl = tk.Label(head, text=title, bg=card_bg, fg=self.fg, font=(FONT, 11, "bold"))
        win.title_lbl.pack(side="left")
        tk.Label(head, text="Lookie", bg=card_bg, fg=self.muted, font=(FONT, 9)).pack(side="left", padx=(8, 0))
        close = tk.Label(head, text="✕", bg=card_bg, fg=self.muted, font=(FONT, 10), cursor="hand2")
        close.pack(side="right", padx=(16, 0))
        win.msg = tk.Label(card, text=message, bg=card_bg, fg=self.muted, font=(FONT, 10), justify="left",
                           wraplength=round(260 * u))
        win.msg.grid(row=1, column=1, sticky="w", pady=(round(3 * u), 0))
        card.columnconfigure(1, weight=1)

        def open_app(_e=None):
            self._close_notice()
            if on_click:
                self._show_window()
                self.root.after(150, on_click)
            else:
                self._bring_to_front()
        win.on_open = open_app
        for w in (card, icon, head) + tuple(card.winfo_children()) + tuple(head.winfo_children()):
            if w is not close:
                w.bind("<Button-1>", lambda _e: win.on_open())
        close.bind("<Button-1>", lambda _e: self._close_notice())

        # Düğmeler ve ilerleme bu alana gelir; karta tıklama davranışını almaz.
        win.card_bg = card_bg
        win.extra = tk.Frame(card, bg=card_bg)
        win.extra.grid(row=2, column=1, sticky="ew")
        if actions:
            row = tk.Frame(win.extra, bg=card_bg)
            row.pack(fill="x", pady=(round(12 * u), 0))
            for text, style, cmd in reversed(actions):
                ttk.Button(row, text=text, style=style, command=cmd).pack(side="right", padx=(round(8 * u), 0))

        self._place_notice(win)
        notice_window_style(win)
        win.attributes("-alpha", 0.0)
        win.deiconify()
        self.notice_win = win

        def fade(a):
            if self.notice_win is not win:
                return
            win.attributes("-alpha", min(1.0, a))
            if a < 1.0:
                win.after(16, lambda: fade(a + 0.08))
        fade(0.08)
        win.timer = win.after(timeout, lambda: self._close_notice() if self.notice_win is win else None) \
            if timeout else None

    def _place_notice(self, win):
        """Kartı (boyutu değiştiyse yeniden) ekranın sağ altına yerleştirir.
        Genişlik ilk hâlinden aşağı inmez (ilerleme görünümü daha kısa yazılıdır)."""
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        w = max(w, getattr(win, "min_w", 0))
        win.min_w = w
        left, top, right, bottom = work_area()
        margin = round(16 * self.ui)
        win.geometry(f"{w}x{h}+{right - w - margin}+{bottom - h - margin}")

    def _close_notice(self):
        if self.notice_win is not None:
            try:
                self.notice_win.destroy()
            except tk.TclError:
                pass
            self.notice_win = None

    # -- çizimler -----------------------------------------------------------
    def _draw_dial(self, head=None, view=None, pitch=None):
        u = self.ui
        img = AAImage(310, 260, u, self.bg)
        cx, cy, r = 130, 130, 104
        # Sağda yukarı-aşağı ölçeği: ±60°, yukarısı yukarı.
        px, top, bot, prange = 290, 30, 230, 60.0
        def py(v): return (top + bot) / 2 - (bot - top) / 2 * max(-1.0, min(1.0, v / prange))
        img.line([(px, top), (px, bot)], self.grid_c, 4)
        for v in (-60, -30, 0, 30, 60):
            half = 8 if v == 0 else 5
            img.line([(px - half, py(v)), (px + half, py(v))], self.grid_c, 2, caps=False)
        if pitch is not None:
            img.line([(px, py(0)), (px, py(pitch))], PITCH_COLOR, 4)
            img.circle(px, py(pitch), 7, fill=PITCH_COLOR)
        # Üstten görünüş: halka, çentikler, baş ve bakış ibreleri
        img.circle(cx, cy, r, outline=self.grid_c, width=2)
        for a in range(0, 360, 30):
            rad = math.radians(a)
            r1 = r - (10 if a % 90 == 0 else 5)
            img.line([(cx + r1 * math.sin(rad), cy - r1 * math.cos(rad)),
                      (cx + r * math.sin(rad), cy - r * math.cos(rad))], self.grid_c, 2, caps=False)
        for ang, color, width in ((head, self.muted, 3), (view, TEAL, 5)):
            if ang is None:
                continue
            rad = math.radians(ang)
            img.line([(cx, cy), (cx + (r - 14) * math.sin(rad), cy - (r - 14) * math.cos(rad))], color, width)
        # Lookie yüzü; göz bebekleri kafayla birlikte sağa-sola ve yukarı-aşağı bakar.
        img.circle(cx, cy, 26, fill=TEAL)
        img.ellipse(cx - 15, cy - 8, cx - 3, cy + 6, fill="#FFFFFF")
        img.ellipse(cx + 3, cy - 8, cx + 15, cy + 6, fill="#FFFFFF")
        ox = 0 if head is None else max(-3.0, min(3.0, head / 15))
        oy = 0 if pitch is None else max(-4.0, min(4.0, -pitch / 10))
        img.circle(cx - 8 + ox, cy - 2 + oy, 3.2, fill="#134E4A")
        img.circle(cx + 10 + ox, cy - 2 + oy, 3.2, fill="#134E4A")
        img.circle(cx - 6.8 + ox, cy - 3.4 + oy, 1.0, fill="#FFFFFF")
        img.circle(cx + 11.2 + ox, cy - 3.4 + oy, 1.0, fill="#FFFFFF")

        c = self.dial
        self.dial_img = img.photo()
        c.delete("all")
        c.create_image(0, 0, image=self.dial_img, anchor="nw")
        f = (FONT, 8)
        c.create_text(cx * u, (cy - r - 10) * u, text="0°", fill=self.muted, font=f)
        c.create_text((px - 12) * u, py(0) * u, text="0°", anchor="e", fill=self.muted, font=f)
        c.create_text(px * u, (top - 12) * u, text="+60°", fill=self.muted, font=f)
        c.create_text(px * u, (bot + 12) * u, text="-60°", fill=self.muted, font=f)

    def _draw_curve(self):
        u = self.ui
        c = self.curve
        w = max(c.winfo_width() / u, 440)
        h = 170
        img = AAImage(w, h, u, self.bg)
        x0, y0, x1, y1 = 34, 10, w - 10, h - 24
        hmax, vmax = 60.0, 180.0
        def X(v): return x0 + (x1 - x0) * v / hmax
        def Y(v): return y1 - (y1 - y0) * v / vmax
        for v in range(0, 181, 45):
            img.line([(x0, Y(v)), (x1, Y(v))], self.grid_c, 1, caps=False)
        for hv in range(0, 61, 15):
            img.line([(X(hv), y0), (X(hv), y1)], self.grid_c, 1, caps=False)
        img.dashed((X(0), Y(0)), (X(60), Y(60)), self.muted, 1.2)
        lin = self.values.get("ylin", 15)
        blend = self.values.get("yblend", 15)
        gain = self.values.get("ygain", 6)
        pts = []
        for i in range(0, 241):
            hv = i * hmax / 240
            pts.append((X(hv), Y(min(yaw_curve(hv, lin, blend, gain), self.yaw_range, vmax))))
        img.line(pts, TEAL, 3)

        self.curve_img = img.photo()
        c.delete("all")
        c.create_image(0, 0, image=self.curve_img, anchor="nw")
        f = (FONT, 8)
        for v in range(0, 181, 45):
            c.create_text((x0 - 6) * u, Y(v) * u, text=f"{v}°", anchor="e", fill=self.muted, font=f)
        for hv in range(0, 61, 15):
            c.create_text(X(hv) * u, (y1 + 12) * u, text=f"{hv}°", fill=self.muted, font=f)


def main():
    if not claim_single_instance():
        return  # uygulama zaten açık: o öne getirildi
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    root.title(T["title"])
    # Pencere, Windows'un başlık çubuğu kaldırılana kadar görünmez kalır.
    try:
        root.attributes("-alpha", 0.0)
    except tk.TclError:
        pass
    frame = None
    try:
        from winchrome import CustomFrame
        frame = CustomFrame(root)
    except Exception:
        log_error("custom frame")  # olmazsa Windows'un başlık çubuğu kalır
    splash = None
    try:
        splash = open_splash(root)  # açılış animasyonu her zaman oynar
    except Exception:
        log_error("splash")
    try:
        App(root, splash, frame)
    finally:
        try:
            root.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        clear_layered(root)
        if splash:
            splash.start()  # arayüz hazır: animasyon oynar, sonra içerik görünür
    root.mainloop()


def open_splash(root):
    """Pencereyi hemen gösterir ve açılış animasyonunu içeriğin üstüne
    koyar. Arayüz bu katmanın arkasında kurulur."""
    from splash import Splash
    theme = PREFS["theme"]
    dark = windows_dark_mode() if theme == "system" else theme == "dark"
    bg = "#1c1c1c" if dark else "#fafafa"
    ui = max(1.0, root.winfo_fpixels("1i") / 96.0)
    # Arayüzün kendi boyutuna yakın bir başlangıç boyutu; pencere ekranın
    # ortasında açılır.
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w, h = min(round(900 * ui), sw - 40), min(round(720 * ui), sh - 80)
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
    root.configure(bg=bg)
    try:
        root.iconphoto(True, ImageTk.PhotoImage(scaled_icon(32), master=root))
    except Exception:
        pass
    splash = Splash(root, ui, bg)
    # İlk kare (logonun boş hali) arayüz kurulmadan önce ekrana gelsin.
    root.update_idletasks()
    splash.redraw()
    root.attributes("-alpha", 1.0)
    root.update()
    return splash


if __name__ == "__main__":
    main()
