$ErrorActionPreference = "Stop"

$venvPath = ".venv"
if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
}

& "$venvPath\Scripts\python.exe" -m pip install --upgrade pip
& "$venvPath\Scripts\python.exe" -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

& "$venvPath\Scripts\python.exe" manage.py migrate
& "$venvPath\Scripts\python.exe" manage.py collectstatic --no-input
& "$venvPath\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
