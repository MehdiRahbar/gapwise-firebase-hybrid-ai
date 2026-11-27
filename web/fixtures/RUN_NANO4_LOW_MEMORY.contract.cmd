@echo off
setlocal EnableExtensions
rem GAPWISE_PUBLIC_CONTRACT_FIXTURE: portable regression contract only.
rem The real Laptop-2 runner and its evidence remain outside this public source export.
rem This fixture never copies a profile, uses CDP, stores credentials, or claims inference.

set "GAPWISE_RUN_ID=%RANDOM%_%RANDOM%"
set "GAPWISE_LOCAL_URL=http://127.0.0.1:18201/?nano4_run=%GAPWISE_RUN_ID%"
set "GAPWISE_EVIDENCE_ENDPOINT=http://127.0.0.1:18201/__gapwise_evidence"
set "CHROME_EXE="
for /f "delims=" %%C in ('where chrome.exe 2^>nul') do if not defined CHROME_EXE set "CHROME_EXE=%%C"

if not defined CHROME_EXE (
  echo Chrome was not found on PATH. This public contract fixture does not install software.
  exit /b 2
)

start "" "%CHROME_EXE%" --profile-directory="Default" --new-window "%GAPWISE_LOCAL_URL%"
echo Evidence endpoint contract: %GAPWISE_EVIDENCE_ENDPOINT%
endlocal
exit /b 0
