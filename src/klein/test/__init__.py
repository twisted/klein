# -*- test-case-name: klein.test -*-
# Copyright (c) 2017-2018. See LICENSE for details.

"""
Tests for L{klein}.
"""

from hypothesis import HealthCheck, settings

settings.register_profile(
    "patience", settings(suppress_health_check=[HealthCheck.too_slow])
)
settings.load_profile("patience")
