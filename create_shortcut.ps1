# Crée un raccourci sur le bureau pour lancer launcher.pyw avec pythonw.exe

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LauncherPath = Join-Path $ProjectDir "launcher.pyw"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopDir "Stream Deck.lnk"

# Recherche de pythonw.exe (même environnement que python.exe courant)
$PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    Write-Error "python.exe introuvable dans le PATH. Installez Python ou ajustez le script."
    exit 1
}
$PythonwExe = Join-Path (Split-Path $PythonExe) "pythonw.exe"
if (-not (Test-Path $PythonwExe)) {
    Write-Error "pythonw.exe introuvable a cote de python.exe ($PythonExe)."
    exit 1
}

# Recherche d'une icone .ico dans le dossier du projet
$IconFile = Get-ChildItem -Path $ProjectDir -Filter "*.ico" -ErrorAction SilentlyContinue | Select-Object -First 1

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonwExe
$Shortcut.Arguments = "`"$LauncherPath`""
$Shortcut.WorkingDirectory = $ProjectDir

if ($IconFile) {
    $Shortcut.IconLocation = $IconFile.FullName
} else {
    $Shortcut.IconLocation = "$PythonwExe,0"
}

$Shortcut.Save()

Write-Host "Raccourci cree : $ShortcutPath"
Write-Host "Cible : $PythonwExe `"$LauncherPath`""
Write-Host "Repertoire de travail : $ProjectDir"
