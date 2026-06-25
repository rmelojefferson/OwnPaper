@echo off
setlocal EnableExtensions
title OwnPaper - Atualizar IP ignorado

REM Configure estes valores antes de usar.
set "OWNPAPER_URL=https://seu-dominio.com"
set "OWNPAPER_TOKEN=cole-o-token-aqui"
set "OWNPAPER_NOME=rede-local"

set "OWNPAPER_PS1=%TEMP%\ownpaper-atualizar-ip-%RANDOM%%RANDOM%.ps1"

echo Atualizando IP publico ignorado no OwnPaper...
echo URL: %OWNPAPER_URL%/estatisticas/registrar-ip-ignorado/
echo Nome: %OWNPAPER_NOME%
echo.

> "%OWNPAPER_PS1%" echo $ErrorActionPreference = 'Stop'
>> "%OWNPAPER_PS1%" echo $url = $env:OWNPAPER_URL.TrimEnd('/') + '/estatisticas/registrar-ip-ignorado/'
>> "%OWNPAPER_PS1%" echo $body = @{ token = $env:OWNPAPER_TOKEN; nome = $env:OWNPAPER_NOME }
>> "%OWNPAPER_PS1%" echo try {
>> "%OWNPAPER_PS1%" echo     $r = Invoke-RestMethod -Method Post -Uri $url -Body $body
>> "%OWNPAPER_PS1%" echo     Write-Host ('IP registrado: ' + $r.ip)
>> "%OWNPAPER_PS1%" echo     Write-Host ('Expira em: ' + $r.expira_em)
>> "%OWNPAPER_PS1%" echo     if ($r.plausible -and $r.plausible.enabled) {
>> "%OWNPAPER_PS1%" echo         if ($r.plausible.error) {
>> "%OWNPAPER_PS1%" echo             Write-Host ('Plausible: erro - ' + $r.plausible.error)
>> "%OWNPAPER_PS1%" echo         } else {
>> "%OWNPAPER_PS1%" echo             Write-Host ('Plausible atualizado: ' + (($r.plausible.updated ^| ForEach-Object { $_ }) -join ', '))
>> "%OWNPAPER_PS1%" echo         }
>> "%OWNPAPER_PS1%" echo     } else {
>> "%OWNPAPER_PS1%" echo         Write-Host 'Plausible: sincronizacao desativada.'
>> "%OWNPAPER_PS1%" echo     }
>> "%OWNPAPER_PS1%" echo     exit 0
>> "%OWNPAPER_PS1%" echo } catch {
>> "%OWNPAPER_PS1%" echo     Write-Host ('Erro: ' + $_.Exception.Message)
>> "%OWNPAPER_PS1%" echo     if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
>> "%OWNPAPER_PS1%" echo     exit 1
>> "%OWNPAPER_PS1%" echo }

powershell -NoProfile -ExecutionPolicy Bypass -File "%OWNPAPER_PS1%"
set "OWNPAPER_EXIT=%ERRORLEVEL%"
del "%OWNPAPER_PS1%" >nul 2>nul

echo.
if "%OWNPAPER_EXIT%"=="0" (
  echo IP publico registrado com sucesso no OwnPaper.
) else (
  echo Falha ao registrar IP publico no OwnPaper.
)

echo.
pause
endlocal
