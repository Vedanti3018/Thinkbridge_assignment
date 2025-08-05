"""
Example module demonstrating basic functionality.
"""

from typing import Any

import requests


def fetch_data(url: str) -> dict[str, Any]:
    """
    Fetch data from a URL and return as JSON.

    Args:
        url: The URL to fetch data from

    Returns:
        dict: The JSON response data

    Raises:
        requests.RequestException: If the request fails
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def greet(name: str) -> str:
    """
    Return a greeting message.

    Args:
        name: The name to greet

    Returns:
        str: A greeting message
    """
    return f"Hello, {name}! Welcome to Thinkbridge."
