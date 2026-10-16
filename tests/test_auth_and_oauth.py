import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import decrypt_token, verify_oauth_state
from app.db.database import Base
from app.db.dependencies import get_db
from app.models.user import User, UserGitHubAccount
from main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

TestingSessionLocal = sessionmaker(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestAuthAndOAuth(unittest.TestCase):

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.clear()

    def test_signup_success(self):
        """Test user signup with valid credentials."""
        res = self.client.post("/api/v1/auth/signup", json={"email": "newuser@example.com", "password": "securepassword123", "full_name": "New User"})
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["email"], "newuser@example.com")
        self.assertEqual(data["user"]["full_name"], "New User")
        self.assertFalse(data["user"]["has_github_connected"])
        # Check cookies
        self.assertIn("access_token", res.cookies)
        self.assertIn("refresh_token", res.cookies)

    def test_signup_duplicate_email_fails(self):
        """Test signup with duplicate email returns 409 conflict."""
        self.client.post("/api/v1/auth/signup", json={"email": "dupe@example.com", "password": "securepassword123"})
        res = self.client.post("/api/v1/auth/signup", json={"email": "dupe@example.com", "password": "anotherpassword"})
        self.assertEqual(res.status_code, 409)

    def test_login_success(self):
        """Test login with valid email and password."""
        self.client.post("/api/v1/auth/signup", json={"email": "loginuser@example.com", "password": "mypassword123"})
        res = self.client.post("/api/v1/auth/login", json={"email": "loginuser@example.com", "password": "mypassword123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["email"], "loginuser@example.com")

    def test_login_invalid_credentials_fails(self):
        """Test login with invalid password fails with 401."""
        self.client.post("/api/v1/auth/signup", json={"email": "user@example.com", "password": "correctpassword"})
        res = self.client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid email or password", res.json()["detail"])

    def test_authenticated_me_endpoint(self):
        """Test /auth/me returns current user info when authenticated."""
        signup_res = self.client.post("/api/v1/auth/signup", json={"email": "me@example.com", "password": "password123", "full_name": "Me"})
        token = signup_res.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        res = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "me@example.com")

    def test_unauthenticated_me_fails(self):
        """Test /auth/me fails with 401 when no token is supplied."""
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_github_login_url_generation(self):
        """Test GET /auth/github/login generates authorization URL with signed CSRF state."""
        res = self.client.get("/api/v1/auth/github/login")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("authorization_url", data)
        self.assertIn("state", data)
        self.assertIn("github.com/login/oauth/authorize", data["authorization_url"])

        state_payload = verify_oauth_state(data["state"])
        self.assertEqual(state_payload["type"], "oauth_state")

    def test_github_callback_csrf_validation_failure(self):
        """Test callback fails when state parameter is invalid or tampered."""
        res = self.client.get("/api/v1/auth/github/callback?code=mock_code&state=invalid_state_token")
        self.assertEqual(res.status_code, 400)
        self.assertIn("CSRF validation failed", res.json()["detail"])

    @patch("urllib.request.urlopen")
    def test_github_callback_success_and_token_encryption(self, mock_urlopen):
        """Test GitHub callback exchanges code, fetches profile, encrypts token, and links user."""
        mock_token_resp = MagicMock()
        mock_token_resp.read.return_value = json.dumps({"access_token": "gho_real_secret_oauth_token_12345", "scope": "repo,read:user"}).encode()
        mock_token_resp.__enter__.return_value = mock_token_resp

        mock_profile_resp = MagicMock()
        mock_profile_resp.read.return_value = json.dumps({"id": 998877, "login": "octocat", "name": "The Octocat", "email": "octocat@github.com"}).encode()
        mock_profile_resp.__enter__.return_value = mock_profile_resp

        mock_urlopen.side_effect = [mock_token_resp, mock_profile_resp]


        # Generate valid state token
        login_res = self.client.get("/api/v1/auth/github/login")
        state = login_res.json()["state"]

        callback_res = self.client.get(f"/api/v1/auth/github/callback?code=valid_code&state={state}")
        self.assertEqual(callback_res.status_code, 200)
        data = callback_res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["email"], "octocat@github.com")
        self.assertTrue(data["user"]["has_github_connected"])
        self.assertEqual(data["user"]["github_username"], "octocat")

        # SECURITY VERIFICATION:
        # 1. Plain-text token is NEVER in API response
        self.assertNotIn("gho_real_secret_oauth_token_12345", json.dumps(data))

        # 2. Token stored in DB is encrypted using Fernet symmetric encryption using AES-128-CBC with HMAC authentication
        user_record = self.db.query(User).filter(User.email == "octocat@github.com").first()
        self.assertIsNotNone(user_record.github_account)
        encrypted_in_db = user_record.github_account.encrypted_access_token
        self.assertNotEqual(encrypted_in_db, "gho_real_secret_oauth_token_12345")
        self.assertEqual(decrypt_token(encrypted_in_db), "gho_real_secret_oauth_token_12345")

    def test_github_disconnect(self):
        """Test disconnecting a linked GitHub account."""
        signup_res = self.client.post("/api/v1/auth/signup", json={"email": "ghuser@example.com", "password": "password123"})
        token = signup_res.json()["access_token"]
        user_id = signup_res.json()["user"]["id"]

        # Create linked account directly in DB
        gh_acc = UserGitHubAccount(user_id=user_id, github_user_id=555, github_username="ghuser", encrypted_access_token="enc")
        self.db.add(gh_acc)
        self.db.commit()

        headers = {"Authorization": f"Bearer {token}"}
        me_before = self.client.get("/api/v1/auth/me", headers=headers).json()
        self.assertTrue(me_before["has_github_connected"])

        disc_res = self.client.post("/api/v1/auth/github/disconnect", headers=headers)
        self.assertEqual(disc_res.status_code, 200)

        me_after = self.client.get("/api/v1/auth/me", headers=headers).json()
        self.assertFalse(me_after["has_github_connected"])


if __name__ == "__main__":
    unittest.main()
