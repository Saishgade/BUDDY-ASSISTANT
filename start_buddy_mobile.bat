@echo off
cd /d "%~dp0\buddy-mobile"
call npm.cmd install
call npm.cmd run start