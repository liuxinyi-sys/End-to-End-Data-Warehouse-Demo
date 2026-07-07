@echo off
setlocal enabledelayedexpansion

echo ========================================
echo  End-to-End Data Warehouse Demo
echo ========================================
echo.

REM 检查 Docker 是否安装
echo Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not found. Please install Docker Desktop.
    echo Download: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo [OK] Docker found
echo.

REM 检查 Docker Compose
echo Checking Docker Compose...
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose not found.
    pause
    exit /b 1
)
echo [OK] Docker Compose found
echo.

REM 创建数据目录
echo Creating data directories...
if not exist "%CD%\data\mysql" (
    mkdir "%CD%\data\mysql"
    echo [OK] Created data/mysql
)
if not exist "%CD%\data\grafana" (
    mkdir "%CD%\data\grafana"
    echo [OK] Created data/grafana
)
if not exist "%CD%\data\ymatrix" (
    mkdir "%CD%\data\ymatrix"
    echo [OK] Created data/ymatrix
)
echo.

REM 检查 .env 文件
if not exist "%CD%\.env" (
    echo [WARNING] .env file not found. Creating from .env.example...
    if exist "%CD%\.env.example" (
        copy "%CD%\.env.example" "%CD%\.env"
        echo [OK] Created .env from .env.example
    ) else (
        echo [WARNING] .env.example not found. Using default settings.
    )
)
echo.

REM 拉取最新镜像
echo Pulling latest images...
docker compose pull
echo.

REM 启动服务
echo Starting services...
docker compose up -d
echo.

REM 等待服务启动
echo Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM 显示服务状态
echo.
echo ========================================
echo Service Status:
docker compose ps
echo.

REM 显示访问信息
echo ========================================
echo Environment is ready!
echo.
echo Access URLs:
echo   Grafana: http://localhost:${GRAFANA_PORT:-3000}
echo   MatrixDB: localhost:${YMATRIX_PORT:-5432}
echo   MySQL: localhost:${MYSQL_PORT:-3306}
echo.
echo Credentials:
echo   Grafana: admin/admin
echo   MatrixDB: mxadmin/mxadmin123
echo   MySQL: root/root
echo.
echo To view logs:
echo   docker compose logs -f
echo.
echo To stop services:
echo   docker compose down
echo ========================================
pause