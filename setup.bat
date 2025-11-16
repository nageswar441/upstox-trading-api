@echo off
REM upstox-trading-api setup.bat for Windows

REM Create virtual environment if not exists
IF NOT EXIST venv (
    echo [1/5] Creating Python virtual environment...
    python -m venv venv
) ELSE (
    echo [1/5] Virtual environment already exists.
)

REM Activate the virtual environment
call venv\Scripts\activate.bat
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment.
    exit /b 1
)

REM Upgrade pip
echo [2/5] Upgrading pip...
python -m pip install --upgrade pip

REM Install required dependencies
echo [3/5] Installing Python dependencies...
IF EXIST requirements.txt (
    pip install -r requirements.txt
) ELSE (
    echo requirements.txt not found! Please add it.
    exit /b 1
)

REM Run profile_manager.py to create environment profiles if needed
echo [4/5] Creating environment profiles (if missing)...
python profile_manager.py create

REM Echo finish
echo [5/5] Setup completed. Default profile is dev (if not changed).

REM Done!
pause
