@echo off
title Limpiador de Carpetas Corruptas de WhatsApp
chcp 65001 >nul
echo ========================================================
echo   Limpieza de Carpetas Temporales y Corruptas WhatsApp
echo ========================================================
echo.

:: Comprobar privilegios de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Solicitando permisos de Administrador para desbloquear archivos...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo [OK] Ejecutando con permisos de Administrador.
cd /d "%~dp0"

:: Cerrar procesos huerfanos de chromedriver si existieran
taskkill /F /IM chromedriver.exe >nul 2>&1

set CARPETAS=test_profile whatsapp_profile whatsapp_profile_clean whatsapp_profile_clean_clean whatsapp_session_fresh whatsapp_test_nocreate temp_test_chrome_dir whatsapp_session_v1

for %%D in (%CARPETAS%) do (
    if exist "%%D" (
        echo Procesando carpeta: %%D...
        takeown /f "%%D" /r /d s >nul 2>&1
        icacls "%%D" /grant:r Administrators:(OI)(CI)F /t /c /q >nul 2>&1
        icacls "%%D" /grant:r "%USERNAME%":(OI)(CI)F /t /c /q >nul 2>&1
        icacls "%%D" /grant:r *S-1-1-0:(OI)(CI)F /t /c /q >nul 2>&1
        rd /s /q "%%D" >nul 2>&1
        if exist "%%D" (
            echo   [REINTENTANDO] Forzando eliminacion de archivos individuales en %%D...
            del /f /s /q /a "%%D\*.*" >nul 2>&1
            rd /s /q "%%D" >nul 2>&1
        )
        if exist "%%D" (
            echo   [AVISO] No se pudo eliminar completamente %%D (archivo en uso por antivirus).
        ) else (
            echo   [EXITO] %%D eliminada correctamente.
        )
    )
)

echo.
echo ========================================================
echo   Limpieza completada.
echo ========================================================
echo Puede cerrar esta ventana.
timeout /t 5 >nul
