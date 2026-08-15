@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

title Gesundheitsdashboard

echo ==========================================
echo   Gesundheitsdashboard
echo ==========================================
echo.

rem --- Python suchen ------------------------------------------------
rem Neueste zuerst: aeltere Versionen funktionieren zwar, bekommen von
rem pip aber aeltere Pakete.
rem
rem Bewusst NICHT ueber "py -3": der Launcher liefert dort die als
rem Standard eingetragene Version, die durchaus die aelteste sein kann.
set "PYTHON="
for %%V in (3.16 3.15 3.14 3.13 3.12 3.11 3.10 3.9) do (
    if not defined PYTHON (
        py -%%V -c "import sys" >nul 2>&1 && set "PYTHON=py -%%V"
    )
)

if not defined PYTHON (
    where python >nul 2>&1 && set "PYTHON=python"
)

if not defined PYTHON (
    echo FEHLER: Python wurde nicht gefunden.
    echo.
    echo Bitte Python installieren:
    echo   https://www.python.org/downloads/
    echo.
    echo WICHTIG: Bei der Installation den Haken bei
    echo "Add python.exe to PATH" setzen.
    echo.
    pause
    exit /b 1
)

rem --- Version pruefen ----------------------------------------------
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Die gefundene Python-Version ist zu alt.
    %PYTHON% --version
    echo.
    echo Benoetigt wird Python 3.9 oder neuer:
    echo   https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%V in ('%PYTHON% --version 2^>^&1') do set "PYVERSION=%%V"
echo Verwende !PYVERSION!
echo.

rem --- Vorhandene Umgebung pruefen ----------------------------------
rem Eine Umgebung aus einer frueheren, inzwischen entfernten Python-
rem Installation laesst sich nicht mehr starten - dann neu anlegen.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import streamlit" >nul 2>&1
    if errorlevel 1 (
        echo Die vorhandene Umgebung ist unvollstaendig und wird erneuert.
        echo.
        rmdir /s /q .venv
    )
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
        echo Besteht eine Internetverbindung?
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

".venv\Scripts\python.exe" -m streamlit run app\dashboard.py

if errorlevel 1 (
    echo.
    echo Das Dashboard wurde beendet oder konnte nicht starten.
    pause
)

endlocal
