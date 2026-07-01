# PowerShell script to run BUDDY with proper environment
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# Activate virtual environment
& ".\\.venv\\Scripts\\Activate.ps1"

# Run buddy
python buddy.py
