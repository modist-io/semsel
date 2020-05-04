# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains version selector and comparator types and logic."""

from enum import Enum
from typing import List, Tuple, Union, Generator
from itertools import combinations

import attr

from .version import PartialVersion


class ConditionOperator(Enum):
    """Enumeration of applicable version constraint flags for a single version."""

    EQ = "="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    MAJOR = "^"
    MINOR = "~"


@attr.s(cmp=False)
class VersionCondition:
    """Describes a constrained version statement for a single version.

    Typically these versions are prefixed with a :class:`~ConditionOperator` value
    before a :class:`~.version.PartialVersion` string. This typically looks like
    ``>1.2.3`` or ``~1.2``.

    .. note:: Although this is an :mod:`attr` class, we are purposefully disabling the
        provided comparison functionality as it can confuse users to use this class
        for equality or ordering checks. For all checks against equality you should
        instead be using the :class:`~.version.PartialVersion` instances.

        This class is simply used for structuring and provided an interface for version
        matching. Please don't compare two instances of this class to eachother.
        Instead, please use the provided :meth:`~VersionCondition.match` method.
    """

    operator: ConditionOperator = attr.ib()
    version: PartialVersion = attr.ib()

    def __str__(self) -> str:
        """Produce a human readable string to describe this version condition.

        :return: A human readable string
        :rtype: str
        """

        return f"{self.operator.value!s}{self.version!s}"

    def match(self, other: Union["VersionCondition", "VersionRange"]) -> bool:
        """Match a given version condition against another condition or range.

        :param Union[VersionCondition, VersionRange] other: Another condition or range
            to use for matching against this condition
        :return: True if the current condition does not conflict with the given
            condition or range
        :rtype: bool
        """

        # NOTE: because MAJOR and MINOR comparisions are not applied in the same
        # way that traditional order or equality based comparaisons are applied,
        # we need to ensure that if either the source or target versions for the
        # match checks are MAJOR or MINOR constrained, we are applying the proper
        # version constraint checks
        if self.operator == ConditionOperator.MAJOR:
            return self.version.__major__(other.version)
        elif self.operator == ConditionOperator.MINOR:
            return self.version.__minor__(other.version)
        elif other.operator == ConditionOperator.MAJOR:
            return other.version.__major__(self.version)
        elif other.operator == ConditionOperator.MINOR:
            return other.version.__minor__(self.version)

        # TODO: I'm not a huge fan of this kind of structure checking
        # maybe this should be cleaned up
        standard_possibilities = {
            ConditionOperator.EQ: (0,),
            ConditionOperator.GT: (1,),
            ConditionOperator.GE: (0, 1,),
            ConditionOperator.LT: (-1,),
            ConditionOperator.LE: (-1, 0,),
        }

        if self.operator in standard_possibilities:
            return (
                self.version.compare(other.version)
                in standard_possibilities[other.operator]
            )
        else:
            return False


@attr.s(cmp=False)
class VersionRange:

    version_start: PartialVersion = attr.ib()
    version_end: PartialVersion = attr.ib()

    def __attrs_post_init__(self):
        if self.version_end <= self.version_start:
            raise ValueError(
                f"ending version {self.version_end!s} is less or equal to the "
                f"starting version {self.version_start!s}"
            )

    def __str__(self) -> str:
        return f"{self.version_start!s} - {self.version_end!s} "

    def match(self, other: Union["VersionCondition", "VersionRange"]) -> bool:
        return other.version >= self.version_start and other.version <= self.version_end


@attr.s
class VersionSelector:
    clauses: List[List[Union[VersionCondition, VersionRange]]] = attr.ib()

    def __attrs_post_init__(self):
        for clause in self.clauses:
            for source, target in combinations(clause, 2):
                if not source.match(target):
                    raise ValueError(
                        f"expression {source!s} conflicts with expression {target!s}"
                    )

    def __str__(self) -> str:
        return " || ".join(
            [
                " ".join([str(expression) for expression in clause])
                for clause in self.clauses
            ]
        )
