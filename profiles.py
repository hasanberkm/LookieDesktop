"""Kullanıcı profilleri: her profil cihaz ayarlarının ayrı bir kopyasıdır.

Profiller bu bilgisayarda %APPDATA%\\Lookie\\profiles.json dosyasında durur.
Bir profil seçilince değerleri cihaza gönderilip cihazın belleğine
kaydedilir; ayarlar değiştirilip "Kaydet"e basılınca hem cihaza hem etkin
profile yazılır.

Şifreli profil: değiştirmek (kaydetmek), adını değiştirmek, silmek ya da
şifreyi kaldırmak için şifre sorulur. Şifrenin kendisi saklanmaz; yalnızca
tuzlanmış PBKDF2-SHA256 özeti tutulur. Ayar değerleri gizli bilgi olmadığı
için şifrelenmez; amaç profilin başkası tarafından değiştirilmesini
önlemektir. Şifre unutulursa profil yalnızca profiles.json silinerek
sıfırlanabilir.
"""

import hashlib
import hmac
import json
import os
import secrets

MAX_PROFILES = 3
PATH = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Lookie", "profiles.json")
_ITER = 200_000


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITER).hex()


class Profile:
    def __init__(self, pid, name, values=None, fresh=False, lock=None):
        self.id = pid
        self.name = name
        # None: henüz değer yok. fresh=True ise profil varsayılan değerlerle
        # başlar; değilse cihazdaki o anki ayarlar profile alınır (ilk profil).
        self.values = values
        self.fresh = fresh
        self.lock = lock  # {"salt": hex, "hash": hex} ya da None

    @property
    def locked(self):
        return bool(self.lock)

    def set_password(self, password):
        salt = secrets.token_bytes(16)
        self.lock = {"salt": salt.hex(), "hash": _hash(password, salt)}

    def check_password(self, password):
        if not self.lock:
            return True
        try:
            salt = bytes.fromhex(self.lock["salt"])
        except (KeyError, ValueError):
            return False
        return hmac.compare_digest(_hash(password, salt), self.lock.get("hash", ""))

    def to_json(self):
        return {"id": self.id, "name": self.name, "values": self.values, "fresh": self.fresh, "lock": self.lock}

    @classmethod
    def from_json(cls, d):
        values = d.get("values")
        if isinstance(values, dict):
            values = {str(k): float(v) for k, v in values.items() if isinstance(v, (int, float))}
        else:
            values = None
        lock = d.get("lock") if isinstance(d.get("lock"), dict) else None
        return cls(str(d["id"]), str(d.get("name") or "Profil"), values, bool(d.get("fresh")), lock)


class ProfileStore:
    def __init__(self, path=PATH, first_name="Profil 1"):
        self.path = path
        self.profiles = []
        self.active_id = None
        self._load()
        if not self.profiles:
            # İlk açılış: Profil 1, cihazdaki mevcut ayarlarla başlar.
            p = Profile(self._new_id(), first_name)
            self.profiles.append(p)
            self.active_id = p.id
            self.save()
        if self.get(self.active_id) is None:
            self.active_id = self.profiles[0].id

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.profiles = [Profile.from_json(d) for d in data.get("profiles", [])][:MAX_PROFILES]
            self.active_id = data.get("active")
        except Exception:
            self.profiles = []

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"active": self.active_id, "profiles": [p.to_json() for p in self.profiles]},
                          f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def _new_id(self):
        used = {p.id for p in self.profiles}
        i = 1
        while f"p{i}" in used:
            i += 1
        return f"p{i}"

    def get(self, pid):
        return next((p for p in self.profiles if p.id == pid), None)

    @property
    def active(self):
        return self.get(self.active_id)

    def can_add(self):
        return len(self.profiles) < MAX_PROFILES

    def next_name(self, template):
        """"Profil {n}" kalıbından kullanılmayan ilk adı üretir."""
        names = {p.name for p in self.profiles}
        n = 1
        while template.format(n=n) in names:
            n += 1
        return template.format(n=n)

    def add(self, name):
        if not self.can_add():
            return None
        p = Profile(self._new_id(), name, fresh=True)
        self.profiles.append(p)
        self.save()
        return p

    def remove(self, pid):
        if len(self.profiles) <= 1:
            return False
        self.profiles = [p for p in self.profiles if p.id != pid]
        if self.active_id == pid:
            self.active_id = self.profiles[0].id
        self.save()
        return True


def same_values(a, b):
    """İki ayar kümesi (cihaz %g ile yuvarlar) aynı mı?"""
    if not a or not b:
        return False
    for k, v in a.items():
        w = b.get(k)
        if w is None:
            continue
        if abs(float(v) - float(w)) > 1e-4 * max(1.0, abs(float(v))):
            return False
    return True
