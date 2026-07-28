"""Root test configuration: hypothesis profiles.

The default profile keeps plain ``pytest`` fast; CI exports
``HYPOTHESIS_PROFILE=ci`` for deeper example generation.
"""

from __future__ import annotations

import os

from hypothesis import settings

settings.register_profile("fast", max_examples=25)
settings.register_profile("ci", max_examples=200)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "fast"))
