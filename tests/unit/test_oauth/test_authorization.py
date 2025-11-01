"""Tests for OAuth authorization URL construction"""
import pytest
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from oauth.authorization import AuthorizationURLBuilder
from oauth.pkce import PKCEManager


@pytest.mark.unit
class TestAuthorizationURLBuilder:
    """Test suite for OAuth authorization URL construction"""

    def test_get_authorize_url_structure(self):
        """Test that standard authorization URL has correct structure"""
        pkce = PKCEManager()
        builder = AuthorizationURLBuilder(pkce)

        with patch.object(pkce, 'save_pkce'):
            url = builder.get_authorize_url()

        # Parse URL
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Check base URL
        assert parsed.scheme == "https"
        assert "claude.ai" in parsed.netloc or "anthropic.com" in parsed.netloc
        assert "/oauth/authorize" in parsed.path

        # Check required parameters
        assert params["code"][0] == "true"
        assert params["response_type"][0] == "code"
        assert params["code_challenge_method"][0] == "S256"
        assert "client_id" in params
        assert "redirect_uri" in params
        assert "scope" in params
        assert "code_challenge" in params
        assert "state" in params

    def test_get_authorize_url_pkce_integration(self):
        """Test that authorization URL properly integrates PKCE"""
        pkce = PKCEManager()
        builder = AuthorizationURLBuilder(pkce)

        with patch.object(pkce, 'save_pkce'):
            url = builder.get_authorize_url()

        # Verify PKCE values were set
        assert pkce.code_verifier is not None
        assert pkce.state is not None
        assert pkce.state == pkce.code_verifier  # OpenCode uses verifier as state

        # Verify code challenge is in URL
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert len(params["code_challenge"][0]) > 0

    def test_get_authorize_url_saves_pkce(self):
        """Test that authorization URL generation saves PKCE values"""
        pkce = PKCEManager()
        builder = AuthorizationURLBuilder(pkce)

        with patch.object(pkce, 'save_pkce') as mock_save:
            builder.get_authorize_url()
            mock_save.assert_called_once()

    def test_get_authorize_url_for_long_term_token_structure(self):
        """Test that long-term token URL has correct structure"""
        pkce = PKCEManager()
        builder = AuthorizationURLBuilder(pkce)

        with patch.object(pkce, 'save_pkce'):
            url = builder.get_authorize_url_for_long_term_token()

        # Parse URL
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Check base URL
        assert parsed.scheme == "https"
        assert "/oauth/authorize" in parsed.path

        # Check required parameters
        assert params["code"][0] == "true"
        assert params["response_type"][0] == "code"
        assert params["code_challenge_method"][0] == "S256"

        # Check minimal scope for long-term tokens
        assert params["scope"][0] == "user:inference"

    def test_get_authorize_url_for_long_term_token_minimal_scope(self):
        """Test that long-term token URL uses minimal scope"""
        pkce = PKCEManager()
        builder = AuthorizationURLBuilder(pkce)

        with patch.object(pkce, 'save_pkce'):
            url = builder.get_authorize_url_for_long_term_token()

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Long-term tokens should use only user:inference scope
        assert params["scope"][0] == "user:inference"
        assert "user:profile" not in params["scope"][0]
        assert "org:create_api_key" not in params["scope"][0]

    def test_start_login_flow_opens_browser(self):
        """Test that start_login_flow opens browser with correct URL"""
        pkce = PKCEManager()
        builder = AuthorizationURLBuilder(pkce)

        with patch.object(pkce, 'save_pkce'), \
             patch('oauth.authorization.webbrowser.open') as mock_open:
            url = builder.start_login_flow()

            # Verify browser was opened with the URL
            mock_open.assert_called_once_with(url)

            # Verify URL is valid
            assert url.startswith("https://")
            assert "/oauth/authorize" in url

    def test_start_login_flow_returns_url(self):
        """Test that start_login_flow returns the authorization URL"""
        pkce = PKCEManager()
        builder = AuthorizationURLBuilder(pkce)

        with patch.object(pkce, 'save_pkce'), \
             patch('oauth.authorization.webbrowser.open'):
            url = builder.start_login_flow()

            # Verify URL structure
            parsed = urlparse(url)
            assert parsed.scheme == "https"
            assert "/oauth/authorize" in parsed.path

    def test_multiple_url_generations_unique_pkce(self):
        """Test that multiple URL generations create unique PKCE values"""
        pkce1 = PKCEManager()
        builder1 = AuthorizationURLBuilder(pkce1)

        pkce2 = PKCEManager()
        builder2 = AuthorizationURLBuilder(pkce2)

        with patch.object(pkce1, 'save_pkce'), \
             patch.object(pkce2, 'save_pkce'):
            url1 = builder1.get_authorize_url()
            url2 = builder2.get_authorize_url()

        # URLs should be different due to different PKCE values
        assert url1 != url2

        # PKCE values should be different
        assert pkce1.code_verifier != pkce2.code_verifier
        assert pkce1.state != pkce2.state
