@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment was not found.
    echo.
    echo Create it once with:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Starting AI Report Assistant...
echo Press Ctrl+C in this window to stop the app.
echo.

".venv\Scripts\python.exe" -m streamlit run app.py %*

if errorlevel 1 (
    echo.
    echo The app has stopped. Press any key to close this window.
    pause
)

endlocal
