@echo off
REM BOBO Processor Windows Batch Wrapper
REM Simple batch file for running BOBO processor with basic error handling

setlocal enabledelayedexpansion

REM Set working directory to script location
cd /d "%~dp0"

REM Log file with timestamp
set timestamp=%date:~-4,4%-%date:~-10,2%-%date:~-7,2%_%time:~0,2%-%time:~3,2%-%time:~6,2%
set timestamp=!timestamp: =0!
set logfile=..\logs\bobo_wrapper_!timestamp!.log

REM Ensure logs directory exists
if not exist "..\logs" mkdir "..\logs"

echo %date% %time%: Starting BOBO processor... >> !logfile!
echo %date% %time%: Starting BOBO processor...

REM Check if .env file exists
if not exist ".env" (
    echo %date% %time%: ERROR - .env file not found. Please create from .env_safe template. >> !logfile!
    echo ERROR: .env file not found. Please create from .env_safe template.
    exit /b 1
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo %date% %time%: ERROR - Python not found in PATH >> !logfile!
    echo ERROR: Python not found in PATH
    exit /b 1
)

REM Check if bobo_processor.py exists
if not exist "bobo_processor.py" (
    echo %date% %time%: ERROR - bobo_processor.py not found >> !logfile!
    echo ERROR: bobo_processor.py not found
    exit /b 1
)

REM Run the processor using virtual environment
echo %date% %time%: Executing myenv\Scripts\python bobo_processor.py >> !logfile!
myenv\Scripts\python bobo_processor.py >> !logfile! 2>&1

if errorlevel 1 (
    echo %date% %time%: BOBO processor failed with error level !errorlevel! >> !logfile!
    echo BOBO processor failed with error level !errorlevel!
    exit /b !errorlevel!
) else (
    echo %date% %time%: BOBO processor completed successfully >> !logfile!
    echo BOBO processor completed successfully
)

REM Clean up old wrapper logs (keep last 7 days)
forfiles /p "..\logs" /s /m "bobo_wrapper_*.log" /d -7 /c "cmd /c del @path" >nul 2>&1

echo %date% %time%: Wrapper finished >> !logfile!
endlocal
exit /b 0 