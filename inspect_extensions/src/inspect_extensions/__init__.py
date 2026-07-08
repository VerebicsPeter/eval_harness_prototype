# This module is the target of the `inspect_ai` setuptools entry point.
# Inspect imports it during discovery, and importing the sandbox module here
# runs the @sandboxenv decorator, which registers "microsandbox" with the
# sandbox registry.
from inspect_extensions.sandboxes.sb_microsandbox import MicrosandboxSandboxEnvironment

__all__ = [
    "MicrosandboxSandboxEnvironment"
]