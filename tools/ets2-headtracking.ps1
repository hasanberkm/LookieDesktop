# ETS2 / ATS: Lookie'yi mutlak (1:1) kafa takibi olarak bagla.
#
# Neden gerekli: ETS2'nin "Look left/right" / "Look up/down" joystick eksenleri
# HIZ kontrolu (looklranaspd = eksen * c_jrspeed). Kafa 5 derece donukken bile
# eksen sifir olmadigi icin kamera surekli doner -> tam tur.
# Oyunun TrackIR yolu (headtryaw/headtrpitch) ise MUTLAK aci bekler. Bu betik
# controls.sii icindeki trackir mix'lerini Lookie'nin RX/RY eksenine
# baglar ve hiz tabanli look mix'lerini sifirlar. PC'ye ek yazilim gerekmez.
#
# KULLANIM: Oyunu KAPAT (acikken oyun dosyayi cikista ezer), sonra:
#   powershell -ExecutionPolicy Bypass -File tools\ets2-headtracking.ps1
# Geri almak icin olusan controls.sii.bak_headtracker dosyasini geri kopyala.
# (Yedek adi projenin eski adindan kalma; degistirilirse betigi daha once
# calistirmis birinin orijinal yedegi, yamali dosyanin kopyasiyla ezilir.)

param(
  # Ilk once otomatik bulunur (Lookie'nin bagli oldugu "joyN").
  [string]$ProfileDir = "",
  [string]$Joy = "",
  # config.h YAW_RANGE_DEG ile ayni olmali: tam eksen = oyunda bu kadar derece bakis.
  [double]$YawRangeDeg = 180.0,
  [double]$PitchRangeDeg = 60.0,
  # Oyundaki yon ters ise -InvertYaw / -InvertPitch ile tekrar calistir.
  [switch]$InvertYaw,
  [switch]$InvertPitch,
  [switch]$Ats,    # American Truck Simulator profili
  [switch]$Force   # oyun acik kontrolunu atla (sadece kopya dosyada test icin)
)

$ErrorActionPreference = "Stop"

$proc = if ($Ats) { "amtrucks" } else { "eurotrucks2" }
if (-not $Force -and (Get-Process $proc -ErrorAction SilentlyContinue)) {
  throw "Oyun acik. Once oyunu kapat (oyun cikarken controls.sii'yi ezer)."
}

if (-not $ProfileDir) {
  $root = Join-Path ([Environment]::GetFolderPath("MyDocuments")) $(if ($Ats) { "American Truck Simulator" } else { "Euro Truck Simulator 2" })
  $file = Get-ChildItem -Path (Join-Path $root "steam_profiles"), (Join-Path $root "profiles") -Filter controls.sii -Recurse -Depth 1 -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $file) { throw "controls.sii bulunamadi, -ProfileDir ver." }
  $ProfileDir = $file.DirectoryName
}
$path = Join-Path $ProfileDir "controls.sii"
$text = [IO.File]::ReadAllText($path)

# Lookie'nin joyN adi: mevcut look baglantisindan (j_look_lr `joy2.rx`)
# ya da daha once bu betigin yazdigi trackiryaw satirindan al.
if (-not $Joy) {
  if ($text -match 'input j_look_lr `(joy\d*)\.rx`') { $Joy = $Matches[1] }
  elseif ($text -match 'mix trackiryaw `-?\(?(joy\d*)\.rx') { $Joy = $Matches[1] }
  else { throw "Lookie eksenini bulamadim. Oyunda once Look left/right'i cihazin RX eksenine bagla ya da -Joy joy2 ver." }
}

$inv = [Globalization.CultureInfo]::InvariantCulture
$yawK   = ($YawRangeDeg   * [Math]::PI / 180.0).ToString("0.000000", $inv)
$pitchK = ($PitchRangeDeg * [Math]::PI / 180.0).ToString("0.000000", $inv)
# ETS2'nin kendi look mix'i -eksen kullaniyor (looklranaraw = -j_look_lr),
# ayni isareti koruyoruz; ters ise -Invert* bunu cevirir.
$ys = if ($InvertYaw)   { "" } else { "-" }
$ps = if ($InvertPitch) { "" } else { "-" }

$repl = [ordered]@{
  # Input baglantilarini bosaltmak ise yaramiyor (oyun profili yuklerken
  # geri yaziyor); onun yerine joystick hiz mix'lerini sifirla. Klavye ile
  # bakis (looklrdigspd) calismaya devam eder.
  'mix looklranaraw' = '`0`'
  'mix lookudanaraw' = '`0`'
  'mix trackiron'    = '`1`'
  'mix trackiryaw'   = "``$ys$Joy.rx?0 * $yawK``"
  'mix trackirpitch' = "``$ps$Joy.ry?0 * $pitchK``"
  'mix trackirroll'  = '`0`'
  'mix trackirx'     = '`0`'
  'mix trackiry'     = '`0`'
  'mix trackirz'     = '`0`'
}
foreach ($k in $repl.Keys) {
  $pattern = '(config_lines\[\d+\]: "' + [regex]::Escape($k) + ' )`[^"]*`(")'
  if ($text -notmatch $pattern) { throw "controls.sii icinde '$k' satiri yok." }
  $val = $repl[$k]
  $text = [regex]::Replace($text, $pattern, { param($m) $m.Groups[1].Value + $val + $m.Groups[2].Value })
}

$bak = "$path.bak_headtracker"
if (-not (Test-Path $bak)) { Copy-Item $path $bak }
[IO.File]::WriteAllText($path, $text)

Write-Host "Yamalandi: $path"
Write-Host "  Lookie = $Joy, yaw $YawRangeDeg deg, pitch $PitchRangeDeg deg"
Write-Host "  Yedek: $bak"
