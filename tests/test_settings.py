"""Unit tests for the settings module."""

import unittest
from unittest.mock import patch

from django.core.signals import setting_changed
from django.test import TestCase, override_settings

from djangorestframework_mcp.settings import (
    DEFAULTS,
    MCPSettings,
    mcp_settings,
    reload_mcp_settings,
)


class MCPSettingsTests(TestCase):
    """Test the MCPSettings class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a fresh settings instance for testing
        self.settings = MCPSettings()

    def test_defaults(self):
        """Test that default values are correctly defined."""
        expected_defaults = {
            "BYPASS_VIEWSET_AUTHENTICATION": False,
            "BYPASS_VIEWSET_PERMISSIONS": False,
        }
        self.assertEqual(DEFAULTS, expected_defaults)

    def test_default_values(self):
        """Test accessing default setting values."""
        # Test default values
        self.assertFalse(self.settings.BYPASS_VIEWSET_AUTHENTICATION)
        self.assertFalse(self.settings.BYPASS_VIEWSET_PERMISSIONS)

    def test_invalid_setting_raises_attribute_error(self):
        """Test that accessing invalid settings raises AttributeError."""
        with self.assertRaises(AttributeError) as cm:
            _ = self.settings.INVALID_SETTING

        self.assertIn("Invalid MCP setting: 'INVALID_SETTING'", str(cm.exception))

    @override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": True})
    def test_user_settings_override_defaults(self):
        """Test that user settings override defaults."""
        # Create new instance to pick up the override
        settings_obj = MCPSettings()

        self.assertTrue(settings_obj.BYPASS_VIEWSET_AUTHENTICATION)
        self.assertFalse(settings_obj.BYPASS_VIEWSET_PERMISSIONS)  # Still default

    @override_settings(
        DJANGORESTFRAMEWORK_MCP={
            "BYPASS_VIEWSET_AUTHENTICATION": True,
            "BYPASS_VIEWSET_PERMISSIONS": True,
        }
    )
    def test_multiple_user_settings(self):
        """Test multiple user settings override defaults."""
        settings_obj = MCPSettings()

        self.assertTrue(settings_obj.BYPASS_VIEWSET_AUTHENTICATION)
        self.assertTrue(settings_obj.BYPASS_VIEWSET_PERMISSIONS)

    def test_caching_behavior(self):
        """Test that settings are cached after first access."""
        # Access a setting
        value1 = self.settings.BYPASS_VIEWSET_AUTHENTICATION

        # Access again - should be cached
        value2 = self.settings.BYPASS_VIEWSET_AUTHENTICATION

        self.assertEqual(value1, value2)
        self.assertIn("BYPASS_VIEWSET_AUTHENTICATION", self.settings._cached_attrs)

    def test_user_settings_property(self):
        """Test the user_settings property."""
        with override_settings(
            DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": True}
        ):
            settings_obj = MCPSettings()
            user_settings = settings_obj.user_settings
            self.assertEqual(user_settings, {"BYPASS_VIEWSET_AUTHENTICATION": True})

    def test_user_settings_property_empty(self):
        """Test the user_settings property when no settings are defined."""
        with override_settings():
            # Remove DJANGORESTFRAMEWORK_MCP if it exists
            from django.conf import settings as django_settings

            if hasattr(django_settings, "DJANGORESTFRAMEWORK_MCP"):
                delattr(django_settings, "DJANGORESTFRAMEWORK_MCP")

            settings_obj = MCPSettings()
            user_settings = settings_obj.user_settings
            self.assertEqual(user_settings, {})

    def test_reload_clears_cache(self):
        """Test that reload() clears the cached attributes."""
        # Access a setting to cache it
        _ = self.settings.BYPASS_VIEWSET_AUTHENTICATION
        self.assertIn("BYPASS_VIEWSET_AUTHENTICATION", self.settings._cached_attrs)

        # Reload should clear cache
        self.settings.reload()
        self.assertEqual(len(self.settings._cached_attrs), 0)
        self.assertFalse(hasattr(self.settings, "_user_settings"))


class GlobalSettingsInstanceTests(TestCase):
    """Test the global mcp_settings instance."""

    def test_global_instance_exists(self):
        """Test that the global mcp_settings instance exists."""
        from djangorestframework_mcp.settings import mcp_settings

        self.assertIsInstance(mcp_settings, MCPSettings)

    def test_global_instance_access(self):
        """Test accessing settings through the global instance."""
        self.assertFalse(mcp_settings.BYPASS_VIEWSET_AUTHENTICATION)
        self.assertFalse(mcp_settings.BYPASS_VIEWSET_PERMISSIONS)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": True})
    def test_global_instance_user_settings(self):
        """Test that the global instance picks up user settings."""
        # Need to reload the global instance to pick up new settings
        mcp_settings.reload()
        self.assertTrue(mcp_settings.BYPASS_VIEWSET_AUTHENTICATION)


class SettingsReloadTests(TestCase):
    """Test the settings reload mechanism."""

    def test_reload_mcp_settings_function(self):
        """Test the reload_mcp_settings function."""
        with patch.object(mcp_settings, "reload") as mock_reload:
            reload_mcp_settings(setting="DJANGORESTFRAMEWORK_MCP")
            mock_reload.assert_called_once()

    def test_reload_mcp_settings_ignores_other_settings(self):
        """Test that reload_mcp_settings ignores other settings."""
        with patch.object(mcp_settings, "reload") as mock_reload:
            reload_mcp_settings(setting="OTHER_SETTING")
            mock_reload.assert_not_called()

    def test_setting_changed_signal_connected(self):
        """Test that the setting_changed signal is connected."""
        # Verify that our reload function is connected to the signal
        receivers = setting_changed._live_receivers(sender=None)
        reload_functions = [
            receiver
            for receiver in receivers
            if receiver.__name__ == "reload_mcp_settings"
        ]
        self.assertTrue(len(reload_functions) > 0)

    def test_settings_reload_on_signal(self):
        """Test that settings reload when the signal is sent."""
        # First access to cache the setting (should be default False)
        original_value = mcp_settings.BYPASS_VIEWSET_AUTHENTICATION
        self.assertFalse(original_value)  # Default value

        # Now apply override and manually reload to simulate signal behavior
        with override_settings(
            DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": True}
        ):
            mcp_settings.reload()
            # Now it should pick up the overridden value
            self.assertTrue(mcp_settings.BYPASS_VIEWSET_AUTHENTICATION)

        # After leaving the override context, reload again and it should go back to default
        mcp_settings.reload()
        self.assertFalse(mcp_settings.BYPASS_VIEWSET_AUTHENTICATION)


class SettingsInitializationTests(unittest.TestCase):
    """Test settings initialization with different parameters."""

    def test_init_with_user_settings(self):
        """Test initialization with explicit user settings."""
        user_settings = {"BYPASS_VIEWSET_AUTHENTICATION": True}
        settings_obj = MCPSettings(user_settings=user_settings)

        self.assertTrue(settings_obj.BYPASS_VIEWSET_AUTHENTICATION)

    def test_init_with_custom_defaults(self):
        """Test initialization with custom defaults."""
        custom_defaults = {
            "BYPASS_VIEWSET_AUTHENTICATION": True,
            "BYPASS_VIEWSET_PERMISSIONS": True,
        }
        settings_obj = MCPSettings(defaults=custom_defaults)

        self.assertTrue(settings_obj.BYPASS_VIEWSET_AUTHENTICATION)
        self.assertTrue(settings_obj.BYPASS_VIEWSET_PERMISSIONS)


if __name__ == "__main__":
    unittest.main()
