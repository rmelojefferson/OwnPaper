@echo off
setlocal

REM Configure estes dois valores antes de usar.
set "OWNPAPER_URL=https://seu-dominio.com"
set "OWNPAPER_TOKEN=cole-o-token-aqui"
set "OWNPAPER_NOME=rede-local"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $url='%OWNPAPER_URL%/estatisticas/registrar-ip-ignorado/'; $body=@{token='%OWNPAPER_TOKEN%'; nome='%OWNPAPER_NOME%'}; Invoke-RestMethod -Method Post -Uri $url -Body $body | Out-Null"

if %ERRORLEVEL% EQU 0 (
  echo IP publico registrado com sucesso no OwnPaper.
) else (
  echo Falha ao registrar IP publico no OwnPaper.
)

endlocal
