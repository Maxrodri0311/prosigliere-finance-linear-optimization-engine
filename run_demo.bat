@echo off
setlocal enabledelayedexpansion

echo ================================================================================
echo   PROSIGLIERE: OMNICHANNEL ATTRIBUTION AND LINEAR OPTIMIZATION ENGINE
echo   Automated Execution, Mathematical Invariants and Quantitative Benchmarks
echo ================================================================================
echo.

echo [1/5] Executing Production Quality and CI/CD Security Guards...
python scripts/validate_no_credentials.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Credential guard failed && exit /b %ERRORLEVEL%)

python scripts/validate_no_internal_leaks.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Internal leaks guard failed && exit /b %ERRORLEVEL%)

python scripts/validate_sql_complexity.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] SQL complexity guard failed && exit /b %ERRORLEVEL%)

python scripts/validate_sql_minimum_viable.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] SQL minimum viable guard failed && exit /b %ERRORLEVEL%)

python scripts/validate_terraform_minimum_viable.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Terraform guard failed && exit /b %ERRORLEVEL%)

python scripts/validate_byte_budget.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Byte budget guard failed && exit /b %ERRORLEVEL%)

echo.
echo [2/5] Synthesizing Calibrated Omnichannel Marketing Dataset (50,000 observations)...
python src/data_generator.py --records 50000
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Data generator failed && exit /b %ERRORLEVEL%)

echo.
echo [3/5] Solving HiGHS Linear Programming and Dual Shadow Prices...
python src/core_engine.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Core engine failed && exit /b %ERRORLEVEL%)

echo.
echo [4/5] Executing Mathematical Invariants and Test Suite...
python -m pytest tests/ -v
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Pytest suite failed && exit /b %ERRORLEVEL%)

echo.
echo [5/5] Running Quantitative Latency and Throughput Benchmarks (30 iterations)...
python tests/benchmark.py
if %ERRORLEVEL% NEQ 0 (echo [ERROR] Benchmark failed && exit /b %ERRORLEVEL%)

echo.
echo ================================================================================
echo   Execution Complete: All Invariants, Security and Latency SLAs Verified!
echo ================================================================================