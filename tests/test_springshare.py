import pytest
import respx
import httpx
import time
from purduelibrary_mcp_server.config import SpringshareConfig
from purduelibrary_mcp_server.springshare import SpringshareClient, SpringshareAPIError
from purduelibrary_mcp_server.server import springshare_search_databases
from mcp.server.fastmcp import Context

@pytest.fixture
def ss_config():
    return SpringshareConfig(
        libguides_base_url="https://lgapi-us.libapps.com/1.2",
        client_id="1079",
        client_secret="o7tlgknxbPRKOULSlAT1"
    )

@pytest.mark.asyncio
@respx.mock
async def test_springshare_client_get_token(ss_config):
    # Mock token request
    respx.post("https://lgapi-us.libapps.com/1.2/oauth/token").respond(
        status_code=200,
        json={
            "access_token": "mocked_access_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "az_get,subjects_get,guides_get"
        }
    )
    
    async with httpx.AsyncClient() as http_client:
        client = SpringshareClient(http_client, ss_config)
        token = await client._get_token()
        assert token == "mocked_access_token"
        assert client.access_token == "mocked_access_token"
        assert client.token_expires_at > time.time()

@pytest.mark.asyncio
@respx.mock
async def test_springshare_client_token_caching(ss_config):
    # Mock token request once
    route = respx.post("https://lgapi-us.libapps.com/1.2/oauth/token").respond(
        status_code=200,
        json={
            "access_token": "mocked_access_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "az_get,subjects_get,guides_get"
        }
    )
    
    async with httpx.AsyncClient() as http_client:
        client = SpringshareClient(http_client, ss_config)
        # First call gets from network
        token1 = await client._get_token()
        # Second call gets from cache
        token2 = await client._get_token()
        
        assert token1 == token2 == "mocked_access_token"
        assert route.call_count == 1

@pytest.mark.asyncio
@respx.mock
async def test_springshare_client_get_databases(ss_config):
    respx.post("https://lgapi-us.libapps.com/1.2/oauth/token").respond(
        status_code=200,
        json={
            "access_token": "mocked_access_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
    )
    
    # Mock /az GET request
    respx.get("https://lgapi-us.libapps.com/1.2/az").respond(
        status_code=200,
        json=[
            {
                "id": "5003",
                "name": "JSTOR",
                "description": "Multi-disciplinary archive of scholarly journals.",
                "url": "https://www.jstor.org",
                "az_vendor_name": "ITHAKA"
            }
        ]
    )
    
    async with httpx.AsyncClient() as http_client:
        client = SpringshareClient(http_client, ss_config)
        dbs = await client.get_databases()
        assert len(dbs) == 1
        assert dbs[0]["name"] == "JSTOR"
        assert dbs[0]["url"] == "https://www.jstor.org"

@pytest.mark.asyncio
@respx.mock
async def test_springshare_client_search_databases(ss_config):
    respx.post("https://lgapi-us.libapps.com/1.2/oauth/token").respond(
        status_code=200,
        json={
            "access_token": "mocked_access_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
    )
    
    # Mock /az GET request returning multiple databases
    respx.get("https://lgapi-us.libapps.com/1.2/az").respond(
        status_code=200,
        json=[
            {
                "id": "1",
                "name": "Business Source Complete",
                "description": "Premium business database.",
                "url": "https://example.com/bsc",
                "az_vendor_name": "EBSCO",
                "subjects": [{"name": "Business"}, {"name": "Economics"}]
            },
            {
                "id": "2",
                "name": "JSTOR",
                "description": "Scholarly journal archive.",
                "url": "https://www.jstor.org",
                "az_vendor_name": "ITHAKA",
                "subjects": [{"name": "History"}, {"name": "Literature"}]
            }
        ]
    )
    
    async with httpx.AsyncClient() as http_client:
        client = SpringshareClient(http_client, ss_config)
        
        # Test exact match
        matches = await client.search_databases("JSTOR")
        assert len(matches) == 1
        assert matches[0]["name"] == "JSTOR"
        assert matches[0]["_score"] == 3
        
        # Test subject match
        matches = await client.search_databases("Business")
        assert len(matches) == 1
        assert matches[0]["name"] == "Business Source Complete"
        assert matches[0]["_score"] == 2
        
        # Test no match
        matches = await client.search_databases("Nonexistent")
        assert len(matches) == 0

@pytest.mark.asyncio
@respx.mock
async def test_springshare_client_error_handling(ss_config):
    # Mock token request with error
    respx.post("https://lgapi-us.libapps.com/1.2/oauth/token").respond(
        status_code=400,
        json={"error": "invalid_client", "error_description": "The client credentials are invalid"}
    )
    
    async with httpx.AsyncClient() as http_client:
        client = SpringshareClient(http_client, ss_config)
        with pytest.raises(SpringshareAPIError) as exc_info:
            await client.get_databases()
        assert "The client credentials are invalid" in str(exc_info.value)
