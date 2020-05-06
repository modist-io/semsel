# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains module-wide utility functions."""

from typing import Any


def cmp(source: Any, target: Any) -> int:
    """Traditional comparison method against two evaulable inputs.

    :param Any source: The source input
    :param Any target: The target input
    :return: -1 if source < target, 0 if source = target, 1 if source > target
    :rtype: int
    """

    return (source > target) - (source < target)
