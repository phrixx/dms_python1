#!/usr/bin/env python3
"""
BOBO CSV Data Simulator
Generates random CSV data for testing the BOBO data processing utility.
Runs continuously every minute until interrupted or max file count is reached.
"""

import csv
import random
import os
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Configuration defaults
DEFAULT_CONFIG = {
    'OUTPUT_DIR': './output',
    'SIMULATION_INTERVAL': 60,
    'MIN_ENTRIES': 5,
    'MAX_ENTRIES': 25,
    'MAX_FILE_COUNT': 100
}

def load_env_config():
    """Load configuration from .env file if it exists."""
    config = DEFAULT_CONFIG.copy()
    env_file = Path('.env')
    
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Convert numeric values
                        if key in ['SIMULATION_INTERVAL', 'MIN_ENTRIES', 'MAX_ENTRIES', 'MAX_FILE_COUNT']:
                            try:
                                config[key] = int(value)
                            except ValueError:
                                print(f"Warning: Invalid numeric value for {key}: {value}")
                        else:
                            config[key] = value
        except Exception as e:
            print(f"Warning: Could not read .env file: {e}")
    
    return config

def ensure_output_directory(output_dir):
    """Create output directory if it doesn't exist."""
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Error creating output directory '{output_dir}': {e}")
        return False

def generate_random_entry(execution_time):
    """Generate a single random CSV entry following the BOBO format."""
    
    # Transaction type: BON or BOF
    transaction_type = random.choice(['BON', 'BOF'])
    
    # Employee ID: 5-digit number (may have leading zeros)
    employee_id = f"{random.randint(1, 99999):05d}"
    
    # Payroll ID: Generate random number (to be ignored)
    payroll_id = random.randint(10000, 99999)
    
    # Use execution time for clocking date and base time
    clocking_date = execution_time.strftime('%Y%m%d')
    
    # Clocking time: Use current hour and minute, but vary seconds
    base_hour = execution_time.hour
    base_minute = execution_time.minute
    random_second = random.randint(0, 59)  # Only seconds vary
    clocking_time = f"{base_hour:02d}{base_minute:02d}{random_second:02d}"
    
    # DateTime created: combination of date and time
    datetime_created = f"{clocking_date}{clocking_time}"
    
    # GeoStatus: random integer (to be ignored)
    geo_status = random.randint(0, 5)
    
    # GeoLatitude: random latitude (to be ignored)
    geo_latitude = round(random.uniform(-90.0, 90.0), 6)
    
    # GeoLongitude: random longitude (to be ignored)
    geo_longitude = round(random.uniform(-180.0, 180.0), 6)
    
    # GeoAccuracy: random accuracy in meters (to be ignored)
    geo_accuracy = round(random.uniform(1.0, 100.0), 2)
    
    return [
        transaction_type,
        employee_id,
        payroll_id,
        clocking_date,
        clocking_time,
        datetime_created,
        geo_status,
        geo_latitude,
        geo_longitude,
        geo_accuracy
    ]

def create_bobo_csv(config, run_counter):
    """Create a CSV file with random BOBO data."""
    
    # Get current execution time
    execution_time = datetime.now()
    
    # Create timestamp for filename
    timestamp = execution_time.strftime('%Y%m%d_%H%M%S')
    filename = f"BOBO_{timestamp}_output.csv"
    
    # Use configured output directory
    output_path = Path(config['OUTPUT_DIR']) / filename
    
    # Generate random number of entries within configured range
    num_entries = random.randint(config['MIN_ENTRIES'], config['MAX_ENTRIES'])
    
    try:
        # Create CSV file
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Generate and write random entries
            for _ in range(num_entries):
                entry = generate_random_entry(execution_time)
                writer.writerow(entry)
        
        print(f"[{execution_time.strftime('%Y-%m-%d %H:%M:%S')}] Generated {filename} with {num_entries} entries (File #{run_counter}/{config['MAX_FILE_COUNT']})")
        print(f"  All entries use date: {execution_time.strftime('%Y%m%d')} and base time: {execution_time.strftime('%H%M')}XX")
        return str(output_path)
    
    except Exception as e:
        print(f"[{execution_time.strftime('%Y-%m-%d %H:%M:%S')}] Error creating CSV file: {e}")
        return None

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Received termination signal. Shutting down gracefully...")
    sys.exit(0)

def main():
    """Main function to run the simulator continuously."""
    print("BOBO CSV Data Simulator - Continuous Mode")
    print("=" * 50)
    
    # Load configuration
    config = load_env_config()
    
    # Display configuration
    print("Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()
    
    # Ensure output directory exists
    if not ensure_output_directory(config['OUTPUT_DIR']):
        print("Failed to create output directory. Exiting.")
        sys.exit(1)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    print(f"Starting continuous simulation (every {config['SIMULATION_INTERVAL']} seconds)")
    print(f"Will create maximum of {config['MAX_FILE_COUNT']} files before stopping")
    print("Each execution will use current date/time with varying seconds only")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    # Initialize run counter
    run_counter = 0
    
    try:
        while run_counter < config['MAX_FILE_COUNT']:
            # Increment counter
            run_counter += 1
            
            # Create CSV file
            csv_file = create_bobo_csv(config, run_counter)
            
            if csv_file:
                print(f"  Output: {csv_file}")
            
            # Check if we've reached the maximum
            if run_counter >= config['MAX_FILE_COUNT']:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Maximum file count ({config['MAX_FILE_COUNT']}) reached. Stopping simulation.")
                break
            
            # Wait for next iteration
            print(f"  Next generation in {config['SIMULATION_INTERVAL']} seconds...")
            time.sleep(config['SIMULATION_INTERVAL'])
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Simulation stopped by user after {run_counter} files.")
    except Exception as e:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unexpected error: {e}")
    
    print(f"BOBO Simulator shutdown complete. Total files created: {run_counter}")

if __name__ == "__main__":
    main() 