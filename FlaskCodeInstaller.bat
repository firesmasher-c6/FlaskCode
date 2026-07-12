@echo off
setlocal enabledelayedexpansion

REM FlaskCode Universal Installer
REM Fetches releases.json from GitHub -> user picks type + version -> downloads all assets

set "INSTALL_DIR=%~dp0"
set "TEMP_DIR=%INSTALL_DIR%_fcinstall_temp"
set "JSON_URL=https://raw.githubusercontent.com/firesmasher-c6/FlaskCode/refs/heads/main/tags/releases/releases.json"
set "JSON_CACHE=%TEMP%\flaskcode_releases.json"

REM ==================== HEADER ====================

cls
echo.
echo ==================================
echo  FlaskCode Installer
echo  Install Any Type Of FlaskCode.
echo ==================================
echo.
echo Fetching release information from GitHub...
echo.

REM ==================== FETCH releases.json ====================

powershell -Command "Invoke-WebRequest -Uri '%JSON_URL%' -OutFile '%JSON_CACHE%' -ErrorAction Stop" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Could not fetch releases.json from GitHub.
    echo Make sure you have an internet connection and try again.
    echo.
    pause
    exit /b 1
)

if not exist "%JSON_CACHE%" (
    echo ERROR: releases.json was not saved correctly.
    echo.
    pause
    exit /b 1
)

REM ==================== TYPE SELECTION ====================

cls
echo.
echo ==================================
echo  FlaskCode Installer
echo  Install Any Type Of FlaskCode.
echo ==================================
echo.
echo Installer^> Which type do you want to install?
echo Installer^> Client-Side = Only for computers with screens, process on your computer.
echo Installer^> Server      = The Flask Code Server designed for linux servers (e.g. Ubuntu Server).
echo Installer^> Client      = Lightweight application that lets you connect to a FlaskCode server.
echo Installer^> For client-side type 1, server type 2, client type 3. [1^|2^|3]
echo.
set /p "USER_TYPE=You> "

if "%USER_TYPE%"=="1" (
    set "TYPE_KEY=client-side"
    set "TYPE_LABEL=Client-Side"
) else if "%USER_TYPE%"=="2" (
    set "TYPE_KEY=servers"
    set "TYPE_LABEL=Server"
) else if "%USER_TYPE%"=="3" (
    set "TYPE_KEY=client"
    set "TYPE_LABEL=Client"
) else (
    echo.
    echo ERROR: Invalid choice. Please run the installer again and type 1, 2, or 3.
    echo.
    pause
    exit /b 1
)

echo.
echo Installer^> Selected !TYPE_LABEL!!

REM ==================== FETCH VERSIONS FOR CHOSEN TYPE ====================

REM Use PowerShell to extract version list and asset URLs from the JSON
REM For servers, the structure is servers -> linux -> versions

if "%USER_TYPE%"=="2" (
    REM Server: path is [0].servers.linux.<version>
    powershell -NoProfile -Command ^
        "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
        "$entry = $json[0].servers.linux; " ^
        "$versions = $entry.PSObject.Properties.Name; " ^
        "$versions -join ',' | Out-File '%TEMP%\fc_versions.txt' -Encoding ASCII -NoNewline"
) else if "%USER_TYPE%"=="1" (
    REM Client-Side: path is [0].'client-side'.<version>
    powershell -NoProfile -Command ^
        "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
        "$entry = $json[0].'client-side'; " ^
        "$versions = $entry.PSObject.Properties.Name; " ^
        "$versions -join ',' | Out-File '%TEMP%\fc_versions.txt' -Encoding ASCII -NoNewline"
) else (
    REM Client: path is [0].client.<version>
    powershell -NoProfile -Command ^
        "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
        "$entry = $json[0].client; " ^
        "$versions = $entry.PSObject.Properties.Name; " ^
        "$versions -join ',' | Out-File '%TEMP%\fc_versions.txt' -Encoding ASCII -NoNewline"
)

set /p AVAILABLE_VERSIONS=<"%TEMP%\fc_versions.txt"
del "%TEMP%\fc_versions.txt" >nul 2>&1

if "!AVAILABLE_VERSIONS!"=="" (
    echo.
    echo ERROR: Could not read versions for !TYPE_LABEL! from releases.json.
    echo.
    pause
    exit /b 1
)

REM ==================== VERSION SELECTION ====================

echo.
echo Installer^> What version to install: !AVAILABLE_VERSIONS!
echo Installer^> Type the literal string of the version
echo.
set /p "USER_VERSION=You> "

REM Validate that the chosen version exists in the list
set "VERSION_VALID=0"
for %%V in (!AVAILABLE_VERSIONS!) do (
    if /i "%%V"=="!USER_VERSION!" set "VERSION_VALID=1"
)

if "!VERSION_VALID!"=="0" (
    echo.
    echo ERROR: Version "!USER_VERSION!" not found. Available: !AVAILABLE_VERSIONS!
    echo.
    pause
    exit /b 1
)

echo.
echo Installer^> Installing !TYPE_LABEL! !USER_VERSION!
echo.

REM ==================== EXTRACT ASSET LIST FROM JSON ====================

REM Write each filename and URL pair to a temp list file
if "%USER_TYPE%"=="2" (
    powershell -NoProfile -Command ^
        "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
        "$assets = $json[0].servers.linux.'!USER_VERSION!'.assets.PSObject.Properties; " ^
        "foreach ($a in $assets) { '%a.Name%|' + $a.Value | Out-File '%TEMP%\fc_assets.txt' -Append -Encoding ASCII }"
) else if "%USER_TYPE%"=="1" (
    powershell -NoProfile -Command ^
        "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
        "$assets = $json[0].'client-side'.'!USER_VERSION!'.assets.PSObject.Properties; " ^
        "foreach ($a in $assets) { $a.Name + '|' + $a.Value | Out-File '%TEMP%\fc_assets.txt' -Append -Encoding ASCII }"
) else (
    powershell -NoProfile -Command ^
        "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
        "$assets = $json[0].client.'!USER_VERSION!'.assets.PSObject.Properties; " ^
        "foreach ($a in $assets) { $a.Name + '|' + $a.Value | Out-File '%TEMP%\fc_assets.txt' -Append -Encoding ASCII }"
)

if not exist "%TEMP%\fc_assets.txt" (
    echo ERROR: Could not extract asset list for !TYPE_LABEL! !USER_VERSION!.
    echo.
    pause
    exit /b 1
)

REM ==================== COUNT TOTAL ASSETS ====================

set "TOTAL_FILES=0"
for /f "usebackq delims=" %%L in ("%TEMP%\fc_assets.txt") do (
    set /a TOTAL_FILES+=1
)

if "!TOTAL_FILES!"=="0" (
    echo ERROR: No assets found for !TYPE_LABEL! !USER_VERSION!.
    echo.
    pause
    exit /b 1
)

REM ==================== PREPARE TEMP DIR ====================

if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >nul 2>&1
mkdir "%TEMP_DIR%"

REM ==================== DOWNLOAD ALL ASSETS ====================

set "CURRENT_FILE=0"
set "DOWNLOAD_ERRORS=0"

for /f "usebackq delims=" %%L in ("%TEMP%\fc_assets.txt") do (
    set /a CURRENT_FILE+=1

    REM Split line into filename and URL on the | delimiter
    for /f "tokens=1,2 delims=|" %%A in ("%%L") do (
        set "DL_FILENAME=%%A"
        set "DL_URL=%%B"
    )

    REM Convert github.com blob URLs to raw.githubusercontent.com
    set "DL_URL=!DL_URL:github.com/firesmasher-c6/FlaskCode/blob/=raw.githubusercontent.com/firesmasher-c6/FlaskCode/!"

    REM Animate then download
    call :animate_download "!DL_FILENAME!" !CURRENT_FILE! !TOTAL_FILES! "!TYPE_LABEL!" "!USER_VERSION!"

    set "TEMPFILE=%TEMP_DIR%\!DL_FILENAME!"

    powershell -Command "Invoke-WebRequest -Uri '!DL_URL!' -OutFile '!TEMPFILE!' -ErrorAction Stop" >nul 2>&1
    if errorlevel 1 (
        echo    ERROR: Failed to download !DL_FILENAME!
        set /a DOWNLOAD_ERRORS+=1
    ) else (
        for %%A in ("!TEMPFILE!") do set "SIZE=%%~zA"
        echo    Downloaded: !SIZE! bytes
    )
)

del "%TEMP%\fc_assets.txt" >nul 2>&1

REM ==================== DOWNLOAD COMPLETE ANIMATION ====================

call :animate_download_complete !TOTAL_FILES! "!TYPE_LABEL!" "!USER_VERSION!"

REM ==================== SCAN FILES ====================

echo.
echo ==================================
echo  Scanning Downloaded Files
echo ==================================
echo.

call :scan_files "!TYPE_LABEL!" "!USER_VERSION!"

REM ==================== MOVE FILES ====================

echo.
echo ==================================
echo  Moving Files to Install Dir
echo ==================================
echo.

call :move_files "!TYPE_LABEL!" "!USER_VERSION!"

REM ==================== EXTRAS ====================

REM Extract extras list from JSON
powershell -NoProfile -Command ^
    "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
    "$extras = $json[1].extras.assets.PSObject.Properties; " ^
    "$names = $extras | ForEach-Object { $_.Name }; " ^
    "$names -join ',' | Out-File '%TEMP%\fc_extras_names.txt' -Encoding ASCII -NoNewline"

set "EXTRAS_NAMES="
if exist "%TEMP%\fc_extras_names.txt" (
    set /p EXTRAS_NAMES=<"%TEMP%\fc_extras_names.txt"
    del "%TEMP%\fc_extras_names.txt" >nul 2>&1
)

echo.
echo ==================================
echo  Installation Complete!
echo ==================================
echo.

if not "!EXTRAS_NAMES!"=="" (
    echo Install Extras? !EXTRAS_NAMES! [y/N]
    echo.
    set /p "INSTALL_EXTRAS=You> "

    if /i "!INSTALL_EXTRAS!"=="y" (
        REM Build extras asset list
        powershell -NoProfile -Command ^
            "$json = Get-Content '%JSON_CACHE%' -Raw | ConvertFrom-Json; " ^
            "$extras = $json[1].extras.assets.PSObject.Properties; " ^
            "foreach ($e in $extras) { $e.Name + '|' + $e.Value.downloadUrl | Out-File '%TEMP%\fc_extras.txt' -Append -Encoding ASCII }"

        set "EXTRA_TOTAL=0"
        for /f "usebackq delims=" %%L in ("%TEMP%\fc_extras.txt") do (
            set /a EXTRA_TOTAL+=1
        )

        set "EXTRA_CURRENT=0"
        for /f "usebackq delims=" %%L in ("%TEMP%\fc_extras.txt") do (
            set /a EXTRA_CURRENT+=1
            for /f "tokens=1,2 delims=|" %%A in ("%%L") do (
                set "EX_FILENAME=%%A"
                set "EX_URL=%%B"
            )
            REM Convert blob URLs to raw
            set "EX_URL=!EX_URL:github.com/firesmasher-c6/FlaskCode/blob/=raw.githubusercontent.com/firesmasher-c6/FlaskCode/!"

            call :animate_download "!EX_FILENAME!" !EXTRA_CURRENT! !EXTRA_TOTAL! "Extras" "optional"

            set "EX_TEMPFILE=%TEMP_DIR%\!EX_FILENAME!"
            powershell -Command "Invoke-WebRequest -Uri '!EX_URL!' -OutFile '!EX_TEMPFILE!' -ErrorAction Stop" >nul 2>&1
            if errorlevel 1 (
                echo    ERROR: Failed to download !EX_FILENAME!
            ) else (
                for %%A in ("!EX_TEMPFILE!") do set "EX_SIZE=%%~zA"
                echo    Downloaded: !EX_SIZE! bytes
            )
        )

        call :animate_download_complete !EXTRA_TOTAL! "Extras" "optional"

        REM Move extras to install dir
        for %%F in ("%TEMP_DIR%\*") do (
            move "%%F" "%INSTALL_DIR%%%~nxF" >nul 2>&1
        )

        del "%TEMP%\fc_extras.txt" >nul 2>&1
        echo    Extras installed successfully.
        echo.
    ) else (
        echo    Skipped extras.
        echo.
    )
) else (
    echo No extras available for this release.
    echo.
)

REM ==================== PIP ====================

echo ==================================
echo  Install Pip Requirements? [y/N]
echo ==================================
echo.
set /p "INSTALL_PIP=You> "

if /i "!INSTALL_PIP!"=="y" (
    echo.
    echo Installing pip requirements...
    if exist "%INSTALL_DIR%requirements.txt" (
        python -m pip install -r "%INSTALL_DIR%requirements.txt"
        if errorlevel 1 (
            echo WARNING: pip install had issues.
        ) else (
            echo pip requirements installed successfully!
        )
    ) else (
        echo WARNING: requirements.txt not found. Skipping.
    )
) else (
    echo Skipped pip installation.
)

REM ==================== CLEANUP ====================

if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >nul 2>&1
if exist "%JSON_CACHE%" del "%JSON_CACHE%" >nul 2>&1

REM ==================== SUMMARY ====================

echo.
echo ==================================
echo  Installation Summary
echo ==================================
echo.
echo Type:     !TYPE_LABEL!
echo Version:  !USER_VERSION!
echo Location: !INSTALL_DIR!
echo Files:    !TOTAL_FILES! assets downloaded
if "!DOWNLOAD_ERRORS!" neq "0" (
    echo Errors:   !DOWNLOAD_ERRORS! file(s) failed to download
)
echo.
echo ==================================
echo  Done!
echo ==================================
echo.
echo Press ENTER to close this window...
pause >nul
exit /b

REM ==================== :animate_download ====================
REM Args: %1=filename %2=current %3=total %4=type_label %5=version

:animate_download
setlocal enabledelayedexpansion
set "FILENAME=%~1"
set "CURRENT=%~2"
set "TOTAL=%~3"
set "ALABEL=%~4"
set "AVERSION=%~5"

set /a OVERALL_PERCENT=(CURRENT*100)/TOTAL

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

for /L %%I in (0,1,10) do (
    cls
    echo.
    echo ==================================
    echo  FlaskCode Installer
    echo  !ALABEL! !AVERSION!
    echo ==================================
    echo.
    echo Downloading Files from GitHub
    echo.
    echo !FRAMES[%%I]! !OVERALL_PERCENT!%% [!CURRENT!/!TOTAL!]
    echo    Downloading: !FILENAME!
    timeout /t 0 >nul 2>&1
)

endlocal
exit /b 0

REM ==================== :animate_download_complete ====================
REM Args: %1=total %2=type_label %3=version

:animate_download_complete
setlocal enabledelayedexpansion
set "TOTAL=%~1"
set "ALABEL=%~2"
set "AVERSION=%~3"

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

for /L %%I in (0,1,10) do (
    cls
    echo.
    echo ==================================
    echo  FlaskCode Installer
    echo  !ALABEL! !AVERSION!
    echo ==================================
    echo.
    echo Downloading Files from GitHub
    echo.
    echo !FRAMES[%%I]! 100%% [!TOTAL!/!TOTAL!]
    echo    All files downloaded!
    timeout /t 0 >nul 2>&1
)

endlocal
exit /b 0

REM ==================== :scan_files ====================
REM Args: %1=type_label %2=version

:scan_files
setlocal enabledelayedexpansion
set "ALABEL=%~1"
set "AVERSION=%~2"
set "FILE_COUNT=0"

for %%F in ("%TEMP_DIR%\*") do (
    set /a FILE_COUNT+=1
    set "FILENAME=%%~nxF"
    for %%A in ("%%F") do set "SIZE=%%~zA"

    call :animate_scan "!FILENAME!" "!SIZE!" !FILE_COUNT! "!ALABEL!" "!AVERSION!"

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

REM ==================== :animate_scan ====================
REM Args: %1=filename %2=size %3=current %4=type_label %5=version

:animate_scan
setlocal enabledelayedexpansion
set "FILENAME=%~1"
set "SIZE=%~2"
set "CURRENT=%~3"
set "ALABEL=%~4"
set "AVERSION=%~5"

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

for /L %%I in (0,1,10) do (
    cls
    echo.
    echo ==================================
    echo  FlaskCode Installer
    echo  !ALABEL! !AVERSION!
    echo ==================================
    echo.
    echo Scanning Downloaded Files
    echo.
    echo !FRAMES[%%I]! Scanning !FILENAME! Size: !SIZE! bytes
    timeout /t 0 >nul 2>&1
)

endlocal
exit /b 0

REM ==================== :move_files ====================
REM Args: %1=type_label %2=version

:move_files
setlocal enabledelayedexpansion
set "ALABEL=%~1"
set "AVERSION=%~2"
set "TOTAL_TO_MOVE=0"
set "CURRENT_MOVE=0"

for %%F in ("%TEMP_DIR%\*") do (
    set /a TOTAL_TO_MOVE+=1
)

for %%F in ("%TEMP_DIR%\*") do (
    set /a CURRENT_MOVE+=1
    set "FILENAME=%%~nxF"

    call :animate_move !CURRENT_MOVE! !TOTAL_TO_MOVE! "!FILENAME!" "!ALABEL!" "!AVERSION!"

    move "%%F" "%INSTALL_DIR%!FILENAME!" >nul 2>&1
)

echo.
echo Moved !CURRENT_MOVE! files successfully

endlocal
exit /b 0

REM ==================== :animate_move ====================
REM Args: %1=current %2=total %3=filename %4=type_label %5=version

:animate_move
setlocal enabledelayedexpansion
set "CURRENT=%~1"
set "TOTAL=%~2"
set "FILENAME=%~3"
set "ALABEL=%~4"
set "AVERSION=%~5"

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

for /L %%I in (0,1,10) do (
    cls
    echo.
    echo ==================================
    echo  FlaskCode Installer
    echo  !ALABEL! !AVERSION!
    echo ==================================
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
