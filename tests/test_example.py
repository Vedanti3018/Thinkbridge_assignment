"""
Tests for the example module.
"""

from unittest.mock import Mock, patch

import pytest

from thinkbridge.example import fetch_data, greet


class TestGreet:
    """Test cases for the greet function."""

    def test_greet_with_name(self) -> None:
        """Test that greet returns the expected message."""
        result = greet("Alice")
        assert result == "Hello, Alice! Welcome to Thinkbridge."

    def test_greet_with_empty_name(self) -> None:
        """Test that greet works with empty name."""
        result = greet("")
        assert result == "Hello, ! Welcome to Thinkbridge."


class TestFetchData:
    """Test cases for the fetch_data function."""

    @patch("thinkbridge.example.requests.get")
    def test_fetch_data_success(self, mock_get: Mock) -> None:
        """Test successful data fetching."""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {"message": "Hello, World!"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_data("https://api.example.com/data")

        assert result == {"message": "Hello, World!"}
        mock_get.assert_called_once_with("https://api.example.com/data")

    @patch("thinkbridge.example.requests.get")
    def test_fetch_data_failure(self, mock_get: Mock) -> None:
        """Test that fetch_data raises an exception on failure."""
        # Mock a failed response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP Error")
        mock_get.return_value = mock_response

        with pytest.raises(Exception, match="HTTP Error"):
            fetch_data("https://api.example.com/data")
