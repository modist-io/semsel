# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains custom exceptions and errors."""


class SemselException(Exception):
    """Module-wide exception namespace."""

    pass


class ParseFailure(SemselException):
    """Raised during BNF-grammer parsing / transformation failures."""

    pass
