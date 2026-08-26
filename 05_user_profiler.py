"""Compatibility wrapper for the migrated user-profile module.

New application code must import ``ml.core.user_profiler`` directly.
"""

from ml.core.user_profiler import *  # noqa: F401,F403


if __name__ == "__main__":
    import runpy

    runpy.run_module("ml.core.user_profiler", run_name="__main__")
