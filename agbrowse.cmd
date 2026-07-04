@echo off
setlocal
set "PATH=C:\Users\GYU\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;%PATH%"
"C:\Users\GYU\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd" dlx agbrowse %*
exit /b %ERRORLEVEL%
