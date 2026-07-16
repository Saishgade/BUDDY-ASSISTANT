Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location "buddy-mobile"
if (-not (Test-Path "node_modules")) {
    npm.cmd install
}
npm.cmd run start
