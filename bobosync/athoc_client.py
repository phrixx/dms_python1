import os
import requests
import ssl
from typing import Dict, List
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime, timedelta
from pathlib import Path

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

# Role mapping from CommonName to full Name
ROLE_MAP = {
    "RORGADM": "Organization Admin",
    "RSDK": "SDK User",
    "RAAPUB": "Advanced Alert Publisher",
    "RSAC": "Draft Alert Creator",
    "RDLM": "Dist. Lists Manager",
    "REUM": "End Users Manager",
    "RENTADM": "Enterprise Admin",
    "RRM": "Report Manager",
    "RAM": "Alert Manager",
    "RCAM": "Connect Agreement Manager",
    "RALM": "Activity Log Manager",
    "RALV": "Activity Log Viewer",
    "RCOLLAB": "Collaboration Manager",
    "RAPUB": "Alert Publisher",
    "RAAM": "Advanced Alert Manager",
    "RGEOM": "Geofence Manager"
}

class TLS12HttpAdapter(HTTPAdapter):
    """Transport adapter that enforces TLS 1.2"""
    def __init__(self, *args, **kwargs):
        self.ssl_context = create_urllib3_context(
            ssl_minimum_version=ssl.TLSVersion.TLSv1_2
        )
        if os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true":
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)

class AtHocClient:
    """Generic AtHoc API client for common operations"""
    
    def __init__(self):
        # Remove role loading attempt - not needed for core functionality
        self.session = self._create_session()
        self.token = self._get_auth_token()
        if not self.token:
            raise Exception("Failed to get AtHoc authentication token")
            
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.base_url = os.getenv("ATHOC_SERVER_URL")
        self.org_code = os.getenv("ORG_CODE")

    @staticmethod
    def format_datetime_for_athoc(dt: datetime) -> str:
        """Format datetime in AtHoc format: dd/MM/yyyy HH:mm:ss"""
        return dt.strftime("%d/%m/%Y %H:%M:%S")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    def _create_session(self):
        """Create a requests session with TLS 1.2 support"""
        session = requests.Session()
        adapter = TLS12HttpAdapter()
        session.mount('https://', adapter)
        
        if os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true":
            session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        return session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _get_auth_token(self) -> str:
        """Get authentication token from AtHoc"""
        required_vars = {
            "ATHOC_SERVER_URL": os.getenv("ATHOC_SERVER_URL"),
            "CLIENT_ID": os.getenv("CLIENT_ID"),
            "CLIENT_SECRET": os.getenv("CLIENT_SECRET"),
            "USERNAME": os.getenv("USERNAME"),
            "PASSWORD": os.getenv("PASSWORD"),
            "ORG_CODE": os.getenv("ORG_CODE")
        }
        
        if missing_vars := [k for k, v in required_vars.items() if not v]:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        token_url = f"{required_vars['ATHOC_SERVER_URL']}/AuthServices/Auth/connect/token"
        
        data = {
            "grant_type": "password",
            "scope": os.getenv("SCOPE", ""),
            "client_id": required_vars["CLIENT_ID"],
            "client_secret": required_vars["CLIENT_SECRET"],
            "username": required_vars["USERNAME"],
            "password": required_vars["PASSWORD"],
            "acr_values": f"tenant:{required_vars['ORG_CODE']}"
        }

        response = self.session.post(token_url, data=data, timeout=30)
        response.raise_for_status()
        
        token_info = response.json()
        if access_token := token_info.get("access_token"):
            return access_token
        raise ValueError("Auth token not found in response")

    def get_alerts(self, start_date: str, end_date: str) -> List[Dict]:
        """Generic alert retrieval"""
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/alerts"
        
        params = {
            "StartDate": start_date,
            "EndDate": end_date,
            "AlertStatus": "live,ended",
            "Limit": 1000,
            "Offset": 0,
            "IncludeSubOrgs": True
        }
        
        response = self.session.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json().get("Data", [])

    def get_device_summary(self, alert_id: str) -> List[Dict]:
        """Generic device summary"""
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/alerts/{alert_id}/reports/devicesummary"
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_user_attributes(self, usernames: List[str]) -> Dict[str, Dict]:
        """Generic user attributes retrieval"""
        if not usernames:
            return {}
            
        # Debug information about USER_ATTRIBUTES
        attr_fields_raw = os.getenv("USER_ATTRIBUTES", "")
        print(f"DEBUG: USER_ATTRIBUTES env value: '{attr_fields_raw}'")
        
        attr_fields = attr_fields_raw.split(",")
        if not attr_fields or not attr_fields[0]:
            print("DEBUG: No valid user attributes found in environment variables")
            return {}
            
        print(f"DEBUG: Using user attributes: {attr_fields}")
            
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/users/search/basic"
        
        criteria = " or ".join([f"LOGIN_ID eq '{username}'" for username in usernames])
        fields = ["LOGIN_ID"] + attr_fields
        
        params = {
            "Criteria": f"({criteria})",
            "Fields": ",".join(fields),
            "limit": len(usernames)
        }
        
        try:
            response = self.session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            users = response.json().get("Users", [])
            result = {
                user["LOGIN_ID"]: {
                    f"attr{i+1}": user.get(field, "")
                    for i, field in enumerate(attr_fields)
                }
                for user in users
            }
            
            # Debug output of what we found
            if users:
                print(f"DEBUG: Found {len(users)} users with attributes")
                for user in users[:2]:  # Just show first 2 users to avoid too much output
                    print(f"DEBUG: User {user.get('LOGIN_ID')} attributes: {[user.get(field, '') for field in attr_fields]}")
            
            # Note any users not found
            found_users = {user["LOGIN_ID"] for user in users}
            missing_users = set(usernames) - found_users
            if missing_users:
                print(f"DEBUG: {len(missing_users)} users not found in user attributes query: {', '.join(sorted(missing_users))}")
                
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"WARNING: Error fetching user attributes: {str(e)}")
            return {}

    def get_all_users_with_attributes(self, fields: List[str] = None) -> Dict[str, Dict]:
        """Generic user retrieval with attributes"""
        # Use provided fields or fall back to environment configuration
        if fields is None:
            attr_fields_raw = os.getenv("USER_ATTRIBUTES", "")
            if not attr_fields_raw:
                print("WARNING: No USER_ATTRIBUTES configured and no fields provided")
                return {}
            fields = [field.strip() for field in attr_fields_raw.split(",") if field.strip()]
        
        print(f"DEBUG: Retrieving all users with fields: {fields}")
        
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/users/search/basic"
        
        # Include LOGIN_ID in fields if not already present
        all_fields = ["LOGIN_ID"] + [field for field in fields if field != "LOGIN_ID"]
        
        # Set limit to exactly 1000 and start with offset 0
        params = {
            "Fields": ",".join(all_fields),
            "Limit": 1000,  # Fixed limit of 1000
            "Offset": 0     # Start with page 0
        }
        
        all_users = {}
        page_number = 0
        
        try:
            while True:
                params["Offset"] = page_number
                response = self.session.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                users = data.get("Users", [])
                total_users = data.get("TotalUsers", 0)
                fetched_records = data.get("FetchedRecords", len(users))
                
                print(f"DEBUG: Fetched {fetched_records} users (page: {page_number}, offset: {page_number}, total: {total_users})")
                
                # Process users from this batch
                for user in users:
                    login_id = user.get("LOGIN_ID")
                    if login_id:
                        # Store all fields as-is (no attr1, attr2 mapping)
                        all_users[login_id] = user
                
                # Check if we have more users to fetch
                if len(users) == 0:
                    break
                
                # Calculate if we've reached the end
                users_retrieved_so_far = (page_number * 1000) + len(users)
                if users_retrieved_so_far >= total_users:
                    break
                
                # Move to next page
                page_number += 1
            
            print(f"DEBUG: Successfully retrieved {len(all_users)} users with attributes")
            
            # Show sample of retrieved data
            if all_users:
                sample_user = next(iter(all_users.values()))
                print(f"DEBUG: Sample user data: {sample_user}")
            
            return all_users
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Failed to retrieve users with attributes: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    print(f"ERROR details: {error_details}")
                except:
                    print(f"ERROR response text: {e.response.text}")
            return {}

    def get_operator_roles(self, login_id: str) -> Dict:
        """Get operator's role information and permissions
        
        Args:
            login_id: The login ID of the operator
            
        Returns:
            Dictionary containing operator's role information and permissions
        """
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/operators/{login_id}"
        
        try:
            response = self.session.get(url, headers=self.headers)
            # Some APIs return 404 if the user is not found in the organization
            if response.status_code == 404:
                print(f"DEBUG: Operator {login_id} not found in organization (404)")
                return {}
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                # This might be due to permissions or an external user
                print(f"DEBUG: Cannot access operator info for {login_id}: Permission denied (403)")
            else:
                print(f"WARNING: HTTP error fetching operator roles for {login_id}: {str(e)}")
            return {}
        except requests.exceptions.RequestException as e:
            print(f"WARNING: Error fetching operator roles for {login_id}: {str(e)}")
            return {}
            
    def get_roles(self) -> List[Dict]:
        """Get all roles from the API"""
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/roles"  # Fixed endpoint
        
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            roles = response.json()
            print(f"INFO: Successfully loaded {len(roles)} roles from API")
            return roles
        except Exception as e:
            print(f"WARNING: Error fetching roles: {str(e)}")
            return []
    
    def get_role_name(self, common_name: str) -> str:
        """Convert a role CommonName to its full Name"""
        if not common_name:
            return "Unknown Role"
            
        # First check our API-loaded mapping
        if common_name in self.roles_by_common_name:
            return self.roles_by_common_name[common_name]
            
        # Fall back to the static mapping
        return ROLE_MAP.get(common_name, common_name)

    def get_operator_roles_batch(self, login_ids: List[str]) -> Dict[str, Dict]:
        """Get operator roles for a list of users
        
        Args:
            login_ids: List of login IDs to fetch roles for
            
        Returns:
            Dictionary mapping login IDs to their operator role information
        """
        if not login_ids:
            return {}
            
        operator_roles = {}
        for login_id in login_ids:
            operator_data = self.get_operator_roles(login_id)
            if operator_data:
                # Extract roles from the first org (typically the home org)
                roles = []
                role_names = []
                
                if "Orgs" in operator_data and operator_data["Orgs"]:
                    for org in operator_data["Orgs"]:
                        if org.get("OrgCode") == self.org_code:
                            common_roles = org.get("Roles", [])
                            roles = common_roles
                            # Convert CommonNames to full role names
                            role_names = [self.get_role_name(role) for role in common_roles]
                            break
                        
                operator_roles[login_id] = {
                    "roles": roles,  # Original CommonName roles
                    "role_names": role_names,  # Full names of roles
                    "displayName": operator_data.get("DISPLAYNAME", ""),
                    "firstName": operator_data.get("FIRSTNAME", ""),
                    "lastName": operator_data.get("LASTNAME", ""),
                    "homeOrg": operator_data.get("HomeOrg", ""),
                    "homeOrgName": operator_data.get("HomeOrgName", "")
                }
                
        return operator_roles

    def sync_users_by_common_names(self, users_data: List[Dict], 
                                 sync_existing_only: bool = True,
                                 allow_partial_update: bool = False,
                                 source_identifier: str = None) -> List[Dict]:
        """Generic user sync - removed BOBO default"""
        if not users_data:
            return []
            
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/users/SyncByCommonNames"
        
        params = {
            "syncExistingUsersOnly": sync_existing_only,
            "AllowPartialUpdate": allow_partial_update,
            "sourceIdentifier": source_identifier
        }
        
        try:
            response = self.session.post(
                url, 
                headers=self.headers, 
                json=users_data,
                params=params,
                timeout=120  # Longer timeout for bulk operations
            )
            response.raise_for_status()
            
            results = response.json()
            
            # Log summary of results
            success_count = sum(1 for r in results if r.get(":SyncStatus") == "OK")
            error_count = sum(1 for r in results if r.get(":SyncStatus") == "Error")
            partial_count = sum(1 for r in results if r.get(":SyncStatus") == "Partial")
            
            print(f"User sync results: {success_count} success, {error_count} errors, {partial_count} partial")
            
            # Log any errors for debugging
            for result in results:
                if result.get(":SyncStatus") in ["Error", "Partial"]:
                    login_id = result.get("LOGIN_ID", "Unknown")
                    details = result.get(":SyncDetails", "No details")
                    print(f"Sync issue for {login_id}: {result.get(':SyncStatus')} - {details}")
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: User sync request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    print(f"ERROR details: {error_details}")
                except:
                    print(f"ERROR response text: {e.response.text}")
            raise
    
    def update_user_duty_status(self, username: str, duty_datetime: str = None, 
                              duty_status_field: str = "DUTY_STATUS") -> bool:
        """Update a single user's duty status using the sync API
        
        Args:
            username: User's LOGIN_ID (email/username)
            duty_datetime: ISO datetime string for on-duty, None/empty for off-duty
            duty_status_field: Common name of the duty status field in AtHoc
            
        Returns:
            True if successful, False otherwise
        """
        user_data = {
            "LOGIN_ID": username,
            duty_status_field: duty_datetime or ""  # Empty string for off-duty
        }
        
        try:
            results = self.sync_users_by_common_names([user_data])
            
            if results and len(results) > 0:
                result = results[0]
                sync_status = result.get(":SyncStatus")
                
                if sync_status == "OK":
                    return True
                else:
                    print(f"Duty status update failed for {username}: {result.get(':SyncDetails', 'Unknown error')}")
                    return False
            else:
                print(f"No results returned for duty status update: {username}")
                return False
                
        except Exception as e:
            print(f"Exception updating duty status for {username}: {str(e)}")
            return False
    
    def batch_update_duty_status(self, duty_updates: List[Dict], 
                               duty_status_field: str = "DUTY_STATUS") -> Dict[str, bool]:
        """Batch update multiple users' duty status
        
        Args:
            duty_updates: List of dicts with 'username' and 'duty_datetime' keys
            duty_status_field: Common name of the duty status field in AtHoc
            
        Returns:
            Dictionary mapping usernames to success/failure status
        """
        if not duty_updates:
            return {}
        
        # Prepare user data for sync
        users_data = []
        for update in duty_updates:
            username = update.get("username")
            duty_datetime = update.get("duty_datetime")
            
            if not username:
                continue
                
            user_data = {
                "LOGIN_ID": username,
                duty_status_field: duty_datetime or ""
            }
            users_data.append(user_data)
        
        # Perform batch sync
        try:
            results = self.sync_users_by_common_names(users_data)
            
            # Map results back to usernames
            status_map = {}
            for result in results:
                username = result.get("LOGIN_ID")
                sync_status = result.get(":SyncStatus")
                status_map[username] = (sync_status == "OK")
            
            return status_map
            
        except Exception as e:
            print(f"Batch duty status update failed: {str(e)}")
            # Return all failed
            return {update.get("username"): False for update in duty_updates if update.get("username")}

    def query_users_with_old_duty_status(self, duty_status_field: str = "DUTY_STATUS", 
                                       hours_threshold: int = 24) -> List[str]:
        """Query users with duty status older than threshold (for auto-cleanup)
        
        Args:
            duty_status_field: Common name of the duty status field
            hours_threshold: Hours after which duty status is considered old
            
        Returns:
            List of usernames that need duty status cleared
        """
        # Calculate cutoff datetime (subtract threshold hours from now)
        cutoff_time = datetime.now() - timedelta(hours=hours_threshold)
        cutoff_formatted = self.format_datetime_for_athoc(cutoff_time)
        
        print(f"DEBUG: Looking for users with {duty_status_field} older than {cutoff_formatted}")
        
        # Use the existing user search API to find users with old duty status
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/users/search/basic"
        
        # Search criteria: duty status field is present AND is older than cutoff
        # AtHoc query syntax: field pr (present) and field lt 'datetime'
        criteria = f"{duty_status_field} pr and {duty_status_field} lt '{cutoff_formatted}'"
        
        params = {
            "Criteria": criteria,
            "Fields": f"LOGIN_ID,{duty_status_field}",
            "limit": 1000  # Adjust as needed
        }
        
        try:
            response = self.session.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            users = response.json().get("Users", [])
            usernames = [user["LOGIN_ID"] for user in users if user.get("LOGIN_ID")]
            
            print(f"Found {len(usernames)} users with duty status older than {hours_threshold} hours")
            return usernames
            
        except Exception as e:
            print(f"WARNING: Error querying users with old duty status: {str(e)}")
            return []

    def clear_old_duty_status(self, duty_status_field: str = "DUTY_STATUS", 
                            hours_threshold: int = 24) -> int:
        """Clear duty status for users with timestamps older than threshold
        
        Args:
            duty_status_field: Common name of the duty status field
            hours_threshold: Hours after which to clear duty status
            
        Returns:
            Number of users successfully cleared
        """
        old_duty_users = self.query_users_with_old_duty_status(duty_status_field, hours_threshold)
        
        if not old_duty_users:
            return 0
        
        # Prepare batch update to clear duty status
        duty_updates = [
            {"username": username, "duty_datetime": None}
            for username in old_duty_users
        ]
        
        # Perform batch clear
        results = self.batch_update_duty_status(duty_updates, duty_status_field)
        
        # Count successes
        success_count = sum(1 for success in results.values() if success)
        
        print(f"Auto-cleanup: Cleared duty status for {success_count}/{len(old_duty_users)} users")
        return success_count 