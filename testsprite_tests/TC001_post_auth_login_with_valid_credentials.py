import requests
import jwt
import time


def test_post_auth_login_valid_credentials():
    base_url = "http://localhost:5000"
    login_url = f"{base_url}/auth/login"
    email = "admin@gobernacion.gov.co"
    password = "Gob2025*"
    timeout = 30

    payload = {
        "email": email,
        "password": password
    }

    try:
        response = requests.post(login_url, json=payload, timeout=timeout)
        assert response.status_code == 200, f"Expected status 200, got {response.status_code}"

        data = response.json()
        assert "access_token" in data, "access_token not in response"
        assert "refresh_token" in data, "refresh_token not in response"

        access_token = data["access_token"]
        refresh_token = data["refresh_token"]

        # Decode without verification since the secret/key is not known here, just check claims presence
        access_claims = jwt.decode(access_token, options={"verify_signature": False})
        refresh_claims = jwt.decode(refresh_token, options={"verify_signature": False})

        # Check required claims in access token (permissions, role)
        assert "permissions" in access_claims, "permissions claim missing in access_token"
        # permissions may be empty list in shadow mode, still must exist
        assert isinstance(access_claims["permissions"], (list, tuple)), "permissions claim is not a list or tuple"

        assert "role" in access_claims or "role_id" in access_claims, "role or role_id claim missing in access_token"

        # Similarly check refresh token claims contains role or role_id (commonly minimal claims present)
        assert "role" in refresh_claims or "role_id" in refresh_claims, "role or role_id missing in refresh_token claims"

    except requests.exceptions.RequestException as e:
        assert False, f"Request to {login_url} failed: {e}"


test_post_auth_login_valid_credentials()