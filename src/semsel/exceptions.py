# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains custom exceptions and errors."""

from typing import Optional


class SemselException(Exception):
    """Module-wide exception namespace."""

    def __init__(self, message: str):
        """Initialize the exception instance.

        :param str message: The user-intended exception message
        """

        super().__init__(message)
        self.message = message


class ParseFailure(SemselException):
    """Raised during BNF-grammer parsing / transformation failures."""

    pass


class InvalidExpression(SemselException):
    """Raised when evaluation of an expression is shown to have conflicts."""

    pass
