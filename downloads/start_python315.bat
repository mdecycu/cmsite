@echo off
set Disk=y
subst %Disk%: "data"

%Disk%:

set HomePath=%Disk%:\home_ipv6
set HomeDrive=%Disk%:\home_ipv6
set Home=%Disk%:\home_ipv6
set USERPROFILE=%Disk%:\home_ipv6

REM 將系統 Python 程式的 io 設為 utf-8
set PYTHONIOENCODING="utf-8"

set PYTHONPATH=%Disk%:\Python315\DLLs;%Disk%:\Python315\Lib;%Disk%:\Python315\Lib\site-packages;

REM for Webots
set PYTHON_PATH=%Disk%:\Python315
set WEBOTS_HOME=%Disk%:\Webots_2023b

REM for putty
set GIT_SSH=%Disk%:\PuTTY\plink.exe

REM 設定跟 Python 有關的命令搜尋路徑
set path_python=%Disk%:\Python315;%Disk%:\Python315\Scripts

REM 設定跟Git 有關的命令搜尋路徑
set path_git=%Disk%:\portablegit\bin

REM 設定 msys2 64 位元的執行路徑
REM %Disk%:\msys64\mingw64\bin is for GD library
set path_msys2=%Disk%:\msys64\ucrt64\bin;%Disk%:\msys64\mingw64\bin

REM for CMake
set CMAKE_C_COMPILER=%Disk%:\msys64\ucrt64\bin\gcc;
set CMAKE_CXX_COMPILER=%Disk%:\msys64\ucrt64\bin\g++;

REM for execute scite directly
set path_scite=%Disk%:\wscite\

REM for tiny C compiler
set path_tcc=%Disk%:\tcc

REM for webots
set  path_webots=%Disk%:\Webots_2023b\msys64\mingw64\bin;%Disk%:\Webots_2023b\msys64\usr\bin

REM for blender
set path_blender=%Disk%:\Blender 4.2

REM 
set path_poppler=%Disk%:\poppler\Library\bin

REM 
set path_openoffice="C:\Program Files\LibreOffice\program"

path=%Disk%:;%path_python%;%path_git%;%path_msys2%;%path_tcc%;%path_scite%;%path_webots%;%path_blender%;%path_poppler%;%path_openoffice%;%path%;

REM for NX2312, must after path setup 
set SPLM_LICENSE_SERVER=29000@192.168.56.3
set UGII_LANG=english
set UGS_LICENSE_BUNDLE=ACD11,ACD10
set UGII_BASE_DIR=y:\nx\
set UGII_TMP_DIR=y:\nx\temp
set UGII_LIB_PATH=y:\nx\NXBIN\python
set ugii=y:\nx\ugii;y:\nx\nxbin;
path = %path%;%ugii%;
REM Xcopy %Disk%:\home_ipv6\AppData\Local\Siemens\NX2312 C:\users\%USERNAME%\AppData\Local\Siemens\NX2312 /E /H /C /I /Y

REM start ugraf -nx

REM python %Disk%:\tmp\nx_ex\new_part.py

REM start webotsw.exe --stream
REM timeout /t 5
 
REM start：在新的視窗中啟動程式，不會讓目前的批次檔等待。
REM webotsw.exe：啟動 Webots（Windows GUI 版）。
REM --stream：啟動 Webots 的 streaming 伺服器，可以設法將模擬場景執行內容，顯示在近端或遠端瀏覽器中。
REM timeout：批次檔暫停。
REM /t 5：等待 5 秒，讓 Webots 有足夠時間啟動。
 
REM start python %Disk%:\webots_streamming\web\python_www_server.py
REM timeout /t 5
 
REM 利用 python 啟動 www 伺服器接收來自 Webots 模擬場景的串流影像。

start /MIN cmd.exe
start /MIN cmd.exe
start /MIN cmd.exe
start /MIN cmd.exe

start /MIN %Disk%:\wscite\SciTE.exe
start /MIN %Disk%:\wscite\SciTE.exe

REM start webotsw.exe

Exit
