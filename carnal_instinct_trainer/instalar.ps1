# Instalador automatico de CITrainer (UE4SS + mod) para Carnal Instinct.
param([switch]$Uninstall)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say($msg, $color = 'White') { Write-Host $msg -ForegroundColor $color }

function Find-GameExe {
    $roots = @('C:\Program Files (x86)\Steam\steamapps\common\CarnalInstinct')
    # Otras bibliotecas de Steam
    $vdf = 'C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf'
    if (Test-Path $vdf) {
        foreach ($m in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
            $roots += (Join-Path ($m.Groups[1].Value -replace '\\\\', '\') 'steamapps\common\CarnalInstinct')
        }
    }
    foreach ($r in $roots) {
        if (Test-Path $r) {
            $exe = Get-ChildItem $r -Recurse -Filter '*-Win64-Shipping.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($exe) { return $exe }
        }
    }
    Say 'No encuentro el juego. Elige la carpeta CarnalInstinct en la ventana que se abre.' Yellow
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Selecciona la carpeta de Carnal Instinct'
    if ($dlg.ShowDialog() -eq 'OK') {
        $exe = Get-ChildItem $dlg.SelectedPath -Recurse -Filter '*-Win64-Shipping.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($exe) { return $exe }
    }
    throw 'No se encontro el ejecutable *-Win64-Shipping.exe del juego.'
}

function Get-UE4SSUrl {
    $headers = @{ 'User-Agent' = 'CITrainer' }
    foreach ($api in @('https://api.github.com/repos/UE4SS-RE/RE-UE4SS/releases/tags/experimental-latest',
                       'https://api.github.com/repos/UE4SS-RE/RE-UE4SS/releases/latest')) {
        try {
            $rel = Invoke-RestMethod -Uri $api -Headers $headers
            $asset = $rel.assets | Where-Object { $_.name -match '^UE4SS.*\.zip$' -and $_.name -notmatch 'zDEV|zCustom|DEV' } | Select-Object -First 1
            if ($asset) { return $asset.browser_download_url }
        } catch { }
    }
    throw 'No se pudo descargar UE4SS (sin conexion o GitHub no responde).'
}

try {
    $exe = Find-GameExe
    $win64 = $exe.DirectoryName
    Say "Juego encontrado: $($exe.FullName)" Green

    if ($Uninstall) {
        foreach ($p in @('dwmapi.dll', 'ue4ss', 'UE4SS.dll', 'UE4SS-settings.ini', 'Mods', 'UE4SS.log')) {
            $full = Join-Path $win64 $p
            if (Test-Path $full) { Remove-Item $full -Recurse -Force }
        }
        Say 'Trainer desinstalado.' Green
        return
    }

    if (-not (Test-Path (Join-Path $win64 'dwmapi.dll'))) {
        $url = Get-UE4SSUrl
        $zip = Join-Path $env:TEMP 'ue4ss.zip'
        Say "Descargando UE4SS..." Cyan
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath $win64 -Force
        Remove-Item $zip -Force
    } else {
        Say 'UE4SS ya estaba instalado.' Cyan
    }

    $ue4ssDir = if (Test-Path (Join-Path $win64 'ue4ss')) { Join-Path $win64 'ue4ss' } else { $win64 }
    $mods = Join-Path $ue4ssDir 'Mods'
    New-Item -ItemType Directory -Force -Path $mods | Out-Null

    # Conservar config.lua si el usuario ya lo habia editado
    $dest = Join-Path $mods 'CITrainer'
    $oldCfg = Join-Path $dest 'Scripts\config.lua'
    $backup = $null
    if (Test-Path $oldCfg) { $backup = Get-Content $oldCfg -Raw }
    Copy-Item (Join-Path $here 'CITrainer') $mods -Recurse -Force
    if ($backup) { Set-Content -Path $oldCfg -Value $backup -NoNewline }

    # Activar en mods.txt si existe
    $modsTxt = Join-Path $mods 'mods.txt'
    if ((Test-Path $modsTxt) -and -not (Select-String -Path $modsTxt -Pattern '^CITrainer' -Quiet)) {
        Add-Content -Path $modsTxt -Value 'CITrainer : 1'
    }

    # Consola visible para ver los mensajes del trainer
    $ini = Join-Path $ue4ssDir 'UE4SS-settings.ini'
    if (Test-Path $ini) {
        $txt = Get-Content $ini -Raw
        $txt = $txt -replace '(?m)^GuiConsoleEnabled\s*=\s*\d', 'GuiConsoleEnabled = 1'
        $txt = $txt -replace '(?m)^GuiConsoleVisible\s*=\s*\d', 'GuiConsoleVisible = 1'
        Set-Content -Path $ini -Value $txt -NoNewline
    }

    Say ''
    Say 'LISTO. Abre el juego desde Steam y carga una partida.' Green
    Say 'F1 Dios | F2 Dinero | F3 Stamina | F4 Atributos | F5 XP'
    Say 'F6 Desbloquear todo | F7 Volcado | F8 Rastreador | F9 Velocidad'
} catch {
    Say ''
    Say "ERROR: $($_.Exception.Message)" Red
}
