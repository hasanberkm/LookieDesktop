"""GitHub Release için update.json üretir.

Kullanım (proje klasöründen):
  python tools/make_update_json.py --app dist/Lookie.exe --app-version 1.1.0 \
      --fw <derleme klasörü>/LookieFirmware.ino.bin --fw-version 1.2.0 --out release

Çıktı klasörüne (varsayılan "release") şunlar yazılır:
  update.json                 sürümler, dosya adları, boyutlar, SHA-256
  Lookie.exe                  (--app verildiyse, kopya)
  lookie-firmware-X.Y.Z.bin   (--fw verildiyse, kopya)

Sonra GitHub'da yeni bir Release oluştur (etiket ör. v1.2.0) ve bu üç
dosyayı ekle. Uygulama "releases/latest"i okuduğu için Release taslak
(draft) ya da ön sürüm (pre-release) olmamalı.

Yalnızca biri güncellendiyse sadece onu ver: --app ya da --fw. Diğer tür
update.json'da olmaz ve onun için güncelleme sunulmaz.

Firmware dosyası: Arduino IDE'de Taslak > Derlenmiş İkili Dosyayı Dışa Aktar
ya da arduino-cli'nin derleme klasöründeki LookieFirmware.ino.bin. Birleşik
(merged) dosya DEĞİL: Bluetooth güncellemesi yalnızca uygulama imajını alır.
"""

import argparse
import hashlib
import json
import os
import shutil


def describe(path, version, name, notes):
    with open(path, "rb") as f:
        data = f.read()
    return {"version": version, "url": name, "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "notes": notes or ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", help="Lookie.exe")
    ap.add_argument("--app-version")
    ap.add_argument("--app-notes", default="")
    ap.add_argument("--fw", help="firmware .bin (LookieFirmware.ino.bin)")
    ap.add_argument("--fw-version")
    ap.add_argument("--fw-notes", default="")
    ap.add_argument("--out", default="release")
    a = ap.parse_args()
    if not a.app and not a.fw:
        ap.error("--app ya da --fw gerekli")
    os.makedirs(a.out, exist_ok=True)
    manifest = {}
    if a.app:
        if not a.app_version:
            ap.error("--app-version gerekli")
        name = "Lookie.exe"
        shutil.copyfile(a.app, os.path.join(a.out, name))
        manifest["app"] = describe(a.app, a.app_version, name, a.app_notes)
    if a.fw:
        if not a.fw_version:
            ap.error("--fw-version gerekli")
        with open(a.fw, "rb") as f:
            img = f.read()
        if img[:1] != b"\xe9":
            ap.error("bu bir ESP32 uygulama imajı değil")
        # Birleşik (merged) dosya da önyükleyiciyle 0xE9 ile başlar, ama
        # uygulama imajı 0x10000'de ikinci bir 0xE9 ile gelir.
        if len(img) > 0x10000 and img[0x10000:0x10001] == b"\xe9":
            ap.error("bu birleşik (merged) dosya; yalnızca LookieFirmware.ino.bin verilmeli")
        name = f"lookie-firmware-{a.fw_version}.bin"
        shutil.copyfile(a.fw, os.path.join(a.out, name))
        manifest["firmware"] = describe(a.fw, a.fw_version, name, a.fw_notes)
    with open(os.path.join(a.out, "update.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\n{a.out}/ içindeki dosyaları GitHub Release'e ekleyin.")


if __name__ == "__main__":
    main()
