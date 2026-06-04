@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "DEPLOY_DIR=%SCRIPT_DIR%qssh_deploy"
set "ZIP_NAME=%SCRIPT_DIR%qssh-deploy.zip"

echo [1/5] Cleaning previous deploy folder...
if exist "%DEPLOY_DIR%" rmdir /s /q "%DEPLOY_DIR%" 2>nul
if exist "%ZIP_NAME%" del /q "%ZIP_NAME%" 2>nul

echo [2/5] Creating deploy folder structure...
mkdir "%DEPLOY_DIR%\qssh"

echo [3/5] Copying source files...
copy /Y "%SCRIPT_DIR%qssh\__init__.py" "%DEPLOY_DIR%\qssh\" >nul
copy /Y "%SCRIPT_DIR%qssh\__main__.py" "%DEPLOY_DIR%\qssh\" >nul
copy /Y "%SCRIPT_DIR%qssh\agent.py" "%DEPLOY_DIR%\qssh\" >nul
copy /Y "%SCRIPT_DIR%qssh\client.py" "%DEPLOY_DIR%\qssh\" >nul
copy /Y "%SCRIPT_DIR%qssh\flush.py" "%DEPLOY_DIR%\qssh\" >nul
copy /Y "%SCRIPT_DIR%qssh\stop.py" "%DEPLOY_DIR%\qssh\" >nul
copy /Y "%SCRIPT_DIR%qssh\utils.py" "%DEPLOY_DIR%\qssh\" >nul

echo [4/5] Copying launcher scripts...
copy /Y "%SCRIPT_DIR%qssh.bat" "%DEPLOY_DIR%\" >nul
copy /Y "%SCRIPT_DIR%stop.bat" "%DEPLOY_DIR%\" >nul
copy /Y "%SCRIPT_DIR%reset.bat" "%DEPLOY_DIR%\" >nul

echo [5/5] Creating zip archive...
powershell -NoProfile -Command "Compress-Archive -Path '%DEPLOY_DIR%\*' -DestinationPath '%ZIP_NAME%' -Force"

rmdir /s /q "%DEPLOY_DIR%" 2>nul

for %%I in ("%ZIP_NAME%") do set "SIZE=%%~zI"
set /a SIZEKB=%SIZE% / 1024

echo.
echo Done! Created qssh-deploy.zip (%SIZEKB% KB)
echo.
echo To deploy on another machine:
echo   1. Extract qssh-deploy.zip to any folder
echo   2. Ensure Python 3.10+ is installed
echo   3. (Optional) pip install pexpect   (only needed on Linux/macOS)
echo   4. Run: qssh.bat user@host
echo.

endlocal
