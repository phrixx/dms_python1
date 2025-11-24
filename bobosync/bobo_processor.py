#!/usr/bin/env python3
"""
BOBO Processor
Processes BOBO CSV files and updates duty status in AtHoc via API calls.
Handles worker ID to email mapping via local database.
All configuration is loaded from .env file in the same directory.
"""

import csv
import sqlite3
import os
import logging
import shutil
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from logging.handlers import TimedRotatingFileHandler
from dataclasses import dataclass
from typing_extensions import Self

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from the same directory as this script
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    print("WARNING: python-dotenv not installed. Environment variables must be set manually.")
except Exception as e:
    print(f"WARNING: Could not load .env file: {e}")

# Import AtHoc client from same directory
from athoc_client import AtHocClient

@dataclass
class BOBOEntry:
    """Represents a single BOBO CSV entry"""
    transaction_type: str  # BON or BOF
    employee_id: str       # Worker ID (5-digit)
    payroll_id: str       # Payroll ID (ignored)
    clocking_date: str    # YYYYMMDD
    clocking_time: str    # HHMMSS
    datetime_created: str # Combined datetime
    geo_status: int       # Geographic status (ignored)
    geo_latitude: float   # Latitude (ignored)
    geo_longitude: float  # Longitude (ignored)
    geo_accuracy: float   # GPS accuracy (ignored)
    
    @classmethod
    def from_csv_row(cls, row: List[str]) -> 'BOBOEntry':
        """Create BOBOEntry from CSV row"""
        return cls(
            transaction_type=row[0],
            employee_id=row[1],
            payroll_id=row[2],
            clocking_date=row[3],
            clocking_time=row[4],
            datetime_created=row[5],
            geo_status=int(row[6]) if row[6] else 0,
            geo_latitude=float(row[7]) if row[7] else 0.0,
            geo_longitude=float(row[8]) if row[8] else 0.0,
            geo_accuracy=float(row[9]) if row[9] else 0.0
        )
    
    def get_event_datetime(self) -> datetime:
        """Parse the datetime from the entry"""
        return datetime.strptime(self.datetime_created, '%Y%m%d%H%M%S')

class BOBODatabase:
    """Handles local SQLite database for worker ID to username mapping"""
    
    def __init__(self, db_path: str = "bobo_mapping.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create mapping table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS worker_mapping (
                    employee_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    collar_id TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create processing log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    entries_processed INTEGER,
                    success_count INTEGER,
                    error_count INTEGER,
                    errors TEXT
                )
            ''')
            
            # Create sync tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_tracking (
                    sync_type TEXT PRIMARY KEY,
                    last_sync_date DATE,
                    last_sync_time TIMESTAMP,
                    status TEXT
                )
            ''')
            
            # Create file retry tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_retry_tracking (
                    filename TEXT PRIMARY KEY,
                    retry_count INTEGER DEFAULT 0,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_retry TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def get_last_sync_date(self, sync_type: str = "user_mapping") -> Optional[str]:
        """Get the last sync date for a specific sync type
        
        Args:
            sync_type: Type of sync to check (e.g., 'user_mapping')
            
        Returns:
            Last sync date as string (YYYY-MM-DD) or None if never synced
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_sync_date FROM sync_tracking WHERE sync_type = ?",
                (sync_type,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_last_sync_status(self, sync_type: str = "user_mapping") -> Optional[str]:
        """Get the status of the last sync operation
        
        Args:
            sync_type: Type of sync to check (e.g., 'user_mapping')
            
        Returns:
            Last sync status ('completed', 'error', 'no_data') or None if never synced
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM sync_tracking WHERE sync_type = ?",
                (sync_type,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def update_sync_tracking(self, sync_type: str = "user_mapping", status: str = "completed"):
        """Update sync tracking with current date and time
        
        Args:
            sync_type: Type of sync performed
            status: Status of the sync operation
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_time = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT OR REPLACE INTO sync_tracking 
                (sync_type, last_sync_date, last_sync_time, status)
                VALUES (?, ?, ?, ?)
            ''', (sync_type, current_date, current_time, status))
            conn.commit()
    
    def get_username_by_employee_id(self, employee_id: str) -> Optional[str]:
        """Get username for a given employee ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username FROM worker_mapping WHERE employee_id = ?",
                (employee_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def update_mapping(self, employee_id: str, username: str, collar_id: str = None):
        """Update or insert worker mapping"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO worker_mapping 
                (employee_id, username, collar_id, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (employee_id, username, collar_id))
            conn.commit()
    
    def log_processing(self, filename: str, entries_processed: int, 
                      success_count: int, error_count: int, errors: str = ""):
        """Log file processing results"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO processing_log 
                (filename, entries_processed, success_count, error_count, errors)
                VALUES (?, ?, ?, ?, ?)
            ''', (filename, entries_processed, success_count, error_count, errors))
            conn.commit()
    
    def get_all_mappings(self) -> List[Tuple[str, str, str]]:
        """Get all worker mappings"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT employee_id, username, collar_id FROM worker_mapping")
            return cursor.fetchall()
    
    def track_file_retry(self, filename: str) -> int:
        """Track retry attempts for a file and return current count
        
        Args:
            filename: Name of the file being retried
            
        Returns:
            Current retry count for this file
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get current retry count
            cursor.execute(
                "SELECT retry_count FROM file_retry_tracking WHERE filename = ?",
                (filename,)
            )
            result = cursor.fetchone()
            
            if result:
                retry_count = result[0] + 1
                cursor.execute(
                    "UPDATE file_retry_tracking SET retry_count = ?, last_retry = CURRENT_TIMESTAMP WHERE filename = ?",
                    (retry_count, filename)
                )
            else:
                retry_count = 1
                cursor.execute(
                    "INSERT INTO file_retry_tracking (filename, retry_count) VALUES (?, ?)",
                    (filename, retry_count)
                )
            
            conn.commit()
            return retry_count
    
    def clear_file_retry_tracking(self, filename: str):
        """Clear retry tracking for a successfully processed file
        
        Args:
            filename: Name of the file that was successfully processed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM file_retry_tracking WHERE filename = ?",
                (filename,)
            )
            conn.commit()

class BOBOProcessor:
    """Main processor for BOBO CSV files"""
    
    def __init__(self):
        # Load configuration from environment variables
        self.config = self._load_config()
        
        # Initialize database with configured path
        self.database = BOBODatabase(self.config['db_path'])
        self.athoc_client = None
        self.logger = self._setup_logging()
        
        # Configuration from environment
        self.batch_size = self.config['batch_size']
        self.auto_cleanup_hours = self.config['auto_cleanup_hours']
        
        # Processing settings
        self.csv_directory = self.config['csv_directory']
        self.processed_directory = self.config['processed_directory']
        self.move_processed_files = self.config['move_processed_files']
        self.duty_status_field = self.config['duty_status_field']
        
        # User mapping sync settings
        self.sync_mappings = self.config['sync_mappings']
        self.sync_hour = self.config['sync_hour']
        self.sync_retry_days = self.config['sync_retry_days']
        
        # Logging settings
        self.log_directory = self.config['log_directory']
        self.log_purge_days = self.config['log_purge_days']
        
        # File retry and failure handling
        self.max_retry_attempts = self.config['max_retry_attempts']
        self.failed_files_directory = self.config['failed_files_directory']
    
    def _normalize_path(self, path: str) -> str:
        """Normalize UNC and mixed-separator paths (Windows-safe).
        Accepts both //server/share and \\\\server\\share inputs and normalizes separators.
        """
        try:
            if isinstance(path, str):
                # Convert //server/share to \\server\share on Windows
                if os.name == 'nt' and path.startswith('//'):
                    path = '\\\\' + path.lstrip('/').replace('/', '\\')
                return os.path.normpath(path)
            return path
        except Exception:
            return path

    @staticmethod
    def format_datetime_for_athoc(dt: datetime) -> str:
        """Format datetime in the format required by AtHoc: dd/MM/yyyy HH:mm:ss"""
        return dt.strftime("%d/%m/%Y %H:%M:%S")

    def _load_config(self) -> Dict:
        """Load configuration from environment variables (loaded from .env file)"""
        config = {}
        
        # Load configuration from environment variables with defaults
        config['csv_directory'] = os.getenv('CSV_DIRECTORY', '../simulator/output')
        config['db_path'] = os.getenv('DB_PATH', 'bobo_mapping.db')
        config['sync_mappings'] = os.getenv('SYNC_MAPPINGS', 'true').lower() == 'true'
        config['duty_status_field'] = os.getenv('DUTY_STATUS_FIELD', 'On-Duty-DTG')
        config['batch_size'] = int(os.getenv('BATCH_SIZE', '10'))
        config['auto_cleanup_hours'] = int(os.getenv('AUTO_CLEANUP_HOURS', '24'))
        config['collar_id_field'] = os.getenv('COLLAR_ID_FIELD', 'COLLAR_ID')
        config['user_attributes'] = [attr.strip() for attr in os.getenv('USER_ATTRIBUTES', 'COLLAR_ID,FIRSTNAME,LASTNAME').split(',')]
        config['log_level'] = os.getenv('LOG_LEVEL', 'INFO')
        
        # File processing configuration
        config['processed_directory'] = os.getenv('PROCESSED_DIRECTORY', '../processed_files')
        config['move_processed_files'] = os.getenv('MOVE_PROCESSED_FILES', 'false').lower() == 'true'
        
        # Logging configuration
        config['log_directory'] = os.getenv('LOG_DIRECTORY', '../logs')
        config['log_purge_days'] = int(os.getenv('LOG_PURGE_DAYS', '10'))
        
        # User mapping sync settings
        config['sync_hour'] = int(os.getenv('SYNC_HOUR', '20'))  # 8pm default
        config['sync_retry_days'] = int(os.getenv('SYNC_RETRY_DAYS', '2'))  # Retry after 2 days
        
        # File retry and failure handling
        config['max_retry_attempts'] = int(os.getenv('MAX_RETRY_ATTEMPTS', '5'))
        config['failed_files_directory'] = os.getenv('FAILED_FILES_DIRECTORY', '../failed_files')
        
        return config

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration with daily rotation and purging"""
        # Get log directory path (convert relative to absolute if needed)
        log_dir = self.config['log_directory']
        if not os.path.isabs(log_dir):
            log_dir = os.path.join(os.path.dirname(__file__), log_dir)
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup log file path
        log_file = os.path.join(log_dir, 'bobo_processor.log')
        
        # Get log level from config
        log_level = getattr(logging, self.config['log_level'].upper(), logging.INFO)
        
        # Create logger
        logger = logging.getLogger('BOBOProcessor')
        logger.setLevel(log_level)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create and configure file handler with daily rotation
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=self.config['log_purge_days'],
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        # Create and configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Purge old log files on startup
        self._purge_old_logs(log_dir)
        
        logger.info(f"Logging initialized - Directory: {log_dir}, Purge after: {self.config['log_purge_days']} days")
        
        return logger

    def _purge_old_logs(self, log_dir: str):
        """Remove *all* log files in the log directory older than the purge window."""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.config['log_purge_days'])
            purged_count = 0
            log_path = Path(log_dir)
            if not log_path.exists():
                return

            for entry in log_path.iterdir():
                if not entry.is_file():
                    continue

                name_lower = entry.name.lower()
                if not (name_lower.endswith(".log") or ".log." in name_lower):
                    continue

                try:
                    file_mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        entry.unlink()
                        purged_count += 1
                        print(f"Purged old log file: {entry.name}")
                except OSError as e:
                    print(f"Warning: Could not purge log file {entry}: {e}")

            if purged_count > 0:
                print(f"Purged {purged_count} log file(s) older than {self.config['log_purge_days']} days")

        except Exception as e:
            print(f"Warning: Error during log purging: {e}")
    
    def connect_athoc(self):
        """Connect to AtHoc and create client"""
        try:
            self.athoc_client = AtHocClient()
            self.logger.info("Successfully connected to AtHoc")
        except Exception as e:
            self.logger.error(f"Failed to connect to AtHoc: {e}")
            raise

    def should_run_user_mapping_sync(self) -> bool:
        """Check if user mapping sync should run based on schedule
        
        Returns:
            True if sync should run, False otherwise
            
        Sync runs if:
        - After configured sync hour and not done today, OR
        - More than configured retry days since last successful sync, OR  
        - Last sync had no data or errors (allow retry)
        """
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_hour = now.hour
        
        # Get last sync info
        last_sync_date = self.database.get_last_sync_date("user_mapping")
        last_sync_status = self.database.get_last_sync_status("user_mapping")
        
        # Calculate days since last sync
        days_since_sync = 0
        if last_sync_date:
            try:
                last_date = datetime.strptime(last_sync_date, "%Y-%m-%d")
                days_since_sync = (now - last_date).days
            except ValueError:
                # If date parsing fails, treat as if never synced
                days_since_sync = 999
        else:
            # Never synced
            days_since_sync = 999
        
        # Reason 1: More than configured retry days since last sync - run immediately
        if days_since_sync > self.sync_retry_days:
            self.logger.info(f"User mapping sync overdue - {days_since_sync} days since last sync (max: {self.sync_retry_days})")
            return True
        
        # Reason 2: Last sync had issues - allow retry regardless of time
        if last_sync_status in ["no_data", "error"]:
            self.logger.info(f"User mapping sync retry - last status: {last_sync_status}")
            return True
        
        # Reason 3: Normal schedule - after configured hour and not done today
        if current_hour < self.sync_hour:
            self.logger.debug(f"User mapping sync scheduled for {self.sync_hour}:00 - current time: {now.strftime('%H:%M')}")
            return False
        
        if last_sync_date == current_date:
            self.logger.debug(f"User mapping sync already completed today: {last_sync_date}")
            return False
        
        self.logger.info(f"User mapping sync due - scheduled run after {self.sync_hour}:00")
        return True

    def sync_worker_mappings(self):
        """Sync worker mappings from AtHoc using configured field names"""
        # Check if sync should run based on schedule
        if not self.should_run_user_mapping_sync():
            return
            
        self.logger.info("Starting scheduled user mapping sync...")
        
        try:
            # Query AtHoc for all users with collar_id field from config
            users_data = self.athoc_client.get_all_users_with_attributes(self.config['user_attributes'])
            
            if not users_data:
                self.logger.warning("No users returned from AtHoc user attributes query")
                # Still update tracking to avoid retrying constantly
                self.database.update_sync_tracking("user_mapping", "no_data")
                return
            
            synced_count = 0
            for username, user_data in users_data.items():
                # Get collar_id from the configured field
                collar_id = user_data.get(self.config['collar_id_field'], '')
                
                if collar_id and collar_id.strip():
                    # Map collar_id to employee_id (assuming they're the same)
                    employee_id = collar_id.strip()
                    self.database.update_mapping(employee_id, username, collar_id)
                    synced_count += 1
                    self.logger.debug(f"Mapped employee {employee_id} to username {username}")
            
            # Update sync tracking
            self.database.update_sync_tracking("user_mapping", "completed")
            self.logger.info(f"User mapping sync completed - {synced_count} mappings updated")
            
        except Exception as e:
            self.logger.error(f"Failed to sync worker mappings: {e}")
            # Update tracking with error status
            self.database.update_sync_tracking("user_mapping", "error")
            raise
    
    def get_csv_files(self, directory: str) -> List[str]:
        """Get all CSV files in directory, sorted by modification time (oldest first)"""
        # Normalize directory (handles //UNC and mixed separators on Windows)
        directory = self._normalize_path(directory)
        csv_pattern = os.path.join(directory, "*.csv")
        csv_pattern = self._normalize_path(csv_pattern)
        self.logger.info(f"Searching for CSV files in {directory}")
        csv_files = [self._normalize_path(p) for p in glob.glob(csv_pattern)]
        
        # Sort by modification time (oldest first)
        def _safe_mtime(p: str) -> float:
            try:
                return os.path.getmtime(p)
            except Exception as e:
                self.logger.warning(f"Skipping file due to mtime error: {p} -> {e}")
                return float('inf')
        csv_files.sort(key=_safe_mtime)
        
        self.logger.info(f"Found {len(csv_files)} CSV files in {directory}")
        return csv_files
    
    def move_processed_file(self, filepath: str) -> bool:
        """Move a processed CSV file to the processed directory if configured
        
        Args:
            filepath: Path to the CSV file that was processed
            
        Returns:
            True if file was moved successfully or moving is disabled, False if error occurred
        """
        if not self.config['move_processed_files']:
            self.logger.debug(f"File moving disabled, leaving {filepath} in place")
            return True
            
        try:
            # Normalize source path
            filepath = self._normalize_path(filepath)
            # Get processed directory path (convert relative to absolute if needed)
            processed_dir = self.config['processed_directory']
            if not os.path.isabs(processed_dir):
                processed_dir = os.path.join(os.path.dirname(__file__), processed_dir)
            processed_dir = self._normalize_path(processed_dir)
            
            # Create processed directory if it doesn't exist
            os.makedirs(processed_dir, exist_ok=True)
            
            # Get filename and construct destination path
            filename = os.path.basename(filepath)
            destination = os.path.join(processed_dir, filename)
            destination = self._normalize_path(destination)
            
            # Handle filename conflicts by adding timestamp suffix
            if os.path.exists(destination):
                name, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{name}_{timestamp}{ext}"
                destination = os.path.join(processed_dir, filename)
                destination = self._normalize_path(destination)
            
            # Move the file
            shutil.move(filepath, destination)
            self.logger.info(f"Moved processed file: {filepath} -> {destination}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to move processed file {filepath}: {e}")
            return False
    
    def move_to_failed_directory(self, filepath: str) -> bool:
        """Move persistently failing file to failed directory
        
        Args:
            filepath: Path to the CSV file that failed repeatedly
            
        Returns:
            True if file was moved successfully, False if error occurred
        """
        try:
            # Create failed directory if it doesn't exist
            failed_dir = self.config['failed_files_directory']
            if not os.path.isabs(failed_dir):
                failed_dir = os.path.join(os.path.dirname(__file__), failed_dir)
            failed_dir = self._normalize_path(failed_dir)
            os.makedirs(failed_dir, exist_ok=True)
            
            # Normalize source path
            filepath = self._normalize_path(filepath)
            
            # Get filename and construct destination path
            filename = os.path.basename(filepath)
            destination = os.path.join(failed_dir, filename)
            destination = self._normalize_path(destination)
            
            # Handle filename conflicts by adding timestamp suffix
            if os.path.exists(destination):
                name, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{name}_{timestamp}{ext}"
                destination = os.path.join(failed_dir, filename)
                destination = self._normalize_path(destination)
            
            # Move the file
            shutil.move(filepath, destination)
            self.logger.warning(f"Moved persistently failing file to failed directory: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to move file to failed directory {filepath}: {e}")
            return False
    
    def parse_csv_file(self, filepath: str) -> List[BOBOEntry]:
        """Parse a single CSV file and return BOBO entries"""
        entries = []
        
        try:
            filepath = self._normalize_path(filepath)
            with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                
                for row_num, row in enumerate(reader, 1):
                    if len(row) < 10:
                        self.logger.warning(f"Skipping row {row_num} in {filepath}: insufficient columns")
                        continue
                    
                    try:
                        entry = BOBOEntry.from_csv_row(row)
                        entries.append(entry)
                    except Exception as e:
                        self.logger.error(f"Error parsing row {row_num} in {filepath}: {e}")
                        continue
                        
        except Exception as e:
            self.logger.error(f"Error reading CSV file {filepath}: {e}")
            raise
        
        self.logger.info(f"Parsed {len(entries)} entries from {filepath}")
        return entries
    
    def update_user_duty_status(self, username: str, is_on_duty: bool, 
                              duty_status_field: str = "DUTY_STATUS") -> bool:
        """Update user duty status in AtHoc"""
        try:
            if is_on_duty:
                # Set duty status to current datetime
                duty_datetime = self.format_datetime_for_athoc(datetime.now())
                self.logger.info(f"Setting {username} ON duty at {duty_datetime}")
                result = self.athoc_client.update_user_duty_status(
                    username, duty_datetime, duty_status_field
                )
            else:
                # Clear duty status
                self.logger.info(f"Setting {username} OFF duty")
                result = self.athoc_client.update_user_duty_status(
                    username, None, duty_status_field
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to update duty status for {username}: {e}")
            return False
    
    def batch_update_duty_status(self, duty_updates: List[Dict], 
                               duty_status_field: str = "DUTY_STATUS") -> Tuple[int, int]:
        """Batch update multiple users' duty status for better performance
        
        Args:
            duty_updates: List of dicts with 'username', 'is_on_duty', and 'datetime' keys
            duty_status_field: Common name of the duty status field in AtHoc
            
        Returns:
            Tuple of (success_count, error_count)
        """
        if not duty_updates:
            return 0, 0
        
        # Prepare batch data
        batch_data = []
        for update in duty_updates:
            username = update.get("username")
            is_on_duty = update.get("is_on_duty")
            event_datetime = update.get("datetime")
            
            if not username:
                continue
            
            duty_datetime = self.format_datetime_for_athoc(event_datetime) if is_on_duty and event_datetime else None
            batch_data.append({
                "username": username,
                "duty_datetime": duty_datetime
            })
        
        try:
            # Use the batch update method from AtHoc client
            results = self.athoc_client.batch_update_duty_status(batch_data, duty_status_field)
            
            success_count = sum(1 for success in results.values() if success)
            error_count = len(results) - success_count
            
            return success_count, error_count
            
        except Exception as e:
            self.logger.error(f"Batch duty status update failed: {e}")
            return 0, len(duty_updates)

    def process_file_batch(self, batch_files: List[str], duty_status_field: str) -> Dict:
        """Process a batch of CSV files together with individual file success tracking
        
        Args:
            batch_files: List of CSV file paths to process together
            duty_status_field: Common name of the duty status field in AtHoc
            
        Returns:
            Dictionary with batch processing results
        """
        # Store file data with user tracking
        file_data = {}
        all_entries = []
        all_duty_updates = []
        
        # Phase 1: Parse all files and track which users belong to which files
        for filepath in batch_files:
            filename = os.path.basename(filepath)
            self.logger.info(f"Parsing: {filename}")
            
            try:
                # Parse CSV file
                entries = self.parse_csv_file(filepath)
                
                if not entries:
                    self.logger.warning(f"No valid entries found in {filename}")
                    file_data[filepath] = {
                        'filename': filename,
                        'entries': [],
                        'file_users': set(),
                        'has_valid_users': False,
                        'status': 'empty'
                    }
                    continue
                
                # Track users for this specific file
                file_users = set()
                for entry in entries:
                    username = self.database.get_username_by_employee_id(entry.employee_id)
                    if username:
                        file_users.add(username)
                
                file_data[filepath] = {
                    'filename': filename,
                    'entries': entries,
                    'file_users': file_users,
                    'has_valid_users': len(file_users) > 0,
                    'status': 'parsed'
                }
                all_entries.extend(entries)
                
            except Exception as e:
                self.logger.error(f"Failed to parse {filename}: {e}")
                file_data[filepath] = {
                    'filename': filename,
                    'entries': [],
                    'file_users': set(),
                    'has_valid_users': False,
                    'status': 'parse_error',
                    'error': str(e)
                }
        
        # Phase 2: Process all entries together if we have any
        batch_success_count = 0
        batch_error_count = 0
        user_results = {}  # Track individual user results
        
        if all_entries:
            self.logger.info(f"Processing {len(all_entries)} entries from {len(file_data)} files as a batch")
            
            # Group all entries by employee ID and get latest status
            employee_entries = {}
            for entry in all_entries:
                if entry.employee_id not in employee_entries:
                    employee_entries[entry.employee_id] = []
                employee_entries[entry.employee_id].append(entry)
            
            # Sort each employee's entries by datetime (oldest first)
            for employee_id in employee_entries:
                employee_entries[employee_id].sort(key=lambda x: x.get_event_datetime())
            
            # Prepare batch updates for ALL files combined
            for employee_id, emp_entries in employee_entries.items():
                try:
                    # Get username from mapping
                    username = self.database.get_username_by_employee_id(employee_id)
                    if not username:
                        self.logger.warning(f"No username mapping found for employee ID: {employee_id}")
                        continue
                    
                    # Get the latest entry for this employee across all files
                    latest_entry = emp_entries[-1]  # Last entry (newest)
                    is_on_duty = latest_entry.transaction_type == "BON"
                    event_datetime = latest_entry.get_event_datetime()
                    
                    # Add to batch update
                    all_duty_updates.append({
                        "username": username,
                        "is_on_duty": is_on_duty,
                        "datetime": event_datetime,
                        "employee_id": employee_id,
                        "transaction_type": latest_entry.transaction_type
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error processing employee {employee_id}: {e}")
            
            # Phase 3: Single batch sync to AtHoc for all files
            if all_duty_updates:
                try:
                    # Make single API call
                    results = self.athoc_client.batch_update_duty_status(all_duty_updates, duty_status_field)
                    
                    # Track individual user results
                    for update in all_duty_updates:
                        username = update["username"]
                        success = results.get(username, False)
                        user_results[username] = success
                        
                        if success:
                            batch_success_count += 1
                            self.logger.info(f"Synced {username} ({update['employee_id']}) - {update['transaction_type']}")
                        else:
                            batch_error_count += 1
                            self.logger.warning(f"Failed to sync {username} ({update['employee_id']}) - {update['transaction_type']}")
                    
                except Exception as e:
                    self.logger.error(f"Batch sync to AtHoc failed: {e}")
                    # API call failed - all users failed
                    for update in all_duty_updates:
                        user_results[update["username"]] = False
                    batch_error_count = len(all_duty_updates)
        
        # Phase 4: Determine individual file success based on user results
        for filepath, data in file_data.items():
            filename = data['filename']
            file_users = data['file_users']
            
            if not data['has_valid_users']:
                # No valid users - consider file successful (nothing to update)
                data['file_success'] = True
                data['file_error_reason'] = "No valid users found"
                self.logger.info(f"File {filename} has no valid users - marking as successful")
            else:
                # Check if all users for this file succeeded
                file_user_results = [user_results.get(user, False) for user in file_users]
                data['file_success'] = all(file_user_results)
                data['file_error_reason'] = "Some users failed to update" if not data['file_success'] else None
                
                if data['file_success']:
                    self.logger.info(f"File {filename} processed successfully - all {len(file_users)} users updated")
                else:
                    failed_users = [user for user in file_users if not user_results.get(user, False)]
                    self.logger.warning(f"File {filename} partially failed - {len(failed_users)}/{len(file_users)} users failed: {failed_users}")
        
        # Phase 5: Handle files based on individual success AND retry count
        files_moved = 0
        files_failed = 0
        total_entries_processed = 0
        
        for filepath, data in file_data.items():
            filename = data['filename']
            entries = data['entries']
            status = data['status']
            
            if status == 'parse_error':
                # Log parse errors
                self.database.log_processing(filename, 0, 0, 1, data.get('error', ''))
                continue
            
            # Calculate this file's contribution to the batch
            file_entries_count = len(entries)
            total_entries_processed += file_entries_count
            
            if data['file_success']:
                # File processed successfully - move to processed directory
                self.database.log_processing(filename, file_entries_count, 
                                           len(data['file_users']) if data['has_valid_users'] else 0, 
                                           0)
                
                # Clear retry tracking for successful file
                self.database.clear_file_retry_tracking(filename)
                
                # Move file to processed directory
                if self.move_processed_file(filepath):
                    files_moved += 1
                    self.logger.info(f"Successfully processed and moved: {filename}")
                else:
                    self.logger.warning(f"Processed {filename} but failed to move to processed directory")
            else:
                # File failed - check retry count
                retry_count = self.database.track_file_retry(filename)
                
                if retry_count >= self.max_retry_attempts:
                    # Move to failed directory
                    self.database.log_processing(filename, file_entries_count, 0, 
                                               len(data['file_users']) if data['has_valid_users'] else 0,
                                               f"Exceeded max retry attempts ({self.max_retry_attempts})")
                    
                    if self.move_to_failed_directory(filepath):
                        files_failed += 1
                        self.logger.warning(f"File exceeded max retries ({self.max_retry_attempts}) - moved to failed directory: {filename}")
                    else:
                        self.logger.error(f"Failed to move file to failed directory: {filename}")
                else:
                    # Keep for retry
                    self.database.log_processing(filename, file_entries_count, 0, 
                                               len(data['file_users']) if data['has_valid_users'] else 0,
                                               f"Retry attempt {retry_count}/{self.max_retry_attempts}: {data.get('file_error_reason', 'Unknown error')}")
                    self.logger.warning(f"File failed (attempt {retry_count}/{self.max_retry_attempts}) - keeping for retry: {filename}")
        
        return {
            'entries_processed': total_entries_processed,
            'success_count': batch_success_count,
            'error_count': batch_error_count,
            'files_moved': files_moved,
            'files_failed': files_failed,
            'file_results': {path: data['file_success'] for path, data in file_data.items()}
        }

    def process_directory(self):
        """Process all CSV files in configured directory with proper batching"""
        directory = self.config['csv_directory']
        duty_status_field = self.config['duty_status_field']
        
        # Convert relative path to absolute if needed
        if not os.path.isabs(directory):
            directory = os.path.join(os.path.dirname(__file__), directory)
        
        if not os.path.exists(directory):
            raise ValueError(f"Directory does not exist: {directory}")
        
        # Connect to AtHoc
        self.connect_athoc()
        
        # Sync mappings if configured
        if self.config['sync_mappings']:
            self.sync_worker_mappings()
        
        # Get all CSV files
        csv_files = self.get_csv_files(directory)
        if not csv_files:
            self.logger.info("No CSV files found to process")
            # Still run auto-cleanup even if no CSV files
            self.auto_cleanup_old_duty_status(duty_status_field)
            return
        
        # Process files in batches
        total_processed = 0
        total_success = 0
        total_errors = 0
        total_files_moved = 0
        total_files_failed = 0
        
        for i in range(0, len(csv_files), self.batch_size):
            batch_files = csv_files[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            
            self.logger.info(f"Processing batch {batch_num}: {len(batch_files)} files")
            
            # Process this batch of files together
            batch_result = self.process_file_batch(batch_files, duty_status_field)
            
            total_processed += batch_result['entries_processed']
            total_success += batch_result['success_count']
            total_errors += batch_result['error_count']
            total_files_moved += batch_result['files_moved']
            total_files_failed += batch_result['files_failed']
            
            # Log batch results
            self.logger.info(f"Batch {batch_num} completed: "
                           f"{batch_result['entries_processed']} entries processed, "
                           f"{batch_result['files_moved']} files moved, "
                           f"{batch_result['files_failed']} files moved to failed directory")
        
        # Auto-cleanup old duty status (when CSV files were processed)
        self.auto_cleanup_old_duty_status(duty_status_field)
        
        # Final summary
        self.logger.info(f"Processing complete: {total_processed} entries processed, "
                        f"{total_success} successful updates, {total_errors} errors, "
                        f"{total_files_moved} files moved to processed directory, "
                        f"{total_files_failed} files moved to failed directory")

    def auto_cleanup_old_duty_status(self, duty_status_field: str = "DUTY_STATUS"):
        """Auto-cleanup users with old duty status timestamps"""
        try:
            # Ensure auto-cleanup runs even if no CSV files were processed
            cleared_count = self.athoc_client.clear_old_duty_status(
                duty_status_field, self.auto_cleanup_hours
            )
            
            if cleared_count > 0:
                self.logger.info(f"Auto-cleanup: Cleared duty status for {cleared_count} users")
            else:
                self.logger.info("Auto-cleanup: No users required duty status clearing")
                
        except Exception as e:
            self.logger.error(f"Auto-cleanup failed: {e}")
def main():
    """Main entry point - all configuration from .env file"""
    try:
        processor = BOBOProcessor()
        
        # Display configuration
        print("BOBO Processor - Configuration loaded from .env file")
        print("=" * 50)
        print(f"CSV Directory: {processor.config['csv_directory']}")
        print(f"Database Path: {processor.config['db_path']}")
        print(f"Sync Mappings: {processor.config['sync_mappings']}")
        print(f"Duty Status Field: {processor.config['duty_status_field']}")
        print(f"Batch Size: {processor.config['batch_size']}")
        print(f"Auto Cleanup Hours: {processor.config['auto_cleanup_hours']}")
        print(f"Collar ID Field: {processor.config['collar_id_field']}")
        print(f"User Attributes: {', '.join(processor.config['user_attributes'])}")
        print(f"Processed Directory: {processor.config['processed_directory']}")
        print(f"Move Processed Files: {processor.config['move_processed_files']}")
        print(f"Log Directory: {processor.config['log_directory']}")
        print(f"Log Purge Days: {processor.config['log_purge_days']}")
        print("-" * 50)
        
        processor.process_directory()
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 