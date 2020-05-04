# -*- encoding: utf-8 -*-
# Copyright (c) 2020 Modist Team <admin@modist.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains module initialization logic."""


from . import __version__  # type: ignore
from .parser import SemselParser

__all__ = ["SemselParser"]
