@echo off
setlocal
cd /d "%~dp0"

set "MCP_URL=http://localhost:18001/mcp"
set "PYTHONUNBUFFERED=1"
set "SAMPLE_PROMPT=Use every available MCP tool: greet Anupriya, report the current server time, and calculate 25 times 12."
if not "%~1"=="" set "SAMPLE_PROMPT=%~1"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: The sample virtual environment does not exist.
  echo Run: py -3.12 -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  exit /b 2
)

echo Running MCP API demonstration and agent prompt...
echo.
".venv\Scripts\python.exe" -m agent_app.demo --prompt "%SAMPLE_PROMPT%"
set "RUN_EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%RUN_EXIT_CODE%"=="0" (
  echo Sample failed with exit code %RUN_EXIT_CODE%.
  echo Confirm the MCP server is healthy and set OPENAI_API_KEY in .env.
) else (
  echo Sample completed successfully.
)

exit /b %RUN_EXIT_CODE%
