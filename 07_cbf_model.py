"""Compatibility wrapper for the migrated content-based recommender.

New application code must import ``ml.core.cbf_model`` directly.
"""

from ml.core.cbf_model import *  # noqa: F401,F403


if __name__ == "__main__":
    import runpy

    runpy.run_module("ml.core.cbf_model", run_name="__main__")
