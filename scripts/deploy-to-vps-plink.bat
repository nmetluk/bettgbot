@echo off
setlocal enabledelayedexpansion

REM Скрипт деплоя Betting Bot на VPS через PuTTY Plink (Windows).
REM Использование: deploy-to-vps-plink.bat [vps-ip] [ssh-user] [ssh-password]

set VPS_IP=%1
set SSH_USER=%2
set SSH_PASS=%3

if "%VPS_IP%"=="" set VPS_IP=5.188.88.78
if "%SSH_USER%"=="" set SSH_USER=root
if "%SSH_PASS%"=="" (
    echo Usage: %0 [vps-ip] [ssh-user] [ssh-password]
    exit /b 1
)

echo ==========================================
echo  Deploying Betting Bot to VPS
echo  IP: %VPS_IP%
echo  SSH: %SSH_USER%
echo  Port: 8888 (no TLS)
echo ==========================================
echo.

set PLINK=C:\Program Files\PuTTY\plink.exe
set PSFTP=C:\Program Files\PuTTY\pscp.exe

REM Step 1: Install Docker on VPS
echo -^> Step 1: Installing Docker on VPS...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "set -e; if ! command -v docker ^&> /dev/null; then sudo apt update ^&^& sudo apt install -y docker.io docker-compose-v2-plugin git make ^&^& sudo systemctl enable docker ^&^& sudo systemctl start docker ^&^& echo 'Docker installed'; else echo 'Docker already installed'; fi; docker --version; docker compose version"

echo.
echo -^> Step 2: Cloning repository...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "set -e; if [ -d /opt/bettgbot ]; then echo 'Repo exists, updating...'; cd /opt/bettgbot; git fetch origin; git reset --hard origin/main; git pull origin main; else sudo mkdir -p /opt/bettgbot; sudo chown $USER:$USER /opt/bettgbot; git clone https://github.com/nmetluk/bettgbot.git /opt/bettgbot; fi; cd /opt/bettgbot; git log --oneline -1"

echo.
echo -^> Step 3: Copying .env to VPS...
%PSFTP% -pw %SSH_PASS% infra/.env %SSH_USER%@%VPS_IP%:/opt/bettgbot/infra/.env
echo .env copied

echo.
echo -^> Step 4: Building Docker images on VPS...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "cd /opt/bettgbot ^&^& make prod.nodomain.build"

echo.
echo -^> Step 5: Starting services...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "cd /opt/bettgbot ^&^& make prod.nodomain.up"

echo.
echo -^> Step 6: Checking health...
timeout /t 5 /nobreak
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "curl -s http://127.0.0.1:8888/healthz ^&^& echo ' Healthz OK'"

echo.
echo ==========================================
echo Deploy completed!
echo ==========================================
echo.
echo URLs:
echo   Admin:  http://%VPS_IP%:8888/admin
echo   Healthz:  http://%VPS_IP%:8888/healthz
echo.
echo Next steps:
echo   1. Create admin user:
echo      ssh %SSH_USER%@%VPS_IP%
echo      cd /opt/bettgbot
echo      docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml exec web python scripts/create_admin.py --login admin --password 'YourPassword'
echo.

endlocal
