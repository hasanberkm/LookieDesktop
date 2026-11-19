"""Açılış ekranı: logo sıvıyla dolar, ardından yazı soldan sağa açılır ve
yazıdaki gözler etrafına bakar.

Logo assets/lookie-logo.svg ile aynı ölçülerle PIL'de çizilir (SVG okuyucu
gerekmez). Değişmeyen katmanlar bir kez hazırlanır; her karede yalnızca sıvı
yüzeyi, göz bebekleri ve yazının açılma maskesi yeniden üretilir.
"""

import math
import time
import tkinter as tk

from PIL import Image, ImageChops, ImageDraw, ImageTk

TEAL = (0x14, 0xB8, 0xA6)
TEAL_DARK = (0x0F, 0x76, 0x6E)
TEAL_LIGHT = (0x2D, 0xD4, 0xBF)
INK = (0x13, 0x4E, 0x4A)
LED = (0xFD, 0xE6, 0x8A)
WHITE = (255, 255, 255)

SS = 4  # kenar yumuşatma için büyütme katı

# Zaman çizelgesi (saniye)
FILL_START, FILL_END = 0.10, 1.25      # simge sıvıyla dolar
OPEN_START, OPEN_END = 1.20, 2.15      # simge sola kayar, yazı açılır
FINISH = 3.05                          # animasyonun sonu
FADE = 0.25                            # kapanırken solma süresi

# Gözlerin baktığı yerler: (zaman, (x, y)) göz merkezine göre, logo biriminde.
# Son nokta logodaki duruş (yana ve hafif yukarı bakış).
LOOK = [
    (0.00, (0, 0)),
    (1.45, (0, 0)),
    (1.62, (-19, 0)),     # sola
    (1.85, (-19, 0)),
    (2.02, (-8, -16)),    # yukarı
    (2.22, (-8, -16)),
    (2.42, (19, 3)),      # sağa
    (2.62, (19, 3)),
    (2.80, (20, -5)),     # logodaki duruş
]

# Yükselen kabarcıklar: (x, başlangıç zamanı, yarıçap), simge biriminde (512).
BUBBLES = [(150, 0.15, 9), (330, 0.30, 7), (240, 0.45, 11), (400, 0.60, 6), (110, 0.70, 7), (290, 0.85, 8)]


def _ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _ease_cubic(t):
    t = min(1.0, max(0.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _mix(a, b, f):
    return tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _look(t):
    for (t0, a), (t1, b) in zip(LOOK, LOOK[1:]):
        if t <= t1:
            f = _ease((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
    return LOOK[-1][1]


class _Pen:
    """Birim koordinatlarla SS kat büyük resme çizer."""

    def __init__(self, w, h, scale, bg):
        self.s = scale * SS
        self.img = Image.new("RGBA", (max(1, round(w * scale)) * SS, max(1, round(h * scale)) * SS), bg)
        self.d = ImageDraw.Draw(self.img)

    def p(self, x, y):
        return (x * self.s, y * self.s)

    def circle(self, cx, cy, r, fill):
        x, y = self.p(cx, cy)
        r *= self.s
        self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def ellipse(self, cx, cy, rx, ry, fill):
        x, y = self.p(cx, cy)
        self.d.ellipse((x - rx * self.s, y - ry * self.s, x + rx * self.s, y + ry * self.s), fill=fill)

    def line(self, pts, color, width):
        xy = [self.p(x, y) for x, y in pts]
        self.d.line(xy, fill=color, width=max(1, round(width * self.s)), joint="curve")
        for x, y in pts:  # yuvarlak uçlar ve köşeler
            self.circle(x, y, width / 2, color)

    def arc(self, cx, cy, r, start, end, color, width):
        x, y = self.p(cx, cy)
        ro = (r + width / 2) * self.s
        self.d.arc((x - ro, y - ro, x + ro, y + ro), start, end, fill=color, width=max(1, round(width * self.s)))
        for a in (start, end):
            self.circle(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)), width / 2, color)

    def done(self):
        return self.img.reduce(SS)


def _stamp(layer, x, y, r, color, alpha=255):
    """Alt piksel konumunda kenarı yumuşak bir daire basar (x, y, r piksel)."""
    ix, iy = math.floor(x - r) - 1, math.floor(y - r) - 1
    n = math.ceil(2 * r) + 3
    patch = Image.new("RGBA", (n * SS, n * SS), color + (0,))
    cx, cy = (x - ix) * SS, (y - iy) * SS
    ImageDraw.Draw(patch).ellipse((cx - r * SS, cy - r * SS, cx + r * SS, cy + r * SS), fill=color + (alpha,))
    layer.alpha_composite(patch.reduce(SS), (ix, iy))


class Splash:
    """Ana pencerenin içinde, bütün içeriğin üstüne yerleşen bir katman.

    Pencere açılır açılmaz logonun boş hali görünür; arayüz bu katmanın
    arkasında kurulur. Kurulum bitince start() çağrılır ve animasyon oynar.
    Sonunda logo zemin rengine solar, katman kalkar ve asıl içerik görünür.
    Katmana tıklamak animasyonu atlar."""

    def __init__(self, root, ui, bg):
        self.root = root
        self.bg = _hex(bg) if isinstance(bg, str) else bg
        self.finished = False
        self.skip = False
        self.t0 = None

        k = self.k = 0.5 * ui          # logo birimi başına piksel (SVG yarı boyutta)
        self.ks = k * 0.5               # simge tasarım birimi (512) başına piksel
        self.isz = round(512 * self.ks)
        self.WX0, self.WY0 = 30, 30    # yazı katmanının logo içindeki başlangıcı
        self._prepare()

        self.pw = self.ph = 0
        self.photo = None
        self.label = tk.Label(root, borderwidth=0, highlightthickness=0, bg=bg, cursor="hand2")
        self.label.place(x=0, y=0, relwidth=1, relheight=1)
        self.label.bind("<Button-1>", lambda _e: setattr(self, "skip", True))
        self._show(self._frame_at(0.0))

    def redraw(self):
        """Pencere boyutu belli olduktan sonra ilk kareyi yeniden çizer."""
        self._show(self._frame_at(0.0))

    def lift(self):
        """Katmanı, sonradan kurulan arayüz öğelerinin üstüne taşır."""
        if not self.finished:
            self.label.lift()

    def start(self):
        """Arayüz hazır: animasyonu başlat."""
        self.lift()
        self.t0 = time.perf_counter()
        self._step()

    def _layout(self, pw, ph):
        # Bütün logo pencerenin ortasında; simge başta tek başına ortada durur.
        k = self.k
        self.pw, self.ph = pw, ph
        self.oy = (ph - 260 * k) / 2
        self.x_final = (pw - 907 * k) / 2
        self.x_start = (pw - self.isz) / 2

    def _frame_at(self, t):
        self.root.update_idletasks()
        pw, ph = max(1, self.label.winfo_width()), max(1, self.label.winfo_height())
        if (pw, ph) != (self.pw, self.ph):
            self._layout(pw, ph)
        frame = self._frame(min(t, FINISH))
        if t > FINISH:  # sonda logo zemin rengine solar
            frame = Image.blend(frame, Image.new("RGB", frame.size, self.bg), min(1.0, (t - FINISH) / FADE))
        return frame

    def _show(self, frame):
        if self.photo is None or (self.photo.width(), self.photo.height()) != frame.size:
            self.photo = ImageTk.PhotoImage(frame)
            self.label.configure(image=self.photo)
        else:
            self.photo.paste(frame)

    # ---------------------------------------------------------------- hazırlık
    def _prepare(self):
        ks, k = self.ks, self.k
        # Simge, göz bebekleri olmadan.
        pen = _Pen(512, 512, ks, TEAL + (0,))
        pen.d.rounded_rectangle((0, 0, 512 * pen.s, 512 * pen.s), radius=116 * pen.s, fill=TEAL + (255,))
        pen.arc(256, 270, 140, 180, 360, TEAL_DARK, 28)
        pen.d.rounded_rectangle((*pen.p(210, 104), *pen.p(302, 154)), radius=17 * pen.s, fill=TEAL_DARK)
        pen.circle(282, 129, 8, LED)
        pen.ellipse(204, 304, 48, 56, WHITE)
        pen.ellipse(308, 304, 48, 56, WHITE)
        pts = []
        for i in range(17):  # gülümseme (ikinci derece Bezier)
            t = i / 16
            pts.append(((1 - t) ** 2 * 234 + 2 * (1 - t) * t * 256 + t * t * 278,
                        (1 - t) ** 2 * 386 + 2 * (1 - t) * t * 402 + t * t * 386))
        pen.line(pts, INK, 10)
        self.icon = pen.done()
        self.icon_alpha = self.icon.getchannel("A")

        # Simgenin boş hali: logo renginde çok hafif bir zemin.
        ghost_c = _mix(self.bg, TEAL, 0.14)
        g = Image.new("RGBA", self.icon.size, ghost_c + (255,))
        g.putalpha(self.icon_alpha)
        self.ghost = g
        self.back_fill = Image.new("RGBA", self.icon.size, TEAL_LIGHT + (255,))

        # Yazı, göz bebekleri olmadan. Koordinatlar SVG'deki yazı grubuyla aynı.
        ox, oy = self.WX0, self.WY0
        pen = _Pen(640, 200, k, TEAL + (0,))
        def P(x, y): return (x - ox, y - oy)
        pen.line([P(60, 50), P(60, 210), P(140, 210)], TEAL, 24)
        for cx in (208, 318):
            pen.circle(*P(cx, 165), 57, TEAL)
            pen.circle(*P(cx, 165), 33, WHITE)
        pen.line([P(398, 50), P(398, 210)], TEAL, 24)
        pen.line([P(398, 170), P(458, 120)], TEAL, 24)
        pen.line([P(420, 152), P(462, 210)], TEAL, 24)
        pen.line([P(508, 120), P(508, 210)], TEAL, 24)
        pen.circle(*P(508, 76), 15, TEAL)
        pen.line([P(555, 165), P(645, 165)], TEAL, 24)
        pen.arc(*P(600, 165), 45, 45, 360, TEAL, 24)
        self.word = pen.done()
        self.word_alpha = self.word.getchannel("A")

        # Yazının açılma kenarındaki yumuşak geçiş (sağa doğru 255 -> 0).
        self.soft = max(2, round(60 * k))
        self.ramp = Image.linear_gradient("L").rotate(90).resize((self.soft, 1))

    # ------------------------------------------------------------------ kareler
    def _liquid_masks(self, t, level):
        """Ön ve arka dalganın altını dolduran maskeler (simge boyutunda)."""
        n = self.isz * SS
        s = self.ks * SS
        base = 532 - level * 572           # yüzey alttan başlar, üstten taşar
        amp = 18 * min(1.0, level * 5) * (1 - level) ** 0.7
        masks = []
        for lift, wl, speed, phase in ((0, 250, 6.5, 0.0), (12, 210, -5.0, 1.7)):
            pts = []
            for i in range(0, 33):
                x = i * 512 / 32
                y = base - lift + amp * math.sin(2 * math.pi * x / wl + speed * t + phase)
                pts.append((x * s, y * s))
            pts += [(n, n), (0, n)]
            m = Image.new("L", (n, n), 0)
            ImageDraw.Draw(m).polygon(pts, fill=255)
            masks.append(ImageChops.multiply(m.reduce(SS), self.icon_alpha))
        return masks

    def _frame(self, t):
        frame = Image.new("RGB", (self.pw, self.ph), self.bg)
        k, ks = self.k, self.ks
        look = _look(t)

        # Yazı açılırken simge ortadan sola kayar.
        o = _ease_cubic((t - OPEN_START) / (OPEN_END - OPEN_START))
        ix = round(self.x_start + (self.x_final - self.x_start) * o)
        iy = round(self.oy + 2 * k)

        # Yazı: simgenin arkasından hafifçe kayarak, soldan sağa açılır.
        if o > 0:
            word = self.word.copy()
            for cx in (208, 318):
                px = (cx + look[0] - self.WX0) * k
                py = (165 + look[1] - self.WY0) * k
                _stamp(word, px, py, 19 * k, INK)
                _stamp(word, px + 6 * k, py - 7 * k, 5 * k, WHITE)
            ww, wh = word.size
            edge = round(o * (ww + self.soft))
            row = Image.new("L", (ww, 1), 0)
            if edge - self.soft > 0:
                row.paste(255, (0, 0, edge - self.soft, 1))
            row.paste(ImageChops.invert(self.ramp), (edge - self.soft, 0))
            wx = round(self.x_final + (250 + self.WX0) * k - (1 - o) * 40 * k)
            # Yazı simgenin içinden çıkıyormuş gibi görünsün: simgenin
            # solunda kalan kısmı gizlenir (gerisini simge zaten örter).
            hide = ix + self.isz // 2 - wx
            if hide > 0:
                row.paste(0, (0, 0, min(ww, hide), 1))
            mask = ImageChops.multiply(row.resize((ww, wh), Image.NEAREST), self.word_alpha)
            word.putalpha(mask)
            frame.paste(word, (wx, round(self.oy + self.WY0 * k)), word)

        # Simge: göz bebekleri ve kabarcıklarla birlikte, sıvı yüzeyine kadar.
        icon = self.icon.copy()
        for cx in (204, 308):
            px, py = (cx + look[0]) * ks, (304 + look[1]) * ks
            _stamp(icon, px, py, 23 * ks, INK)
            _stamp(icon, px + 7 * ks, py - 8 * ks, 7 * ks, WHITE)

        level = _ease((t - FILL_START) / (FILL_END - FILL_START))
        if level < 1:
            fade = 1 - _ease((level - 0.7) / 0.3)
            for bx, bt, br in BUBBLES:
                age = t - bt
                if 0 < age < 1.2 and fade > 0:
                    by = 540 - age * 380
                    wob = 6 * math.sin(age * 9 + bx)
                    _stamp(icon, (bx + wob) * ks, by * ks, br * ks, WHITE, round(110 * fade))
            front, back = self._liquid_masks(t, level)
            frame.paste(self.ghost, (ix, iy), self.ghost)
            self.back_fill.putalpha(back)
            frame.paste(self.back_fill, (ix, iy), self.back_fill)
            icon.putalpha(front)
        frame.paste(icon, (ix, iy), icon)
        return frame

    # ---------------------------------------------------------------- oynatma
    def _step(self):
        if self.finished:
            return
        t = time.perf_counter() - self.t0
        if self.skip:  # tıklanınca solma aşamasına atla
            self.skip = False
            self.t0 -= max(0.0, FINISH - t)
            t = max(t, FINISH)
        if t >= FINISH + FADE:
            self.close()
            return
        try:
            self._show(self._frame_at(t))
        except Exception:
            # Çizim bir nedenle başarısız olursa asıl içerik yine de görünsün.
            self.close()
            raise
        self.root.after(15, self._step)

    def close(self):
        """Katmanı kaldırır ve asıl içeriği gösterir."""
        if self.finished:
            return
        self.finished = True
        try:
            self.label.destroy()
        except tk.TclError:
            pass
