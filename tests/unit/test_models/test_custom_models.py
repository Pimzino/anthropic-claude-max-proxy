"""Tests for custom models configuration"""
import pytest
from unittest.mock import patch, mock_open
import json

from models.custom_models import load_custom_models


@pytest.mark.unit
class TestLoadCustomModels:
    """Test suite for loading custom models"""

    def test_load_empty_config(self):
        """Test loading empty custom models config"""
        mock_data = json.dumps({"custom_models": []})

        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("pathlib.Path.exists", return_value=True):
                models = load_custom_models()

                assert models == []

    def test_load_single_model(self):
        """Test loading single custom model"""
        mock_data = json.dumps({
            "custom_models": [
                {
                    "id": "test-model",
                    "base_url": "https://api.test.com/v1",
                    "api_key": "test-key"
                }
            ]
        })

        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("pathlib.Path.exists", return_value=True):
                models = load_custom_models()

                assert len(models) == 1
                assert models[0]["id"] == "test-model"

    def test_load_multiple_models(self):
        """Test loading multiple custom models"""
        mock_data = json.dumps({
            "custom_models": [
                {"id": "model1", "base_url": "url1", "api_key": "key1"},
                {"id": "model2", "base_url": "url2", "api_key": "key2"}
            ]
        })

        with patch("builtins.open", mock_open(read_data=mock_data)):
            with patch("pathlib.Path.exists", return_value=True):
                models = load_custom_models()

                assert len(models) == 2

    def test_file_not_found_returns_empty(self):
        """Test that missing file returns empty list"""
        with patch("pathlib.Path.exists", return_value=False):
            models = load_custom_models()

            assert models == []

    def test_invalid_json_returns_empty(self):
        """Test that invalid JSON returns empty list"""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch("pathlib.Path.exists", return_value=True):
                models = load_custom_models()

                assert models == []
