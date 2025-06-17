import os
import requests
import ssl
from typing import Dict, List
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from tenacity import retry, stop_after_attempt, wait_exponential

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
    def __init__(self):
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
        
        # Role mapping from API (will be populated if get_roles is called)
        self.roles_by_common_name = {}
        
        # Try to load roles at initialization, but don't fail if it doesn't work
        try:
            self.load_roles()
        except Exception as e:
            print(f"WARNING: Could not load roles at initialization: {str(e)}")
            # Fall back to the static mapping
            self.roles_by_common_name = ROLE_MAP.copy()

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
        """Get alerts for a date range"""
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
        """Get device summary for an alert"""
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/alerts/{alert_id}/reports/devicesummary"
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_user_attributes(self, usernames: List[str]) -> Dict[str, Dict]:
        """Get user attributes for a list of users"""
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
            
    def load_roles(self) -> Dict[str, str]:
        """Load roles from the API and build a mapping of CommonName to Name"""
        roles = self.get_roles()
        
        # Create mapping from CommonName to Name
        role_map = {
            role.get("CommonName", ""): role.get("Name", "Unknown Role")
            for role in roles
            if role.get("CommonName")
        }
        
        # Store for future lookups
        self.roles_by_common_name = role_map
        
        return role_map
    
    def get_roles(self) -> List[Dict]:
        """Get all roles from the API"""
        url = f"{self.base_url}/api/v2/orgs/{self.org_code}/roles"
        
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