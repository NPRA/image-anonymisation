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
$yml = LoadYml $Env:DEFAULT_360_CONFIG
#$yml.data.param2 = $
#$yml.footer.body = $FooterBody
#WriteYml "sample.yml" $yml
$newConfigRootFolder = "tmp/configs"
mkdir -Force "tmp/configs"
$config_options = @{
    mask_dilation_pixels = @(20, 30, 50, 70);
    #mask_dilation_pixels = @(30);
    #blur = @(10, 8, 4)
    # normalized_gray_blur = @("False")

}

# Iterate over the different variations of config options.
<#foreach ($feature in $config_options.keys) {
    foreach ($option in $config_options.$feature) {
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
$output = "$output_folder_base_name"
$log = "$log_folder_base_name"
#: planar
# $configfile = $Env:DEFAULT_CONFIG
# 360
$configfile = $Env:DEFAULT_360_CONFIG
# cd to root folder
cd $Env:PROJECT_ROOT_FOLDER
#python -m src.main -i $input_folder -o $output -l $log
python -m src.main -i $input_folder -o $output -l $log -k $configfile

#: Cd back to script folder
cd "$Env:PROJECT_ROOT_FOLDER\\scripts"

# "Running a total of $num_experiments experiments...`n`n"
# run image anonymisation
# foreach($file in  $tmp_config_dirs){
    
    
#     "@@@@@@@@@@@@@@@@@@@@@@@@ Experiment $file @@@@@@@@@@@@@@@@@@@@@@@@"
#     $option = $file.BaseName
#     $output = "$output_folder_base_name"
#     $log = "$log_folder_base_name"
#     $configfile = $file.FullName
#     #"$option, $output, $log, $configfile"
#     # cd to root of folder
#     cd $Env:PROJECT_ROOT_FOLDER
#     # Run the image anonymisation
#     # Planar
#     python -m src.main -i $input_folder -o $output -l $log
#     python -m src.main -i $input_folder -o $output -l $log -k $configfile
    
#     #python -m src.main -i $input_folder -o $output_folder_base_name -l $log -k $configfile
#     # cd back to script folder
#     cd "$Env:PROJECT_ROOT_FOLDER\\scripts"
#     "Finished experiment`n"
# }
"Finished script`n"
