"""Compatibility wrapper for the migrated hybrid recommender.

New application code must import ``ml.core.hybrid_recommender`` directly.
"""

from ml.core.hybrid_recommender import *  # noqa: F401,F403


if __name__ == "__main__":
    import runpy

    runpy.run_module("ml.core.hybrid_recommender", run_name="__main__")
