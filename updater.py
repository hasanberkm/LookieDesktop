"""Güncelleme denetimi ve indirme (sunucu gerekmez: GitHub Releases).

Yayın akışı (bkz. tools/make_update_json.py):
  1. GitHub'da yeni bir Release oluştur (ör. etiket v1.2.0).
  2. Dosyaları ekle: Lookie.exe, firmware .bin (firmware.ino.bin) ve
     update.json (betik üretir: sürümler, dosya adları, boyut, SHA-256).
  3. Uygulama açılışta ve belli aralıklarla
     https://api.github.com/repos/<UPDATE_REPO>/releases/latest
     adresini okur, ekteki update.json'u indirir ve sürümleri karşılaştırır.

Kimlik doğrulamasız GitHub API sınırı IP başına saatte 60 istektir; açılışta
ve 6 saatte bir denetim bunun çok altında kalır. Ek dosyaların indirilmesi
bu sınıra girmez. Repo herkese açık olmalı (gizli repoda API 404 döner).

Test ya da kendi sunucun için: LOOKIE_UPDATE_URL ortam değişkeni bir
update.json adresi (http://.../update.json) ya da bir release API adresi
olabilir.

update.json biçimi:
  {
    "app":      {"version": "1.1.0", "url": "Lookie.exe", "size": 123, "sha256": "...", "notes": "..."},
    "firmware": {"version": "1.2.0", "url": "lookie-firmware-1.2.0.bin", "size": 456, "sha256": "...",
                 "notes": "..."}
  }
"url" yalnızca dosya adıysa aynı release'in eklerinde aranır; tam adres de
olabilir. Bölümlerden biri yoksa o tür için güncelleme sunulmaz.
"""

import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request

UPDATE_REPO = "hasanberkm/LookieApp"
USER_AGENT = "Lookie-Updater"
TIMEOUT = 15


class UpdateError(Exception):
    pass


def parse_version(v):
    """"v1.2.0" / "1.2" -> (1, 2, 0). Sayı olmayan kısımlar yok sayılır."""
    nums = [int(x) for x in re.findall(r"\d+", str(v or ""))[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def is_newer(candidate, current):
    return parse_version(candidate) > parse_version(current)


def _get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("yayın bulunamadı (404)")
        if e.code == 403:
            raise UpdateError("GitHub istek sınırı doldu, daha sonra denenecek")
        raise UpdateError(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        raise UpdateError(f"bağlanılamadı ({e.reason})")
    except OSError as e:
        raise UpdateError(str(e))


def _get_json(url):
    with _get(url) as r:
        try:
            return json.loads(r.read().decode("utf-8"))
        except ValueError:
            raise UpdateError("geçersiz yanıt")


def fetch_manifest():
    """Son yayının güncelleme bilgisini döndürür:
    {"app": {...} | None, "firmware": {...} | None, "release": <etiket>}
    Dosya adresleri tam adrese çevrilmiş olur."""
    src = os.environ.get("LOOKIE_UPDATE_URL") or f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
    if src.lower().split("?")[0].endswith(".json") and "api.github.com" not in src:
        manifest = _get_json(src)
        base = src.rsplit("/", 1)[0] + "/"
        assets, tag = {}, ""
    else:
        rel = _get_json(src)
        assets = {a.get("name"): a.get("browser_download_url") for a in rel.get("assets", [])}
        tag = rel.get("tag_name", "")
        if "update.json" not in assets:
            raise UpdateError("yayında update.json yok")
        manifest = _get_json(assets["update.json"])
        base = None

    out = {"release": tag}
    for kind in ("app", "firmware"):
        info = manifest.get(kind)
        if not isinstance(info, dict) or not info.get("version") or not info.get("url"):
            out[kind] = None
            continue
        url = info["url"]
        if "://" not in url:
            if base:
                url = urllib.parse.urljoin(base, url)
            elif url in assets:
                url = assets[url]
            else:
                out[kind] = None  # dosya yayına eklenmemiş
                continue
        out[kind] = {"version": str(info["version"]), "url": url, "size": int(info.get("size") or 0),
                     "sha256": str(info.get("sha256") or "").lower(), "notes": str(info.get("notes") or "")}
    return out


def download(info, progress=None, cancel=None):
    """Dosyayı geçici klasöre indirir, boyut ve SHA-256'yı doğrular, yolunu
    döndürür. progress(indirilen, toplam) çağrılır; cancel() True dönerse
    durur (UpdateError("iptal edildi"))."""
    name = os.path.basename(urllib.parse.urlparse(info["url"]).path) or "update.bin"
    folder = os.path.join(tempfile.gettempdir(), "LookieUpdate")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    part = path + ".part"
    sha = hashlib.sha256()
    done = 0
    with _get(info["url"], accept="application/octet-stream") as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or info.get("size") or 0)
        while True:
            if cancel and cancel():
                f.close()
                _remove(part)
                raise UpdateError("iptal edildi")
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if info.get("size") and done != info["size"]:
        _remove(part)
        raise UpdateError("dosya eksik indi")
    if info.get("sha256") and sha.hexdigest() != info["sha256"]:
        _remove(part)
        raise UpdateError("dosya doğrulanamadı (SHA-256 tutmuyor)")
    _remove(path)
    os.replace(part, path)
    return path


def _remove(p):
    try:
        os.remove(p)
    except OSError:
        pass


def can_self_update():
    """Yalnızca paketlenmiş exe kendini değiştirebilir (kaynak koddan çalışırken değil)."""
    return bool(getattr(sys, "frozen", False))


def install_app(new_exe, relaunch=True, target=None):
    """Çalışan exe'yi yenisiyle değiştiren (relaunch ise yeniden açan) küçük bir betik başlatır.
    Çağıran uygulama hemen ardından kapanmalı: exe kullanımdayken üzerine
    yazılamaz, betik dosya serbest kalana kadar (en fazla ~60 sn) bekler."""
    import subprocess
    target = target or sys.executable
    script = os.path.join(tempfile.gettempdir(), "LookieUpdate", "install.cmd")
    # Not: arka planda konsolsuz çalıştığı için "timeout" kullanılamaz (hemen
    # hata verir); bekleme ping ile. Sayaç bloğun dışında (blok içindeki
    # %n% okunduğu anda sabitlenir ve artmaz).
    lines = [
        "@echo off",
        "set n=0",
        ":retry",
        "ping -n 2 127.0.0.1 >nul",
        f'move /y "{new_exe}" "{target}" >nul 2>&1',
        "if not errorlevel 1 goto ok",
        "set /a n+=1",
        "if %n% lss 60 goto retry",
        "exit /b 1",
        ":ok",
    ]
    if relaunch:
        lines.append(f'start "" "{target}"')
    lines.append('del "%~f0"')
    with open(script, "w", encoding="mbcs", errors="replace") as f:
        f.write("\r\n".join(lines) + "\r\n")
    # Görünmez konsolla (ping/move çalışsın), uygulamadan bağımsız; Windows'ta
    # alt süreç, açan uygulama kapanınca da sürer.
    flags = 0x00000200 | 0x08000000  # CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    subprocess.Popen(["cmd", "/c", script], creationflags=flags, close_fds=True)
