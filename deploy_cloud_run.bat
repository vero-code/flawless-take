@echo off
REM ==============================================================================
REM deploy_cloud_run.bat - One-click deployment to Google Cloud Run (Windows)
REM ==============================================================================
setlocal enabledelayedexpansion

set PROJECT_ID=%1
if "%PROJECT_ID%"=="" set PROJECT_ID=%GOOGLE_CLOUD_PROJECT%
if "%PROJECT_ID%"=="" (
    for /f "tokens=*" %%i in ('gcloud config get-value project 2^>nul') do set PROJECT_ID=%%i
)
if "%PROJECT_ID%"=="" (
    echo ERROR: Please specify your Google Cloud Project ID.
    echo Usage: deploy_cloud_run.bat YOUR_PROJECT_ID [REGION]
    exit /b 1
)
if "%PROJECT_ID%"=="(unset)" (
    echo ERROR: No active Google Cloud Project configured in gcloud.
    echo Please run: gcloud config set project YOUR_PROJECT_ID
    exit /b 1
)

set REGION=%2
if "%REGION%"=="" set REGION=us-central1
set SERVICE_NAME=flawless-take
set IMAGE_NAME=gcr.io/%PROJECT_ID%/%SERVICE_NAME%:latest

echo =======================================================
echo  Deploying Flawless Take to Google Cloud Run
echo  Project: %PROJECT_ID%
echo  Region:  %REGION%
echo  Service: %SERVICE_NAME%
echo =======================================================

echo Step 1: Building container with Google Cloud Build...
call gcloud builds submit --project %PROJECT_ID% --tag %IMAGE_NAME% .
if errorlevel 1 (
    echo Build failed!
    exit /b 1
)

echo Step 2: Deploying to Google Cloud Run with Secret Manager...
call gcloud run deploy %SERVICE_NAME% ^
  --project %PROJECT_ID% ^
  --image %IMAGE_NAME% ^
  --region %REGION% ^
  --platform managed ^
  --allow-unauthenticated ^
  --set-env-vars "GOOGLE_CLOUD_PROJECT=%PROJECT_ID%,APP_ENV=production,USE_SECRET_MANAGER=true" ^
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"

if errorlevel 1 (
    echo Deployment failed!
    exit /b 1
)

echo =======================================================
echo  Deployment Complete!
echo  Service URL:
call gcloud run services describe %SERVICE_NAME% --project %PROJECT_ID% --region %REGION% --format="value(status.url)"
echo =======================================================
pause
