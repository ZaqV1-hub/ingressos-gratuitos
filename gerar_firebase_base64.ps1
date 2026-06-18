$jsonPath = Read-Host "Caminho do serviceAccount.json"
if (-not (Test-Path $jsonPath)) {
  Write-Host "Arquivo não encontrado."
  exit 1
}

$content = Get-Content $jsonPath -Raw
$base64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($content))
Write-Host ""
Write-Host "Cole esse valor em FIREBASE_SERVICE_ACCOUNT_JSON_BASE64:"
Write-Host ""
Write-Output $base64
