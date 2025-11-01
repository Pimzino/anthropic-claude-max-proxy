"""Tests for cli/status_display module"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from cli.status_display import show_token_status, get_auth_status


@pytest.mark.unit
class TestShowTokenStatus:
    """Test suite for show_token_status function"""

    @patch('cli.status_display.input')
    def test_show_token_status_with_tokens(self, mock_input):
        """Test showing token status when tokens exist"""
        mock_input.return_value = ""

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": "2025-12-31T23:59:59",
            "time_until_expiry": "365 days"
        }
        storage.token_file = "/path/to/tokens.json"

        console = MagicMock()

        show_token_status(storage, console)

        # Verify table was printed
        assert console.print.call_count >= 1

    @patch('cli.status_display.input')
    def test_show_token_status_no_tokens(self, mock_input):
        """Test showing token status when no tokens exist"""
        mock_input.return_value = ""

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": False,
            "is_expired": False,
            "expires_at": None,
            "time_until_expiry": None
        }
        storage.token_file = "/path/to/tokens.json"

        console = MagicMock()

        show_token_status(storage, console)

        # Verify table was printed
        assert console.print.call_count >= 1

    @patch('cli.status_display.input')
    def test_show_token_status_expired(self, mock_input):
        """Test showing token status when tokens are expired"""
        mock_input.return_value = ""

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "expires_at": "2024-01-01T00:00:00",
            "time_until_expiry": "expired 30 days ago"
        }
        storage.token_file = "/path/to/tokens.json"

        console = MagicMock()

        show_token_status(storage, console)

        # Verify table was printed
        assert console.print.call_count >= 1


@pytest.mark.unit
class TestGetAuthStatus:
    """Test suite for get_auth_status function"""

    def test_get_auth_status_no_tokens(self):
        """Test auth status when no tokens exist"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": False,
            "is_expired": False,
            "expires_at": None,
            "time_until_expiry": None
        }

        status, detail = get_auth_status(storage)

        assert status == "NO AUTH"
        assert "No tokens available" in detail

    def test_get_auth_status_expired(self):
        """Test auth status when tokens are expired"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "expires_at": "2024-01-01T00:00:00",
            "time_until_expiry": "expired 30 days ago"
        }

        status, detail = get_auth_status(storage)

        assert status == "EXPIRED"
        assert "Expired" in detail

    def test_get_auth_status_valid_hours(self):
        """Test auth status with valid token (hours remaining)"""
        future_time = datetime.now() + timedelta(hours=3, minutes=30)

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": future_time.isoformat()
        }

        status, detail = get_auth_status(storage)

        assert status == "VALID"
        assert "Expires in" in detail
        assert "h" in detail  # Should show hours

    def test_get_auth_status_valid_minutes_only(self):
        """Test auth status with valid token (minutes only)"""
        future_time = datetime.now() + timedelta(minutes=45)

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": future_time.isoformat()
        }

        status, detail = get_auth_status(storage)

        assert status == "VALID"
        assert "Expires in" in detail
        assert "m" in detail  # Should show minutes

    def test_get_auth_status_negative_delta(self):
        """Test auth status with expired token (negative time delta)"""
        past_time = datetime.now() - timedelta(hours=1)

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,  # Status says not expired but time is in past
            "expires_at": past_time.isoformat()
        }

        status, detail = get_auth_status(storage)

        assert status == "EXPIRED"
        assert "expired" in detail.lower()

    def test_get_auth_status_no_expires_at(self):
        """Test auth status when expires_at is None"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": None
        }

        status, detail = get_auth_status(storage)

        assert status == "UNKNOWN"
        assert "Unable to determine" in detail

    def test_get_auth_status_valid_days(self):
        """Test auth status with valid token (many days remaining)"""
        future_time = datetime.now() + timedelta(days=30, hours=5)

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": future_time.isoformat()
        }

        status, detail = get_auth_status(storage)

        assert status == "VALID"
        assert "Expires in" in detail
        # Should show hours and minutes from the delta

    def test_get_auth_status_edge_case_zero_minutes(self):
        """Test auth status with token expiring in less than a minute"""
        future_time = datetime.now() + timedelta(seconds=30)

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": future_time.isoformat()
        }

        status, detail = get_auth_status(storage)

        assert status == "VALID"
        # Should show 0m when less than a minute
        assert "0m" in detail or "Expires in" in detail

    def test_get_auth_status_exactly_one_hour(self):
        """Test auth status with exactly 1 hour remaining"""
        future_time = datetime.now() + timedelta(hours=1)

        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": future_time.isoformat()
        }

        status, detail = get_auth_status(storage)

        assert status == "VALID"
        assert "1h" in detail
