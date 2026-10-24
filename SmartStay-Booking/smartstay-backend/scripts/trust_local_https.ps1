# Run in PowerShell from the project root, after gateway starts.
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path "dev-certs" | Out-Null
docker compose cp gateway:/data/caddy/pki/authorities/local/root.crt ./dev-certs/root.crt
if ($LASTEXITCODE -ne 0) { throw "Cannot export the local CA. Check docker compose ps gateway." }
# Trust this project's local CA for the current Windows user only.
Import-Certificate -FilePath ./dev-certs/root.crt -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
Write-Host "Local HTTPS ready: https://localhost:8443/docs"
