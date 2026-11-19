"""Windows'un başlık çubuğunu kaldırır, pencerenin geri kalanını korur.

Pencere çerçevesi (kenarlardan boyutlandırma, ekran kenarına yaslama, gölge,
Windows 11'in yuvarlak köşeleri, görev çubuğu, simge durumuna küçültme)
Windows'ta kalır; yalnızca başlık çubuğunun alanı uygulamaya verilir.
Uygulama kendi başlık alanını ve düğmelerini çizer, set_caption() ile bu
alanı bildirir. Windows o alanı başlık çubuğu sayar; böylece sürükleme,
çift tıklayıp büyütme ve sağ tık menüsü kendiliğinden çalışır.
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


user32.SetWindowLongPtrW.restype = ctypes.c_void_p
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
user32.CallWindowProcW.restype = LRESULT
user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]

class WINDOWPOS(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("hwndInsertAfter", wintypes.HWND), ("x", ctypes.c_int),
                ("y", ctypes.c_int), ("cx", ctypes.c_int), ("cy", ctypes.c_int), ("flags", wintypes.UINT)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", ctypes.c_void_p), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


gdi32 = ctypes.windll.gdi32
gdi32.CreateSolidBrush.restype = ctypes.c_void_p
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]
user32.SetClassLongPtrW.restype = ctypes.c_void_p
user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

GWLP_WNDPROC = -4
WM_WINDOWPOSCHANGING = 0x0046
SWP_NOSIZE = 0x0001
_cover_class = None
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
HTCLIENT, HTCAPTION = 1, 2
HTTOP, HTTOPLEFT, HTTOPRIGHT = 12, 13, 14
SWP_FRAMECHANGED = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # boyut/konum/sıra değişmeden


class CustomFrame:
    def __init__(self, root):
        self.cap_bottom = 0    # başlık alanının alt sınırı (pencere içi piksel)
        self.exclude = []      # başlık alanındaki düğmeler: (x0, y0, x1, y1)
        root.update_idletasks()
        self.hwnd = user32.GetParent(root.winfo_id())
        if not self.hwnd:
            raise OSError("pencere tutamacı yok")
        dpi = root.winfo_fpixels("1i") / 96.0
        self.grip = max(4, round(5 * dpi))  # üst kenarda boyutlandırma payı
        self._proc = WNDPROC(self._wndproc)  # geri çağrı yaşadığı sürece tutulmalı
        self._old = user32.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC,
                                             ctypes.cast(self._proc, ctypes.c_void_p))
        user32.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, SWP_FRAMECHANGED)
        try:
            self._create_cover()
        except Exception:
            self.cover = None
        # Büyütme/küçültme animasyonunu kapat: Windows animasyonu pencerenin yeni
        # boyuttaki görüntüsüyle oynatıyor, Tk ise yeni boyuttaki bileşenleri o
        # anda henüz çizmemiş oluyor; animasyon boyunca bileşenler siyah
        # görünüyordu. Animasyonsuz geçişte bu ara kare oluşmaz.
        try:
            off = ctypes.c_int(1)  # DWMWA_TRANSITIONS_FORCEDISABLED
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self.hwnd, 3, ctypes.byref(off), ctypes.sizeof(off))
        except Exception:
            pass

    # -- boyut değişiminde örtü --------------------------------------------------
    # Pencere büyüyüp küçülünce Windows pencerenin çizim yüzeyini sıfırdan
    # kurar; Tk bileşenleri tek tek çizdiği için ~0,2 sn boyunca henüz
    # çizilmemiş yerler siyah görünür. Büyük bir boyut değişimi başlarken
    # pencerenin üstüne zemin renginde bir örtü konur (Windows'un kendi
    # penceresi: anında çizilir), uygulama çizimi bitirince örtüyü söndürür.
    def _create_cover(self):
        global _cover_class
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        if _cover_class is None:
            wc = WNDCLASSW()
            wc.lpfnWndProc = ctypes.cast(user32.DefWindowProcW, ctypes.c_void_p).value
            wc.hInstance = hinst
            wc.lpszClassName = "LookieResizeCover"
            user32.RegisterClassW(ctypes.byref(wc))
            _cover_class = wc
        # WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT, WS_POPUP
        self.cover = user32.CreateWindowExW(0x80000 | 0x80 | 0x08000000 | 0x20, "LookieResizeCover", None,
                                            0x80000000, 0, 0, 0, 0, self.hwnd, None, hinst, None)
        self.cover_brush = None
        self.cover_on = False

    def set_cover_color(self, color):
        """Örtünün rengi (uygulamanın zemin rengi, "#rrggbb")."""
        if not getattr(self, "cover", None):
            return
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        brush = gdi32.CreateSolidBrush(r | (g << 8) | (b << 16))
        user32.SetClassLongPtrW(self.cover, -10, brush)  # GCLP_HBRBACKGROUND
        if self.cover_brush:
            gdi32.DeleteObject(self.cover_brush)
        self.cover_brush = brush
        user32.InvalidateRect(self.cover, None, True)

    def _show_cover(self, x, y, cx, cy):
        if not getattr(self, "cover", None) or not self.cover_brush:
            return
        user32.SetLayeredWindowAttributes(self.cover, 0, 255, 2)  # LWA_ALPHA
        # SWP_NOACTIVATE | SWP_SHOWWINDOW; sahibi ana pencere olduğu için onun üstünde durur
        user32.SetWindowPos(self.cover, None, x, y, cx, cy, 0x0010 | 0x0040)
        self.cover_on = True

    def cover_alpha(self, alpha):
        """Örtünün saydamlığı (0-255); 0'da gizlenir."""
        if not getattr(self, "cover", None):
            return
        if alpha <= 0:
            user32.ShowWindow(self.cover, 0)  # SW_HIDE
            self.cover_on = False
        else:
            user32.SetLayeredWindowAttributes(self.cover, 0, int(alpha), 2)

    def set_caption(self, bottom, exclude):
        """Başlık alanını bildirir. Windows mesajı işlenirken yalnızca bu
        sayılara bakılır; Tk'ye o sırada dokunulmaz."""
        self.cap_bottom = bottom
        self.exclude = list(exclude)

    def _is_caption(self, x, y):
        if y >= self.cap_bottom:
            return False
        return not any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in self.exclude)

    def zoomed(self):
        return bool(user32.IsZoomed(self.hwnd))

    def _frame_y(self):
        # Büyütülmüş pencere ekranın biraz dışına taşar; üst kenarı içeri al.
        return user32.GetSystemMetrics(33) + user32.GetSystemMetrics(92)  # SM_CYFRAME + SM_CXPADDEDBORDER

    def _wndproc(self, hwnd, msg, wp, lp):
        try:
            if msg == WM_NCCALCSIZE and wp:
                p = ctypes.cast(lp, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
                top = p.rgrc[0].top
                r = user32.CallWindowProcW(self._old, hwnd, msg, wp, lp)
                # Varsayılan hesap kenarları bırakıp üstten başlık kadar keser;
                # üst kenarı eski yerine koymak başlığı kaldırır.
                p.rgrc[0].top = top + (self._frame_y() if user32.IsZoomed(hwnd) else 0)
                return r
            if msg == WM_WINDOWPOSCHANGING and getattr(self, "cover", None):
                wp_ = ctypes.cast(lp, ctypes.POINTER(WINDOWPOS)).contents
                if (not wp_.flags & SWP_NOSIZE and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd)
                        and wp_.x > -30000 and wp_.cx > 0 and wp_.cy > 0):
                    rc = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rc))
                    # Yalnızca büyük sıçramalar (büyütme, geri alma, yaslama); kenardan
                    # sürükleyerek boyutlandırmanın küçük adımları değil.
                    if abs(wp_.cx - (rc.right - rc.left)) > 80 or abs(wp_.cy - (rc.bottom - rc.top)) > 80:
                        self._show_cover(wp_.x, wp_.y, wp_.cx, wp_.cy)
            if msg == WM_NCHITTEST:
                r = user32.CallWindowProcW(self._old, hwnd, msg, wp, lp)
                if r != HTCLIENT:
                    return r
                pt = wintypes.POINT(ctypes.c_short(lp & 0xFFFF).value, ctypes.c_short((lp >> 16) & 0xFFFF).value)
                user32.ScreenToClient(hwnd, ctypes.byref(pt))
                if not user32.IsZoomed(hwnd) and pt.y < self.grip:
                    rc = wintypes.RECT()
                    user32.GetClientRect(hwnd, ctypes.byref(rc))
                    if pt.x < self.grip * 3:
                        return HTTOPLEFT
                    if pt.x >= rc.right - self.grip * 3:
                        return HTTOPRIGHT
                    return HTTOP
                if self._is_caption(pt.x, pt.y):
                    return HTCAPTION
                return r
        except Exception:
            pass
        return user32.CallWindowProcW(self._old, hwnd, msg, wp, lp)
