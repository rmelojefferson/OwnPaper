@echo off
setlocal
title OwnPaper - Atualizar IP ignorado

REM Configure estes valores antes de usar.
set "OWNPAPER_URL=https://seu-dominio.com"
set "OWNPAPER_TOKEN=cole-o-token-aqui"
set "OWNPAPER_NOME=rede-local"

echo Atualizando IP publico ignorado no OwnPaper...
echo URL: %OWNPAPER_URL%/estatisticas/registrar-ip-ignorado/
echo Nome: %OWNPAPER_NOME%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; try { $url='%OWNPAPER_URL%/estatisticas/registrar-ip-ignorado/'; $body=@{token='%OWNPAPER_TOKEN%'; nome='%OWNPAPER_NOME%'}; $r=Invoke-RestMethod -Method Post -Uri $url -Body $body; Write-Host ('IP registrado: ' + $r.ip); Write-Host ('Expira em: ' + $r.expira_em); exit 0 } catch { Write-Host ('Erro: ' + $_.Exception.Message); if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }; exit 1 }"

if %ERRORLEVEL% EQU 0 (
  echo.
  echo IP publico registrado com sucesso no OwnPaper.
) else (
  echo.
  echo Falha ao registrar IP publico no OwnPaper.
)

echo.
pause
endlocal
