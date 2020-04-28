param (
    [Parameter(Mandatory=$true)][string]$input_folder,
    [Parameter(Mandatory=$true)][string]$output_folder,
    [string]$archive_folder,
    [string]$log_folder,
    [string]$python_module = "src.main",
    [string]$conda_env_name = "image-anonymisation",
    [string]$conda_path,
    [string]$oracle_client_path
)

# Configure arguments to script
$python_args = "-i $input_folder -o $output_folder"
# Add the archive argument if it is not empty
if ($archive_folder) { $python_args = "$python_args -a $archive_folder" }
# Add the log-folder argument if it is not empty
if ($log_folder) { $python_args = "$python_args -l $log_folder" }

$old_path = $env:PATH
if ($oracle_client_path) {
    $env:PATH += ";$oracle_client_path"
}

# Run the conda-hook script which gives us the `conda` command.
if ($conda_path) { Invoke-Expression -Command "$conda_path\shell\condabin\conda-hook.ps1" }
# Activate the environment
conda activate $conda_env_name

# Run the script
echo "Running script..."
Invoke-Expression -Command "python -m $python_module $python_args"
echo "Done running script"

# Deactivate the conda environment.
conda deactivate
# Reset the PATH environment variable
$env:PATH = $old_path