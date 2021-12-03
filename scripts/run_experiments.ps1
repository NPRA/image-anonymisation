 # Install and import the `powershell-yaml` module
# Install module has a -Force -Verbose -Scope CurrentUser arguments which might be necessary in your CI/CD environment to install the module
# Install-Module -Name powershell-yaml -Force -Verbose -Scope CurrentUser
Import-Module powershell-yaml
 
# LoadYml function that will read YML file and deserialize it
function LoadYml {
    param (
        $FileName
    )
	# Load file content to a string array containing all YML file lines
    [string[]]$fileContent = Get-Content $FileName
    $content = ''
    # Convert a string array to a string
    foreach ($line in $fileContent) { $content = $content + "`n" + $line }
    # Deserialize a string to the PowerShell object
    $yml = ConvertFrom-YAML $content
    # return the object
    Write-Output $yml
}
 
# WriteYml function that writes the YML content to a file
function WriteYml {
    param (
        $FileName,
        $Content
    )
	#Serialize a PowerShell object to string
    $result = ConvertTo-YAML $Content
    
    $result
    #write to a file
    Set-Content -Path $FileName -Value $result

    # Replace some serialized values in the .yaml file
    (Get-Content $FileName).replace('false', 'False') | Set-Content $FileName
    (Get-Content $FileName).replace('true', 'True') | Set-Content $FileName
    (Get-Content $FileName).replace('"', '') | Set-Content $FileName

}
 
# Loading yml, setting new values and writing it back to disk
$yml = LoadYml $Env:360_TEST_CONFIG
#$yml.data.param2 = $
#$yml.footer.body = $FooterBody
#WriteYml "sample.yml" $yml
<#$newConfigRootFolder = "tmp/configs"
mkdir -Force "tmp/configs"
$config_options = @{
    cutout_step_factor = @([1000, 800], @(1000, 900), @(1000, 1100), @(900, 2000));
    #mask_dilation_pixels = @(30);
    #blur = @(10, 8, 4)
    # normalized_gray_blur = @("False")

}#>

# Iterate over the different variations of config options.
<#foreach ($feature in $config_options.keys) {
    foreach ($option in $config_options.$feature) {
        $option
        $yml.$feature = $option
        $yml.mask_color = "null"
        $confg_yml_file = "$newConfigRootFolder/$feature"+"_$option.yml"
        WriteYml $confg_yml_file $yml
    }
}#>

#$input_folder = "C:\Users\norpal\Documents\E6_360_ViaTech"
$input_folder = $Env:EXPERIMENT_INPUT_FOLDER
#$output_folder_base_name = "C:\Users\norpal\Documents\out\E6_360_ViaTech_"
$output_folder_base_name = $Env:EXPERIMENT_OUTPUT_FOLDER_BASE
$log_folder_base_name = $Env:EXPERIMENT_LOG_FOLDER_BASE

$tmp_config_dirs = dir "tmp/configs"
$num_experiments = Get-ChildItem $tmp_config_dirs -Recurse -File | Measure-Object | %{$_.Count}

"Running one iteration of image anonymisation"
$step = $yml.cutout_step_factor
$dim = $yml.cutout_dim_downscale
$output = "$output_folder_base_name"
$log = "$log_folder_base_name#"
#: planar
# $configfile = $Env:DEFAULT_CONFIG
#$configfile = $Env:PLANAR_TEST_CONFIG
 # 360
$configfile = $Env:360_TEST_CONFIG
# $archive_file = $Env:EXPERIMENT_ARCHIVE_FOLDER_BASE
#$configfile = $Env:PLANAR_TEST_CONFIG
# cd to root folder
#python create_json.py -i $input_folder -o $output -l $log -k $configfile
cd $Env:PROJECT_ROOT_FOLDER
#python -m src.main -i $input_folder -o $output -l $log
#python -m src.main -i $input_folder -o $output -l $log -k $configfile
python -m scripts.create_json -i $input_folder -o $output -l $log -k $configfile

#: Cd back to script folder
cd "$Env:PROJECT_ROOT_FOLDER\\scripts"

#"Running a total of $num_experiments experiments...`n`n"

# run image anonymisation
<#foreach($file in  $tmp_config_dirs){


    "@@@@@@@@@@@@@@@@@@@@@@@@ Experiment $file @@@@@@@@@@@@@@@@@@@@@@@@"

    $yml = LoadYml $file.FullName
    $param_tuning = $yml.cutout_step_factor
    #"$param_tuning"
    $output = "$output_folder_base_name\\step_$param_tuning"
    $log = "$log_folder_base_name\\step_$param_tuning"
    $option = $file.BaseName
    $configfile = $file.FullName

    "CONFIG: $configfile"
    "OPTION: $option"
    "LOG: $log"
    "OUTPUT: $output"
    #"$option, $output, $log, $configfile"
    # cd to root of folder
    cd $Env:PROJECT_ROOT_FOLDER

    # Run the image anonymisation
    # Planar
    #python -m src.main -i $input_folder -o $output -l $log
    python -m src.main -i $input_folder -o $output -l $log -k $configfile

    #python -m src.main -i $input_folder -o $output_folder_base_name -l $log -k $configfile
    # cd back to script folder
    cd "$Env:PROJECT_ROOT_FOLDER\\scripts"
    "Finished experiment`n"
 }#>
"Finished script`n"
