@echo off
rem Lookie.exe'yi olusturur (sonuc: app\dist\Lookie.exe).
rem Gereksinimler: Python 3.10+ ve "python -m pip install -r requirements.txt"
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name Lookie ^
  --icon icon.ico ^
  --add-data "icon.png;." ^
  --add-data "fonts;fonts" ^
  --collect-data sv_ttk ^
  --collect-submodules winrt ^
  --hidden-import pystray._win32 ^
  lookie_app.py
