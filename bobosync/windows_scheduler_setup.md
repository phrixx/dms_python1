# Windows Task Scheduler Setup Guide

This guide explains how to configure the BOBO processor to run automatically on Windows every minute using Windows Task Scheduler.

## Quick Setup (Recommended)

### 1. Choose Your Wrapper Script

**PowerShell Wrapper (Recommended):**
- `run_bobo_windows.ps1` - Advanced error handling, process management, timeout protection
- Best for production environments

**Batch File Wrapper (Simple):**
- `run_bobo_windows.bat` - Basic error handling, easier to understand
- Good for simple setups

### 2. Test the Wrapper Manually

Before setting up the scheduler, test your chosen wrapper:

```cmd
# Test PowerShell wrapper
cd C:\path\to\your\dms_python\bobosync
powershell -ExecutionPolicy Bypass -File "run_bobo_windows.ps1"

# OR test Batch wrapper
cd C:\path\to\your\dms_python\bobosync
run_bobo_windows.bat
```

### 3. Create the Scheduled Task

**Option A: Using PowerShell (Quick Setup)**
```powershell
# Run PowerShell as Administrator
$taskName = "BOBO Sync Processor"
$scriptPath = "C:\path\to\your\dms_python\bobosync"
$scriptFile = "run_bobo_windows.ps1"  # or "run_bobo_windows.bat"

# Create the action
if ($scriptFile -like "*.ps1") {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$scriptPath\$scriptFile`"" -WorkingDirectory $scriptPath
} else {
    $action = New-ScheduledTaskAction -Execute "$scriptPath\$scriptFile" -WorkingDirectory $scriptPath
}

# Create the trigger (every minute)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 365)

# Create the principal (run as SYSTEM with highest privileges)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Create the settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Processes BOBO CSV files and syncs to AtHoc every minute"

Write-Host "Task '$taskName' created successfully!"
```

**Option B: Using Task Scheduler GUI**

1. **Open Task Scheduler**
   - Press `Win + R`, type `taskschd.msc`, press Enter
   - Or search for "Task Scheduler" in Start menu

2. **Create Basic Task**
   - Right-click "Task Scheduler Library" → "Create Basic Task"
   - Name: `BOBO Sync Processor`
   - Description: `Processes BOBO CSV files and syncs to AtHoc every minute`

3. **Configure Trigger**
   - When: Daily
   - Start: Today, current time
   - Recur every: 1 days
   - ✅ Repeat task every: 1 minute
   - ✅ for a duration of: Indefinitely

4. **Configure Action**
   
   **For PowerShell wrapper:**
   ```
   Program/script: powershell.exe
   Add arguments: -ExecutionPolicy Bypass -File "run_bobo_windows.ps1"
   Start in: C:\path\to\your\dms_python\bobosync
   ```
   
   **For Batch wrapper:**
   ```
   Program/script: C:\path\to\your\dms_python\bobosync\run_bobo_windows.bat
   Add arguments: (leave empty)
   Start in: C:\path\to\your\dms_python\bobosync
   ```

5. **Advanced Settings**
   - ✅ Run whether user is logged on or not
   - ✅ Run with highest privileges
   - ✅ Wake the computer to run this task

## Important Considerations

### Frequency Recommendations

**Every Minute May Be Excessive:**
- Consider if you really need minute-by-minute processing
- Most BOBO systems don't generate data that frequently
- More frequent = higher system load and log volume

**Alternative Schedules:**
- **Every 5 minutes**: Good balance for most use cases
- **Every 15 minutes**: Suitable for less time-critical operations
- **Every hour**: For batch processing scenarios

**To Change Frequency:**
- Modify the trigger repetition interval in Task Scheduler
- Or change `-RepetitionInterval (New-TimeSpan -Minutes 5)` in PowerShell setup

### System Requirements

**Permissions:**
- Task must run with elevated privileges
- User account needs permission to write to log directories
- Access to AtHoc server URLs

**Resources:**
- Ensure adequate disk space for logs
- Monitor memory usage if running very frequently
- Consider network bandwidth to AtHoc server

### Process Management

**The wrapper scripts handle:**
- ✅ Preventing multiple simultaneous instances
- ✅ Timeout protection (30-minute default)
- ✅ Error logging and reporting
- ✅ Working directory management
- ✅ Log file cleanup

**Built-in Safety Features:**
- If processor is already running, skip execution
- Kill stuck processes after timeout
- Comprehensive error logging
- Automatic log cleanup (7-day retention)

## Monitoring and Troubleshooting

### Check Task Status
```powershell
# Get task information
Get-ScheduledTask -TaskName "BOBO Sync Processor"

# Get task history
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TaskScheduler/Operational'; ID=200,201} | 
    Where-Object {$_.Message -like "*BOBO Sync Processor*"} | 
    Select-Object TimeCreated, Id, LevelDisplayName, Message
```

### Log Locations
- **Wrapper Logs**: `../logs/bobo_wrapper_YYYY-MM-DD_HH-mm-ss.log`
- **Processor Logs**: `../logs/bobo_processor.log`
- **Windows Task Logs**: Event Viewer → Windows Logs → System

### Common Issues and Solutions

**Task Not Running:**
1. Check if task is enabled in Task Scheduler
2. Verify trigger conditions are met
3. Check user permissions and "Run as" settings
4. Look for errors in Event Viewer

**Python Not Found:**
1. Ensure Python is in system PATH
2. Or use full path: `C:\Python\python.exe`
3. Test from command prompt: `python --version`

**Permission Denied:**
1. Run Task Scheduler as Administrator
2. Set task to "Run with highest privileges"
3. Check file/directory permissions

**Process Running Too Long:**
1. Check AtHoc connectivity
2. Review log files for stuck operations
3. Adjust timeout in wrapper script
4. Consider reducing batch size

### Performance Optimization

**For High-Frequency Execution:**
```bash
# In .env file, optimize these settings:
BATCH_SIZE=5                    # Smaller batches for faster processing
LOG_LEVEL=WARNING               # Reduce log volume
AUTO_CLEANUP_HOURS=12           # More frequent cleanup
MOVE_PROCESSED_FILES=true       # Prevent file accumulation
```

**Monitor System Impact:**
- CPU usage during execution
- Memory usage growth
- Disk space consumption
- Network traffic to AtHoc

## Testing the Setup

### 1. Manual Test
```cmd
# Test the wrapper script directly
cd C:\path\to\your\dms_python\bobosync
run_bobo_windows.ps1  # or .bat

# Check for errors and verify log output
```

### 2. Task Scheduler Test
```cmd
# Run task manually from Task Scheduler
# Right-click task → Run

# Or from PowerShell
Start-ScheduledTask -TaskName "BOBO Sync Processor"
```

### 3. Monitor First Few Executions
- Watch for successful executions in Task Scheduler
- Check wrapper logs for any issues
- Verify BOBO processor logs show normal operation
- Confirm no file accumulation in source directory

## Disabling/Modifying the Task

**Temporarily Disable:**
```powershell
Disable-ScheduledTask -TaskName "BOBO Sync Processor"
```

**Re-enable:**
```powershell
Enable-ScheduledTask -TaskName "BOBO Sync Processor"
```

**Modify Frequency:**
```powershell
# Change to every 5 minutes
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365)
Set-ScheduledTask -TaskName "BOBO Sync Processor" -Trigger $trigger
```

**Remove Completely:**
```powershell
Unregister-ScheduledTask -TaskName "BOBO Sync Processor" -Confirm:$false
```

This setup provides a robust, production-ready solution for automatically running the BOBO processor on Windows with proper error handling and monitoring capabilities. 