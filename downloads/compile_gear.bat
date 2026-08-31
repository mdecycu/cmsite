@echo off
setlocal EnableExtensions DisableDelayedExpansion

title VS 2026 - UGS NX3 Gear DLL Compiler

echo.
echo ==========================================
echo VS 2026 - UGS NX3 Gear DLL Compiler
echo ==========================================
echo.

REM ============================================================
REM Basic paths
REM ============================================================

set "SOURCE=Y:\gear\gear.c"
set "BUILD=Y:\gear\gear_build.dll"
set "FINAL=Y:\gear\gear.dll"

set "VSROOT=C:\Program Files\Microsoft Visual Studio\18\Community"
set "VCTOOLS=%VSROOT%\VC\Auxiliary\Build\vcvarsall.bat"
set "CL_EXE=%VSROOT%\VC\Tools\MSVC\14.50.35717\bin\Hostx86\x86\cl.exe"

set "NX3=C:\nx3"
set "NX_INC=%NX3%\ugopen"
set "UF_LIB=%NX3%\ugopen\libufun.lib"
set "UGOPEN_LIB=%NX3%\ugopen\libugopenint.lib"

REM ============================================================
REM Check files
REM ============================================================

echo Checking files...
echo.

if not exist "%SOURCE%" goto FILE_ERROR
if not exist "%VCTOOLS%" goto FILE_ERROR
if not exist "%CL_EXE%" goto FILE_ERROR
if not exist "%UF_LIB%" goto FILE_ERROR
if not exist "%UGOPEN_LIB%" goto FILE_ERROR

echo Source:
echo %SOURCE%
echo.
echo Build:
echo %BUILD%
echo.
echo Final:
echo %FINAL%
echo.

echo ==========================================
echo Starting Visual Studio x86 environment...
echo ==========================================
echo.

REM ============================================================
REM IMPORTANT:
REM Prevent "The input line is too long" by checking if 
REM vcvarsall.bat was already called in this console session.
REM ============================================================

if defined DevEnvDir (
    echo Visual Studio environment already initialized. Skipping vcvarsall.bat.
    goto SKIP_VCVARS
)

call "%VCTOOLS%" x86
if errorlevel 1 goto VC_ERROR

:SKIP_VCVARS

echo.
echo ==========================================
echo Compiler
echo ==========================================
echo.

where cl
if errorlevel 1 goto VC_ERROR

echo.
echo ==========================================
echo Compiling
echo ==========================================
echo.

REM ============================================================
REM Remove old build files.
REM We deliberately build to gear_build.dll first.
REM This avoids linker LNK1104 when gear.dll is still loaded
REM by NX.
REM ============================================================

if exist "%BUILD%" del /f /q "%BUILD%" >nul 2>&1
if exist "%BUILD:.dll=.lib%" del /f /q "%BUILD:.dll=.lib%" >nul 2>&1

REM ============================================================
REM Compile
REM ============================================================

cl.exe /nologo /LD /TC /EHsc- /W3 /DWIN32 /D_WINDOWS /D_USRDLL /I"%NX_INC%" /Fe"%BUILD%" "%SOURCE%" /link /MACHINE:X86 "%UF_LIB%" "%UGOPEN_LIB%"

if errorlevel 1 goto BUILD_ERROR

echo.
echo ==========================================
echo Compilation successful
echo ==========================================
echo.

if not exist "%BUILD%" goto BUILD_ERROR

echo Build DLL:
echo %BUILD%
echo.

REM ============================================================
REM Replace final DLL
REM ============================================================

echo Replacing final DLL...
echo.

if exist "%FINAL%" (
    del /f /q "%FINAL%" >nul 2>&1

    if exist "%FINAL%" (
        echo.
        echo ==========================================
        echo WARNING
        echo ==========================================
        echo.
        echo %FINAL% is currently locked.
        echo.
        echo Most likely NX is still using the old DLL.
        echo Close NX, then run this BAT again.
        echo.
        goto BUILD_ERROR
    )
)

copy /y "%BUILD%" "%FINAL%" >nul

if errorlevel 1 goto BUILD_ERROR

if not exist "%FINAL%" goto BUILD_ERROR

echo.
echo ==========================================
echo BUILD SUCCESS
echo ==========================================
echo.
echo Final DLL:
echo %FINAL%
echo.
echo Architecture:
echo x86 / 32-bit
echo.
echo NX3 UGOPEN libraries:
echo %UF_LIB%
echo %UGOPEN_LIB%
echo.
echo ==========================================
echo.

goto END


:FILE_ERROR

echo.
echo ==========================================
echo FILE CHECK FAILED
echo ==========================================
echo.

if not exist "%SOURCE%" (
    echo Missing source:
    echo %SOURCE%
    echo.
)

if not exist "%VCTOOLS%" (
    echo Missing vcvarsall.bat:
    echo %VCTOOLS%
    echo.
)

if not exist "%CL_EXE%" (
    echo Missing compiler:
    echo %CL_EXE%
    echo.
)

if not exist "%UF_LIB%" (
    echo Missing:
    echo %UF_LIB%
    echo.
)

if not exist "%UGOPEN_LIB%" (
    echo Missing:
    echo %UGOPEN_LIB%
    echo.
)

goto END


:VC_ERROR

echo.
echo ==========================================
echo VISUAL STUDIO INITIALIZATION FAILED
echo ==========================================
echo.
echo vcvarsall:
echo %VCTOOLS%
echo.
echo Expected compiler:
echo %CL_EXE%
echo.

goto END


:BUILD_ERROR

echo.
echo ==========================================
echo BUILD FAILED
echo ==========================================
echo.
echo Please check the compiler/linker messages above.
echo.

goto END


:END

echo.
pause
endlocal