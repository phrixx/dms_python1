# BOBO Processor Windows Wrapper Script
# This script ensures proper execution environment and prevents multiple instances

param(
    [string]$ScriptPath = $PSScriptRoot,
    [string]$LogPath = "../logs",
    [int]$TimeoutMinutes = 30
)

# Set working directory
Set-Location $ScriptPath

# Check if another instance is already running
$processName = "python"
$scriptName = "bobo_processor.py"
$runningProcesses = Get-Process -Name $processName -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*$scriptName*" }

if ($runningProcesses) {
    Write-Host "$(Get-Date): BOBO processor is already running (PID: $($runningProcesses.Id -join ', '))"
    
    # Check if process has been running too long (stuck)
    foreach ($proc in $runningProcesses) {
        $runtime = (Get-Date) - $proc.StartTime
        if ($runtime.TotalMinutes -gt $TimeoutMinutes) {
            Write-Warning "$(Get-Date): Process $($proc.Id) has been running for $($runtime.TotalMinutes.ToString('F1')) minutes, terminating..."
            Stop-Process -Id $proc.Id -Force
            Start-Sleep -Seconds 5
        } else {
            Write-Host "$(Get-Date): Process $($proc.Id) running normally ($($runtime.TotalMinutes.ToString('F1')) minutes)"
            exit 0
        }
    }
}

# Ensure log directory exists
$fullLogPath = Join-Path $ScriptPath $LogPath
if (-not (Test-Path $fullLogPath)) {
    New-Item -ItemType Directory -Path $fullLogPath -Force | Out-Null
}

# Set up logging
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$wrapperLogFile = Join-Path $fullLogPath "bobo_wrapper_$timestamp.log"

try {
    Write-Host "$(Get-Date): Starting BOBO processor..."
    
    # Verify Python installation
    $pythonVersion = & python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found in PATH. Please ensure Python is installed and accessible."
    }
    Write-Host "$(Get-Date): Using $pythonVersion"
    
    # Verify script exists
    if (-not (Test-Path "bobo_processor.py")) {
        throw "bobo_processor.py not found in current directory: $PWD"
    }
    
    # Verify .env file exists
    if (-not (Test-Path ".env")) {
        Write-Warning "$(Get-Date): .env file not found. Please create from .env_safe template."
        throw ".env configuration file missing"
    }
    
    # Run the processor with timeout
    $job = Start-Job -ScriptBlock {
        param($workingDir)
        Set-Location $workingDir
        & python bobo_processor.py 2>&1
    } -ArgumentList $PWD
    
    # Wait for completion or timeout
    $completed = Wait-Job -Job $job -Timeout ($TimeoutMinutes * 60)
    
    if ($completed) {
        $output = Receive-Job -Job $job
        $exitCode = $job.State
        
        if ($job.State -eq "Completed") {
            Write-Host "$(Get-Date): BOBO processor completed successfully"
            if ($output) {
                Write-Host "Output: $output"
            }
        } else {
            Write-Error "$(Get-Date): BOBO processor failed with state: $($job.State)"
            if ($output) {
                Write-Error "Error output: $output"
            }
        }
    } else {
        Write-Warning "$(Get-Date): BOBO processor timed out after $TimeoutMinutes minutes, stopping job..."
        Stop-Job -Job $job
        throw "Process timed out"
    }
    
    Remove-Job -Job $job -Force
    
} catch {
    $errorMessage = "$(Get-Date): Error running BOBO processor: $($_.Exception.Message)"
    Write-Error $errorMessage
    
    # Log to wrapper log file
    Add-Content -Path $wrapperLogFile -Value $errorMessage
    
    # Exit with error code
    exit 1
} finally {
    Write-Host "$(Get-Date): BOBO processor wrapper finished"
}

# Clean up old wrapper logs (keep last 7 days)
try {
    $cutoffDate = (Get-Date).AddDays(-7)
    Get-ChildItem -Path $fullLogPath -Name "bobo_wrapper_*.log" | 
        Where-Object { 
            $fileDate = [DateTime]::ParseExact($_.Substring(13, 19), "yyyy-MM-dd_HH-mm-ss", $null)
            $fileDate -lt $cutoffDate 
        } | 
        ForEach-Object { Remove-Item -Path (Join-Path $fullLogPath $_) -Force }
} catch {
    Write-Warning "$(Get-Date): Could not clean up old wrapper logs: $($_.Exception.Message)"
}

exit 0 