@echo off
setlocal enabledelayedexpansion

set VPS_IP=5.188.88.78
set SSH_USER=root
set SSH_PASS=asd98$^!NmN

set PLINK="C:\Program Files\PuTTY\plink.exe"
set PSCP="C:\Program Files\PuTTY\pscp.exe"

echo ==========================================
echo  Deploying Betting Bot to VPS
echo  IP: %VPS_IP%
echo ==========================================
echo.

echo Step 1: Install Docker...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "command -v docker || (apt update && apt install -y docker.io docker-compose-v2-plugin git make && systemctl enable docker && systemctl start docker)"

echo.
echo Step 2: Clone/Update repo...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "mkdir -p /opt/bettgbot && (cd /opt/bettgbot 2>/dev/null && git pull || (cd /opt && rm -rf bettgbot && git clone https://github.com/nmetluk/bettgbot.git bettgbot))"

echo.
echo Step 3: Copy .env...
%PSCP% -pw %SSH_PASS% infra\.env %SSH_USER%@%VPS_IP%:/opt/bettgbot/infra\.env

echo.
echo Step 4: Build images...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "cd /opt/bettgbot && docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml build"

echo.
echo Step 5: Start services...
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "cd /opt/bettgbot && docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml up -d"

echo.
echo Step 6: Wait and check...
timeout /t 10 /nobreak
%PLINK% -ssh -pw %SSH_PASS% %SSH_USER%@%VPS_IP% "curl -s http://127.0.0.1:8888/healthz"

echo.
echo ==========================================
echo Deploy done!
echo ==========================================
echo.
echo Admin URL: http://%VPS_IP%:8888/admin
echo.
echo Create admin user:
echo   ssh %SSH_USER%@%VPS_IP%
echo   cd /opt/bettgbot
echo   docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml exec web python scripts/create_admin.py --login admin --password 'PASS'
echo.

pause
