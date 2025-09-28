# 드랍십핑 API 개발 서버 실행 스크립트
param(
    [string]System.Management.Automation.Internal.Host.InternalHost = "0.0.0.0",
    [int] = 8000,
    [switch] = False
)

Write-Host "드랍십핑 API 개발 서버 시작..." -ForegroundColor Green

# 가상환경 활성화 확인
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "가상환경 활성화..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
}

# 환경변수 파일 로드
if (Test-Path ".env") {
    Write-Host "환경변수 파일 로드..." -ForegroundColor Yellow
    Get-Content ".env" | ForEach-Object {
        if ( -match '^([^=]+)=(.*)$') {
             = [1]
             = [2]
            [Environment]::SetEnvironmentVariable(, )
        }
    }
}

# Python 모듈 경로 설정
 = D:\fast\fast_16

# 서버 실행
 = if () { "--reload" } else { "" }
 = "python -m uvicorn src.app.main:app --host System.Management.Automation.Internal.Host.InternalHost --port  "

Write-Host "실행 명령: " -ForegroundColor Cyan
Invoke-Expression 
