# 드랍십핑 API 테스트 실행 스크립트
param(
    [string] = "unit",  # unit, integration, e2e
    [switch] = False,
    [switch] = False
)

Write-Host "드랍십핑 API 테스트 실행..." -ForegroundColor Green

# 가상환경 활성화 확인
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "가상환경 활성화..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
}

# 테스트 경로 설정
 = "src\tests\"
if (-not (Test-Path )) {
    Write-Host "테스트 경로가 존재하지 않습니다: " -ForegroundColor Red
    exit 1
}

# Python 모듈 경로 설정
 = D:\fast\fast_16

# 테스트 실행 옵션
 = if () { "-v" } else { "-q" }
 = if () { "--cov=src --cov-report=html --cov-report=term" } else { "" }

# 테스트 실행
 = "python -m pytest   "

Write-Host "실행 명령: " -ForegroundColor Cyan
Invoke-Expression 

 = 
if ( -eq 0) {
    Write-Host "테스트 완료!" -ForegroundColor Green
} else {
    Write-Host "테스트 실패!" -ForegroundColor Red
}

exit 
