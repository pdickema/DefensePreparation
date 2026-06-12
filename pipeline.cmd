@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Could not find .venv\Scripts\python.exe.
  echo Create the virtual environment first:
  echo   py -3.11 -m venv .venv
  echo   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
  exit /b 1
)

if "%~1"=="" goto help

set "PIPELINE_COMMAND=%~1"
shift /1

if /I "%PIPELINE_COMMAND%"=="all" set "PIPELINE_COMMAND=run-all"
if /I "%PIPELINE_COMMAND%"=="run" set "PIPELINE_COMMAND=run-all"
if /I "%PIPELINE_COMMAND%"=="preflight" set "PIPELINE_COMMAND=preflight-pdfs"
if /I "%PIPELINE_COMMAND%"=="export" set "PIPELINE_COMMAND=export-llm"
if /I "%PIPELINE_COMMAND%"=="llm" set "PIPELINE_COMMAND=export-llm"
if /I "%PIPELINE_COMMAND%"=="manifest" set "PIPELINE_COMMAND=validate-manifest"
if /I "%PIPELINE_COMMAND%"=="scan" set "PIPELINE_COMMAND=scan-pdfs"

set "ARGS="
:collect_args
if "%~1"=="" goto run_command
set "ARGS=%ARGS% "%~1""
shift /1
goto collect_args

:run_command
"%PYTHON_EXE%" -m paper_pipeline.cli %PIPELINE_COMMAND% %ARGS%
exit /b %ERRORLEVEL%

:help
echo Defense paper pipeline launcher
echo.
echo Usage:
echo   pipeline.cmd all
echo   pipeline.cmd preflight
echo   pipeline.cmd scan
echo   pipeline.cmd manifest
echo   pipeline.cmd process
echo   pipeline.cmd chunk
echo   pipeline.cmd report
echo   pipeline.cmd defense-prep
echo   pipeline.cmd export
echo   pipeline.cmd query "your question"
echo.
echo Aliases:
echo   all, run      - run-all
echo   preflight    - preflight-pdfs
echo   scan         - scan-pdfs
echo   manifest     - validate-manifest
echo   export, llm  - export-llm
echo.
"%PYTHON_EXE%" -m paper_pipeline.cli --help
exit /b %ERRORLEVEL%
