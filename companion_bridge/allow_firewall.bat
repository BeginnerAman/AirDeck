@echo off
:: AirDeck Pro — Automated Windows Firewall Rule Installer
:: Requires Administrator privileges.
echo ============================================================
echo   AirDeck Pro - Windows Firewall Configuration
echo ============================================================
echo.
echo Adding inbound firewall rule for ports 8765-8775 (TCP)...

netsh advfirewall firewall add rule name="AirDeck Pro" dir=in action=allow protocol=TCP localport=8765-8775 profile=any

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] AirDeck Pro firewall rule added successfully!
    echo Your mobile phone can now connect to AirDeck on this Wi-Fi.
) else (
    echo.
    echo [ERROR] Failed to add firewall rule. Please right-click this script
    echo and choose 'Run as administrator'.
)
echo.
pause
