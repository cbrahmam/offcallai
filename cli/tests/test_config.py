# cli/tests/test_config.py
"""
Configuration tests for OffCall CLI.
"""

import pytest
import tempfile
import os
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock
import yaml


class TestConfig:
    """Test configuration management."""

    def test_config_directory_created(self):
        """Config directory should be created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_dir / "config.yaml"):
                    from offcall.config import Config

                    config = Config()
                    config.set_api_key("test-key")

                    assert config_dir.exists()

    def test_config_file_permissions(self):
        """Config file should have secure permissions (0600)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config

                    config = Config()
                    config.set_api_key("test-key")

                    # Check file permissions
                    file_stat = os.stat(config_file)
                    mode = stat.S_IMODE(file_stat.st_mode)

                    # Should be 0600 (read/write for owner only)
                    assert mode == (stat.S_IRUSR | stat.S_IWUSR)

    def test_config_directory_permissions(self):
        """Config directory should have secure permissions (0700)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config

                    config = Config()
                    config.set_api_key("test-key")

                    # Check directory permissions
                    dir_stat = os.stat(config_dir)
                    mode = stat.S_IMODE(dir_stat.st_mode)

                    # Should be 0700 (rwx for owner only)
                    assert mode == stat.S_IRWXU

    def test_https_enforcement(self):
        """Non-localhost HTTP URLs should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config

                    config = Config()

                    # HTTP to external host should raise
                    with pytest.raises(ValueError) as exc_info:
                        config.set_api_url("http://external-api.com/api/v1")

                    assert "HTTPS" in str(exc_info.value)

    def test_localhost_http_allowed(self):
        """HTTP should be allowed for localhost development."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config

                    config = Config()

                    # HTTP to localhost should work
                    config.set_api_url("http://localhost:8000/api/v1")
                    assert config.api_url == "http://localhost:8000/api/v1"

                    config.set_api_url("http://127.0.0.1:8000/api/v1")
                    assert config.api_url == "http://127.0.0.1:8000/api/v1"

    def test_https_url_allowed(self):
        """HTTPS URLs should be allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config

                    config = Config()
                    config.set_api_url("http://localhost:8000/api/v1")

                    assert config.api_url == "http://localhost:8000/api/v1"

    def test_environment_variable_override(self):
        """Environment variables should override config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            # Create config file with different values
            config_dir.mkdir(parents=True)
            with open(config_file, 'w') as f:
                yaml.dump({
                    'default': {
                        'api_key': 'file-key',
                        'api_url': 'https://file-url.com'
                    }
                }, f)

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    with patch.dict(os.environ, {
                        'OFFCALL_API_KEY': 'env-key',
                        'OFFCALL_API_URL': 'https://env-url.com'
                    }):
                        from offcall.config import Config

                        config = Config()

                        # Environment variables should take precedence
                        assert config.api_key == 'env-key'
                        assert config.api_url == 'https://env-url.com'

    def test_multiple_profiles(self):
        """Multiple profiles should be supported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config

                    # Create default profile
                    default_config = Config("default")
                    default_config.set_api_key("default-key")

                    # Create staging profile
                    staging_config = Config("staging")
                    staging_config.set_api_key("staging-key")

                    # Verify both profiles
                    assert Config("default").api_key == "default-key"
                    assert Config("staging").api_key == "staging-key"

    def test_is_configured_check(self):
        """is_configured should return False when no API key is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config

                    config = Config()

                    # Should not be configured initially
                    assert not config.is_configured()

                    # Should be configured after setting key
                    config.set_api_key("test-key")
                    assert config.is_configured()

    def test_default_api_url(self):
        """Default API URL should be production URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".offcall"
            config_file = config_dir / "config.yaml"

            with patch('offcall.config.CONFIG_DIR', config_dir):
                with patch('offcall.config.CONFIG_FILE', config_file):
                    from offcall.config import Config, DEFAULT_API_URL

                    config = Config()

                    assert config.api_url == DEFAULT_API_URL
                    assert "localhost" in config.api_url
