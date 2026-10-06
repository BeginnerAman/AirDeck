@echo off
title AirDeck Pro Companion Suite
cd /d "%~dp0"
cls
echo ================================================================
echo                Starting AirDeck Pro Server...
echo ================================================================
echo.
python server.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ================================================================
    echo [ERROR] AirDeck stopped unexpectedly.
    echo ================================================================
    pause
)
