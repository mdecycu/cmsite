@echo off
chcp 65001 >nul
setlocal ENABLEEXTENSIONS

REM ==================================================
REM  Portable System Bootstrap (Rust / Python / Webots)
REM ==================================================

REM === 虛擬磁碟代號（請勿加反斜線）===
set DRIVE=R:

REM === 取得 batch 所在目錄（結尾含 \）===
set ROOT=%~dp0
set DATA=%ROOT%data

REM === 若已存在則先解除（避免錯誤）===
subst %DRIVE% /D >nul 2>&1

REM === 建立虛擬磁碟 ===
subst %DRIVE% "%DATA%"

REM ==================================================
REM  Home / User 環境（避免污染系統）
REM ==================================================
set HOMEDRIVE=%DRIVE%
set HOMEPATH=\home
set USERPROFILE=%DRIVE%\home
set HOME=%DRIVE%\home

REM ==================================================
REM  Python 環境
REM ==================================================
set PYTHONIOENCODING=utf-8
set PYTHONHOME=%DRIVE%\Python315

set PYTHONPATH=%DRIVE%\Python315\DLLs^
;%DRIVE%\Python315\Lib^
;%DRIVE%\Python315\Lib\site-packages^

REM ==================================================
REM  Git / Putty
REM ==================================================
set GIT_SSH=%DRIVE%\PuTTY\plink.exe

REM ==================================================
REM  Rust (Portable, GNU)
REM ==================================================
set RUSTUP_HOME=%DRIVE%\.rustup
REM et CARGO_HOME=%DRIVE%\.cargo
REM cargo cache need NTFS disk
set CARGO_HOME=C:\cargo
set SCITE_HOME=%DRIVE%\wscite
set RUSTUP_NO_UPDATE_CHECK=1

REM === 強制使用 GNU toolchain ===
set RUSTUP_TOOLCHAIN=stable-x86_64-pc-windows-gnu

REM === MinGW 編譯器指定（非常重要）===
set CC=%DRIVE%\msys64\ucrt64\bin\gcc.exe
set CXX=%DRIVE%\msys64\ucrt64\bin\g++.exe
set AR=%DRIVE%\msys64\ucrt64\bin\ar.exe

REM === Rust linker 指定 ===
set RUSTFLAGS=-C linker=%DRIVE%\msys64\ucrt64\bin\gcc.exe

REM ==================================================
REM  PATH 組合
REM ==================================================
set PATH=%DRIVE%\msys64\ucrt64\bin^
;%CARGO_HOME%\bin^
;%SCITE_HOME%^
;%DRIVE%\Python315^
;%DRIVE%\Python315\Scripts^
;%DRIVE%\portablegit\bin^
;%PATH%

set PATH=%PATH%;%DRIVE%;%DRIVE%\.rustup\toolchains\stable-x86_64-pc-windows-gnu\bin;

REM ==================================================
REM  顯示資訊
REM ==================================================
title Portable Rust GNU Environment (%DRIVE%)

echo ======================================
echo  Portable Environment Ready
echo  Mounted Drive : %DRIVE%
echo  Data Path     : %DATA%
echo  Rust Toolchain: %RUSTUP_TOOLCHAIN%
echo  MinGW GCC     : %CC%
echo  Type STOP then close window to exit
echo ======================================
echo.

REM ==================================================
REM  啟動工具
REM ==================================================
if exist "%SCITE_HOME%\SciTE.exe" (
    start "" /MIN "%SCITE_HOME%\SciTE.exe"
)

REM === 切換到虛擬磁碟 ===
%DRIVE%

REM ==================================================
REM  保持命令列
REM ==================================================
start "CMD-1" cmd /k
start "CMD-2" cmd /k
REM start "CMD-3" cmd /k
REM start "CMD-4" cmd /k
