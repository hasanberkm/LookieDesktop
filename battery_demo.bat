@echo off
rem Pil gostergesi testi: yuzde 100den 0a azalir, sonra sarj animasyonu oynar.
rem Hizi degistirmek icin: battery_demo.bat 60   (adim basina ms, varsayilan 150)
cd /d "%~dp0"
set LOOKIE_BATTERY_DEMO=1
if not "%~1"=="" set LOOKIE_BATTERY_DEMO_MS=%~1
if exist dist\Lookie.exe (start "" dist\Lookie.exe) else (start "" pythonw lookie_app.py)
