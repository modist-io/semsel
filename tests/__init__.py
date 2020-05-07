# -*- encoding: utf-8 -*-
# Copyright (c) 2020 Modist Team <admin@modist.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains unit tests for the module."""

import os

from hypothesis import HealthCheck, settings

settings.register_profile("default", max_examples=10)
settings.register_profile(
    "ci", suppress_health_check=[HealthCheck.too_slow], max_examples=30, deadline=None
)

settings.load_profile("default")
if os.environ.get("CI", None) == "true":
    settings.load_profile("ci")
