@echo off
setlocal
cd /d "%~dp0"

title Gesundheitsdashboard

echo ==========================================
echo   Gesundheitsdashboard
echo ==========================================
echo.

rem --- Python suchen -------------------------------------------------
set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON (
    where python >nul 2>&1 && set "PYTHON=python"
)

if not defined PYTHON (
    echo FEHLER: Python wurde nicht gefunden.
    echo.
    echo Bitte Python 3.11 oder neuer installieren:
    echo   https://www.python.org/downloads/
    echo.
    echo WICHTIG: Bei der Installation den Haken bei
    echo "Add python.exe to PATH" setzen.
    echo.
    pause
    exit /b 1
)

rem --- Umgebung beim ersten Start einrichten -------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Erster Start - richte die Umgebung ein.
    echo Das dauert einige Minuten und passiert nur einmal.
    echo.
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo FEHLER: Die Umgebung konnte nicht angelegt werden.
        pause
        exit /b 1
    )
    echo Installiere benoetigte Pakete ...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo FEHLER: Die Pakete konnten nicht installiert werden.
        pause
        exit /b 1
    )
    echo Einrichtung abgeschlossen.
    echo.
)

rem --- Dashboard starten ---------------------------------------------
echo Starte das Dashboard - der Browser oeffnet sich gleich von selbst.
echo.
echo Zum Beenden dieses Fenster schliessen.
echo.

".venv\Scripts\python.exe" -m streamlit run app\dashboard.py --browser.gatherUsageStats false

if errorlevel 1 (
    echo.
    echo Das Dashboard wurde beendet oder konnte nicht starten.
    pause
)

endlocal
