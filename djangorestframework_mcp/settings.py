"""
Settings for django-rest-framework-mcp are all namespaced in the DJANGORESTFRAMEWORK_MCP setting.
For example your project's `settings.py` file might look like this:

DJANGORESTFRAMEWORK_MCP = {
    'BYPASS_VIEWSET_AUTHENTICATION': False,
    'BYPASS_VIEWSET_PERMISSIONS': False,
}

This module provides the `mcp_settings` object, that is used to access
django-rest-framework-mcp settings, checking for user settings first, then falling
back to the defaults.
"""

from django.conf import settings

# Import from `django.core.signals` instead of the official location
# `django.test.signals` to avoid importing the test module unnecessarily.
from django.core.signals import setting_changed

DEFAULTS = {
    # Authentication and permission bypass settings
    "BYPASS_VIEWSET_AUTHENTICATION": False,
    "BYPASS_VIEWSET_PERMISSIONS": False,
}


class MCPSettings:
    """
    A settings object that allows django-rest-framework-mcp settings to be accessed as
    properties. For example:

        from djangorestframework_mcp.settings import mcp_settings
        print(mcp_settings.BYPASS_VIEWSET_AUTHENTICATION)

    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.

    Note:
    This is an internal class that is only compatible with settings namespaced
    under the DJANGORESTFRAMEWORK_MCP name. It is not intended to be used by 3rd-party
    apps, and test helpers like `override_settings` may not work as expected.
    """

    def __init__(self, user_settings=None, defaults=None):
        if user_settings:
            self._user_settings = user_settings
        self.defaults = defaults or DEFAULTS
        self._cached_attrs = set()

    @property
    def user_settings(self):
        if not hasattr(self, "_user_settings"):
            self._user_settings = getattr(settings, "DJANGORESTFRAMEWORK_MCP", {})
        return self._user_settings

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError(f"Invalid MCP setting: '{attr}'")

        try:
            # Check if present in user settings
            val = self.user_settings[attr]
        except KeyError:
            # Fall back to defaults
            val = self.defaults[attr]

        # Cache the result
        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    def reload(self):
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, "_user_settings"):
            delattr(self, "_user_settings")


mcp_settings = MCPSettings(None, DEFAULTS)


def reload_mcp_settings(*args, **kwargs):
    setting = kwargs["setting"]
    if setting == "DJANGORESTFRAMEWORK_MCP":
        mcp_settings.reload()


setting_changed.connect(reload_mcp_settings)
