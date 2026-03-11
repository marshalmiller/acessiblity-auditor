@echo off
REM Quick start script for Accessibility Auditor (Windows)

echo Starting Accessibility Auditor...
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed. Please install Docker Desktop first.
    echo Visit: https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker Compose is not installed.
    echo It should come with Docker Desktop. Please reinstall Docker Desktop.
    pause
    exit /b 1
)

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file...
    copy .env.example .env >nul
    echo WARNING: Please edit .env and set a secure SECRET_KEY for production!
    echo.
)

REM Start the application
echo Building and starting containers...
docker-compose up -d --build

REM Wait for the application to be ready
echo.
echo Waiting for application to start...
timeout /t 5 /nobreak >nul

REM Check if the application is running
curl -s http://localhost:5000 >nul 2>&1
if errorlevel 1 (
    echo.
    echo Application may still be starting. Check logs with:
    echo    docker-compose logs -f
    echo.
) else (
    echo.
    echo Accessibility Auditor is running!
    echo.
    echo Access the application at: http://localhost:5000
    echo.
    echo View logs:    docker-compose logs -f
    echo Stop app:     docker-compose down
    echo Restart:      docker-compose restart
    echo.
)

pause
