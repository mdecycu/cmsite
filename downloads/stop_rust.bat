@echo off
set DRIVE=R:

taskkill /IM python.exe /F
taskkill /IM pythonw.exe /F
REM taskkill /IM adb.exe /F
taskkill /IM scite.exe /F
taskkill /IM ugraf.exe /F
taskkill /IM webotsw.exe /F
taskkill /IM solvespace.exe /F
taskkill /IM sharex.exe /F

echo Unmounting %DRIVE% ...
subst %DRIVE% /D

REM 關閉 cmd 指令視窗
taskkill /IM cmd.exe /F

echo Done.

EXIT
