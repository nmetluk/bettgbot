# PowerShell скрипт деплоя на VPS с поддержкой пароля
# Использование: .\scripts\deploy-to-vps.ps1 -VpsIp "5.188.88.78" -SshUser "root" -SshPassword "yourpassword"

param(
    [string]$VpsIp = "5.188.88.78",
    [string]$SshUser = "root",
    [string]$SshPassword = ""
)

if (-not $SshPassword) {
    Write-Host "Usage: .\scripts\deploy-to-vps.ps1 -VpsIp 'IP' -SshUser 'user' -SshPassword 'password'" -ForegroundColor Red
    exit 1
}

$plink = "C:\Program Files\PuTTY\plink.exe"
$pscp = "C:\Program Files\PuTTY\pscp.exe"

if (-not (Test-Path $plink)) {
    Write-Host "Plink not found at $plink" -ForegroundColor Red
    exit 1
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Deploying Betting Bot to VPS" -ForegroundColor Cyan
Write-Host " IP: $VpsIp" -ForegroundColor Cyan
Write-Host " SSH: $SshUser" -ForegroundColor Cyan
Write-Host " Port: 8888 (no TLS)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Function to run SSH command
function Invoke-SSH {
    param([string]$Command)
    $output = & $plink -ssh -pw $SshPassword "$SshUser@$VpsIp" $Command 2>&1
    return $output
}

# Function to copy file via SCP
function Copy-ToVPS {
    param([string]$Source, [string]$Dest)
    & $pscp -pw $SshPassword $Source "$SshUser@$VpsIp`:$Dest" 2>&1
}

# Check local .env
Write-Host "→ Checking local files..." -ForegroundColor Yellow
if (-not (Test-Path "infra\.env")) {
    Write-Host "ERROR: infra/.env not found!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Local files OK" -ForegroundColor Green
Write-Host ""

# Step 1: Install Docker
Write-Host "→ Step 1: Installing Docker on VPS..." -ForegroundColor Yellow
Invoke-SSH "set -e; if ! command -v docker &> /dev/null; then sudo apt update && sudo apt install -y docker.io docker-compose-v2-plugin git make && sudo systemctl enable docker && sudo systemctl start docker && echo 'Docker installed'; else echo 'Docker already installed'; fi; docker --version; docker compose version"
Write-Host ""

# Step 2: Clone repo
Write-Host "→ Step 2: Cloning repository..." -ForegroundColor Yellow
Invoke-SSH "set -e; if [ -d /opt/bettgbot ]; then echo 'Repo exists, updating...'; cd /opt/bettgbot; git fetch origin; git reset --hard origin/main; git pull origin main; else sudo mkdir -p /opt/bettgbot; sudo chown \$USER:\$USER /opt/bettgbot; git clone https://github.com/nmetluk/bettgbot.git /opt/bettgbot; fi; cd /opt/bettgbot; git log --oneline -1"
Write-Host ""

# Step 3: Copy .env
Write-Host "→ Step 3: Copying .env to VPS..." -ForegroundColor Yellow
Copy-ToVPS "infra\.env" "/opt/bettgbot/infra/.env"
Write-Host "✓ .env copied" -ForegroundColor Green
Write-Host ""

# Step 4: Build images
Write-Host "→ Step 4: Building Docker images on VPS..." -ForegroundColor Yellow
Invoke-SSH "cd /opt/bettgbot && make prod.nodomain.build"
Write-Host ""

# Step 5: Start services
Write-Host "→ Step 5: Starting services..." -ForegroundColor Yellow
Invoke-SSH "cd /opt/bettgbot && make prod.nodomain.up"
Write-Host ""

# Step 6: Wait and check health
Write-Host "→ Step 6: Waiting 5s for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "→ Checking health..." -ForegroundColor Yellow
Invoke-SSH "curl -s http://127.0.0.1:8888/healthz && echo ' ✓ Healthz OK'"
Write-Host ""

Write-Host "==========================================" -ForegroundColor Green
Write-Host "✓ Deploy completed!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  Admin:   http://${VpsIp}:8888/admin"
Write-Host "  Healthz: http://${VpsIp}:8888/healthz"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. SSH into VPS: ssh ${SshUser}@${VpsIp}"
Write-Host "  2. Create admin:"
Write-Host "     cd /opt/bettgbot"
Write-Host "     docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml exec web python scripts/create_admin.py --login admin --password 'YourSecurePassword'"
Write-Host ""
