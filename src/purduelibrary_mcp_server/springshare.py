import time
import httpx
from typing import Any
from purduelibrary_mcp_server.config import SpringshareConfig

class SpringshareAPIError(Exception):
    """Custom exception for Springshare API errors."""
    pass

class SpringshareClient:
    """HTTP client for interacting with Springshare LibGuides v1.2 API."""

    def __init__(self, http_client: httpx.AsyncClient, config: SpringshareConfig):
        self.http_client = http_client
        self.config = config
        self.access_token: str | None = None
        self.token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        """Fetch or return cached OAuth2 Bearer token."""
        if not self.config.client_id or not self.config.client_secret:
            raise SpringshareAPIError(
                "Springshare client credentials are not configured.\n"
                "Please configure SPRINGSHARE_CLIENT_ID and SPRINGSHARE_CLIENT_SECRET in your .env file."
            )

        # Check if cached token is still valid (with a 60-second buffer)
        if self.access_token and time.time() < self.token_expires_at - 60:
            return self.access_token

        token_url = f"{self.config.libguides_base_url.rstrip('/')}/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret
        }

        try:
            resp = await self.http_client.post(token_url, data=data, timeout=self.config.request_timeout)
            if resp.status_code == 400:
                body = resp.json()
                raise SpringshareAPIError(
                    f"Authentication failed (400 Bad Request): {body.get('error_description', body.get('error', 'Invalid client credentials'))}"
                )
            resp.raise_for_status()
            token_data = resp.json()
            self.access_token = token_data["access_token"]
            self.token_expires_at = time.time() + token_data.get("expires_in", 3600)
            return self.access_token
        except httpx.HTTPStatusError as e:
            raise SpringshareAPIError(f"HTTP error during authentication: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            if not isinstance(e, SpringshareAPIError):
                raise SpringshareAPIError(f"Unexpected authentication error: {e}")
            raise e

    async def get_databases(self) -> list[dict[str, Any]]:
        """Fetch all A-Z databases with expanded subjects."""
        token = await self._get_token()
        url = f"{self.config.libguides_base_url.rstrip('/')}/az"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"expand": "subjects,az_props"}

        try:
            resp = await self.http_client.get(url, headers=headers, params=params, timeout=self.config.request_timeout)
            if resp.status_code == 403:
                raise SpringshareAPIError(
                    "Forbidden (403): The request requires higher privileges than provided by the access token.\n"
                    "Please verify that your LibGuides API application has the 'Get list of A-Z assets' scope enabled."
                )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise SpringshareAPIError(f"HTTP error fetching databases: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            if not isinstance(e, SpringshareAPIError):
                raise SpringshareAPIError(f"Unexpected error fetching databases: {e}")
            raise e

    async def search_databases(self, query: str) -> list[dict[str, Any]]:
        """Fetch all databases and search locally."""
        databases = await self.get_databases()
        query_lower = query.lower().strip()
        
        matches = []
        for db in databases:
            name = db.get("name", "") or ""
            description = db.get("description", "") or ""
            vendor = db.get("az_vendor_name", "") or ""
            
            # Alt names and more info in meta
            meta = db.get("meta", {}) or {}
            more_info = meta.get("more_info", "") or ""
            alt_names = meta.get("alt_names", "") or ""
            
            # Subjects
            subjects = db.get("subjects", []) or []
            subject_names = [sub.get("name", "").lower() for sub in subjects if sub]
            
            # Match scoring
            name_lower = name.lower()
            if query_lower == name_lower:
                score = 3  # Perfect title match
            elif name_lower.startswith(query_lower):
                score = 2  # Prefix title match
            elif (
                query_lower in name_lower
                or query_lower in description.lower()
                or query_lower in vendor.lower()
                or query_lower in more_info.lower()
                or query_lower in alt_names.lower()
                or any(query_lower in s for s in subject_names)
            ):
                score = 1  # Substring match anywhere
            else:
                score = 0
                
            if score > 0:
                db["_score"] = score
                matches.append(db)
                
        # Sort by score (highest first), then by name alphabetically
        matches.sort(key=lambda x: (-x["_score"], x.get("name", "").lower()))
        return matches
