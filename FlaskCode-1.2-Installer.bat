@echo off
setlocal enabledelayedexpansion

REM Flask Code 1.2 Installer with Animations
REM Downloads from GitHub -> writes to temp -> scans -> moves to final location

cls
echo.
echo ================================
echo  Flask Code 1.2 Installer
echo ================================
echo.

set "INSTALL_DIR=%~dp0"
set "TEMP_DIR=%INSTALL_DIR%_temp"
set "MOVED_COUNT=0"
set "TOTAL_FILES=26"

echo Installation directory: %INSTALL_DIR%
echo.

if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >nul 2>&1
mkdir "%TEMP_DIR%"

REM ==================== DOWNLOAD AND WRITE FILES ====================

echo ================================
echo  Downloading Files from GitHub
echo ================================
echo.

call :download_and_write "main.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/main.py" 1
call :download_and_write "apikey_settings.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/apikey_settings.py" 2
call :download_and_write "auth.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/auth.py" 3
call :download_and_write "chat_history.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/chat_history.py" 4
call :download_and_write "chat_loader.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/chat_loader.py" 5
call :download_and_write "code_extractor.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/code_extractor.py" 6
call :download_and_write "custom_terminal.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/custom_terminal.py" 7
call :download_and_write "engine.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/engine.py" 8
call :download_and_write "file_handler.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/file_handler.py" 9
call :download_and_write "gemini_client.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/gemini_client.py" 10
call :download_and_write "groq_client.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/groq_client.py" 11
call :download_and_write "markdown_highlighter.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/markdown_highlighter.py" 12
call :download_and_write "openrouter_client.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/openrouter_client.py" 13
call :download_and_write "prompt_mode.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/prompt_mode.py" 14
call :download_and_write "saved_info.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/saved_info.py" 15
call :download_and_write "shell_actions.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/shell_actions.py" 16
call :download_and_write "user-interface.py" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/user-interface.py" 17
call :download_and_write "flaskc.ps1" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/flaskc.ps1" 18
call :download_and_write "flaskcode.ps1" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/flaskcode.ps1" 19
call :download_and_write "flck.ps1" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/flck.ps1" 20
call :download_and_write "requirements.txt" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/requirements.txt" 21
call :download_and_write ".gitignore" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/.gitignore" 22
call :download_and_write "README.md" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/README.md" 23
call :download_and_write "Guide.md" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/Guide.md" 24
call :download_and_write "LICENSE" "https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/main/LICENSE" 25

type nul > "%TEMP_DIR%\.apikeys"

call :animate_download_complete 26

echo.
echo ================================
echo  Scanning Downloaded Files
echo ================================
echo.

call :scan_files

echo.
echo ================================
echo  Moving Files to Install Dir
echo ================================
echo.

call :move_files

echo.
echo ================================
echo  Download and Setup Complete!
echo ================================
echo.

set /p INSTALL_PIP="Install pip requirements? (y/n): "

if /i "%INSTALL_PIP%"=="y" (
    echo.
    echo Installing pip requirements...
    python -m pip install -r "%INSTALL_DIR%requirements.txt"
    if errorlevel 1 (
        echo WARNING: pip install had issues.
    ) else (
        echo pip requirements installed successfully!
    )
) else (
    echo Skipped pip installation.
)

if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >nul 2>&1

echo.
echo ================================
echo  Installation Summary
echo ================================
echo.
echo Location: %INSTALL_DIR%
echo.
echo Downloaded, Scanned and Moved:
echo   - 17 Python files
echo   - 3 PowerShell launcher scripts
echo   - README.md, Guide.md, LICENSE
echo   - requirements.txt, .gitignore
echo   - .apikeys (created empty)
echo.
echo Next Steps:
echo   1. Edit .apikeys with your API keys
echo   2. python main.py (terminal mode)
echo   3. python user-interface.py (GUI mode)
echo.
echo ================================
echo  Installation Complete!
echo ================================
echo.
echo Press ENTER to close this window...
pause
exit /b

REM ==================== DOWNLOAD AND WRITE FUNCTION ====================

:download_and_write
setlocal enabledelayedexpansion
set "FILENAME=%~1"
set "URL=%~2"
set "FILE_NUM=%~3"
set "TEMPFILE=%TEMP_DIR%\%FILENAME%"

REM Animate download
call :animate_download "!FILENAME!" "!FILE_NUM!" 26

REM Download
powershell -Command "Invoke-WebRequest -Uri '!URL!' -OutFile '!TEMPFILE!' -ErrorAction Stop" >nul 2>&1

if errorlevel 1 (
	echo ERROR: Failed to download !FILENAME!
	endlocal
	exit /b 1
)

REM Get file size
for %%A in ("!TEMPFILE!") do set "SIZE=%%~zA"

if "!SIZE!"=="0" (
	echo ERROR: !FILENAME! is empty
	endlocal
	exit /b 1
)

echo    Downloaded: !SIZE! bytes

endlocal
exit /b 0

REM ==================== ANIMATE DOWNLOAD ====================

:animate_download
setlocal enabledelayedexpansion
set "FILENAME=%~1"
set "CURRENT=%~2"
set "TOTAL=%~3"

REM Calculate overall progress percentage
set /a OVERALL_PERCENT=(CURRENT*100)/TOTAL

REM Animation frames for overall progress
set "FRAMES[0]=[===>          ]"
set "FRAMES[1]=[====>         ]"
set "FRAMES[2]=[=====>        ]"
set "FRAMES[3]=[======>       ]"
set "FRAMES[4]=[=======>      ]"
set "FRAMES[5]=[========>     ]"
set "FRAMES[6]=[=========>    ]"
set "FRAMES[7]=[==========>   ]"
set "FRAMES[8]=[===========>  ]"
set "FRAMES[9]=[============> ]"
set "FRAMES[10]=[=============>]"

REM Show animation
for /L %%I in (0,1,10) do (
	cls
	echo.
	echo ================================
	echo  Flask Code 1.2 Installer
	echo ================================
	echo.
	echo Downloading Files from GitHub
	echo.
	echo !FRAMES[%%I]! !OVERALL_PERCENT!%% [!CURRENT!/!TOTAL!]
	echo    Downloading: !FILENAME!
	timeout /t 0 >nul 2>&1
)

endlocal
exit /b 0

REM ==================== ANIMATE DOWNLOAD COMPLETE ====================

:animate_download_complete
setlocal enabledelayedexpansion
set "TOTAL=%~1"

set "FRAMES[0]=[===>          ]"
set "FRAMES[1]=[====>         ]"
set "FRAMES[2]=[=====>        ]"
set "FRAMES[3]=[======>       ]"
set "FRAMES[4]=[=======>      ]"
set "FRAMES[5]=[========>     ]"
set "FRAMES[6]=[=========>    ]"
set "FRAMES[7]=[==========>   ]"
set "FRAMES[8]=[===========>  ]"
set "FRAMES[9]=[============> ]"
set "FRAMES[10]=[============>]"

for /L %%I in (0,1,10) do (
	cls
	echo.
	echo ================================
	echo  Flask Code 1.2 Installer
	echo ================================
	echo.
	echo Downloading Files from GitHub
	echo.
	echo !FRAMES[%%I]! 100%% [!TOTAL!/!TOTAL!]
	echo    Creating .apikeys file...
	timeout /t 0 >nul 2>&1
)

endlocal
exit /b 0

REM ==================== SCAN FILES FUNCTION ====================

:scan_files
setlocal enabledelayedexpansion
set "FILE_COUNT=0"

for %%F in ("%TEMP_DIR%\*") do (
	set /a FILE_COUNT+=1
	set "FILENAME=%%~nxF"
	for %%A in ("%%F") do set "SIZE=%%~zA"
	
	REM Animated scan progress
	call :animate_scan "!FILENAME!" "!SIZE!" !FILE_COUNT!
	
	REM Scan for malicious patterns
	findstr /i "remove.*file delete.*system malware.*virus backdoor.*shell" "%%F" >nul 2>&1
	if errorlevel 1 (
		echo    Status: OK
	) else (
		echo    Status: WARNING - Contains keywords
	)
)

echo.
echo Scanned !FILE_COUNT! files successfully

endlocal
exit /b 0

REM ==================== ANIMATE SCAN ====================

:animate_scan
setlocal enabledelayedexpansion
set "FILENAME=%~1"
set "SIZE=%~2"
set "CURRENT=%~3"

REM Animation frames
set "FRAMES[0]=[#..........]"
set "FRAMES[1]=[##.........]"
set "FRAMES[2]=[###........]"
set "FRAMES[3]=[####.......]"
set "FRAMES[4]=[#####......]"
set "FRAMES[5]=[######.....]"
set "FRAMES[6]=[#######....]"
set "FRAMES[7]=[########...]"
set "FRAMES[8]=[#########..]"
set "FRAMES[9]=[##########.]"
set "FRAMES[10]=[###########]"

REM Animate through frames
for /L %%I in (0,1,10) do (
	cls
	echo.
	echo ================================
	echo  Flask Code 1.2 Installer
	echo ================================
	echo.
	echo Scanning Downloaded Files
	echo.
	echo !FRAMES[%%I]! Scanning !FILENAME! Size: !SIZE! bytes
	timeout /t 0 >nul 2>&1
)

endlocal
exit /b 0

REM ==================== MOVE FILES FUNCTION ====================

:move_files
setlocal enabledelayedexpansion
set "TOTAL_TO_MOVE=0"
set "CURRENT_MOVE=0"

REM Count total files to move
for %%F in ("%TEMP_DIR%\*") do (
	set /a TOTAL_TO_MOVE+=1
)

for %%F in ("%TEMP_DIR%\*") do (
	set /a CURRENT_MOVE+=1
	set "FILENAME=%%~nxF"
	
	REM Animated move progress
	call :animate_move !CURRENT_MOVE! !TOTAL_TO_MOVE! "!FILENAME!"
	
	REM Move file
	move "%%F" "%INSTALL_DIR%!FILENAME!" >nul 2>&1
)

echo.
echo Moved !CURRENT_MOVE! files successfully

endlocal
exit /b 0

REM ==================== ANIMATE MOVE ====================

:animate_move
setlocal enabledelayedexpansion
set "CURRENT=%~1"
set "TOTAL=%~2"
set "FILENAME=%~3"

REM Animation frames
set "FRAMES[0]=[=----------]"
set "FRAMES[1]=[==---------]"
set "FRAMES[2]=[===--------]"
set "FRAMES[3]=[====-------]"
set "FRAMES[4]=[=====------]"
set "FRAMES[5]=[======-----]"
set "FRAMES[6]=[=======----]"
set "FRAMES[7]=[========---]"
set "FRAMES[8]=[=========--]"
set "FRAMES[9]=[==========-]"
set "FRAMES[10]=[===========]"

REM Animate through frames
for /L %%I in (0,1,10) do (
	cls
	echo.
	echo ================================
	echo  Flask Code 1.2 Installer
	echo ================================
	echo.
	echo Moving Files to Install Dir
	echo.
	echo !FRAMES[%%I]! Moving Files [!CURRENT!/!TOTAL!]
	timeout /t 0 >nul 2>&1
)

echo !FRAMES[10]! Moving Files [!CURRENT!/!TOTAL!]
echo    Moved: !FILENAME!

endlocal
exit /b 0