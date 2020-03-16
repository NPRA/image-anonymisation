@echo off

:: Python script to run
set pythonModule="src.main"
:: Name of conda environment
set condaEnvName="image-anonymisation"

:: Clear variables from potential previous execution
set inputDir=
set outputDir=
set archDir=
set logDir=
:: Get paths from user
set /p inputDir="Enter input folder: "
set /p outputDir="Enter output folder: "
set /p archDir="Enter archive folder (leave this blank to disable archiving): "
set /p logDir="Enter logging folder (leave this blank to disable file logging): "

:: Check for empty input and output paths
IF [%inputDir%] == [] echo Error: Input folder cannot be empty && exit /b
IF [%outputDir%] == [] echo Error: Output folder cannot be empty && exit /b

:: Activate the environment
:: call conda activate %condaEnvName%
call C:\Users\dantro\AppData\Local\Continuum\anaconda3\condabin\activate.bat %condaEnvName%
:: If `conda` is not on the PATH, replace the above with:
:: call \path\to\anaconda\condabin\activate.bat %condaEnvName%

:: Arguments to module call
set moduleArgs="-i" %inputDir% "-o" %outputDir%
:: Append the archive argument if it is non-empty
IF NOT [%archDir%] == [] set moduleArgs=%moduleArgs% "-a" %archDir%
:: Append th log-dir argument if it is not empty
IF NOT [%logDir%] == [] set moduleArgs=%moduleArgs% "-l" %logDir%

:: Run
echo Running script...
python -m %pythonModule% %moduleArgs%
echo Done running script.

:: Deactivate environment
call conda deactivate
