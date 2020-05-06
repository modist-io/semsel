# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains version selector and comparator types and logic."""

from enum import Enum
from typing import List, Tuple, Union, Generator
from warnings import warn
from itertools import combinations

import attr

from .utils import cmp
from .version import PartialVersion
from .exceptions import InvalidExpression


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

    __condition_comparisons = {
        ConditionOperator.EQ: (0,),
        ConditionOperator.GT: (1,),
        ConditionOperator.GE: (0, 1,),
        ConditionOperator.LT: (-1,),
        ConditionOperator.LE: (-1, 0,),
    }
    __range_comparisons = {
        ConditionOperator.EQ: ((0, 1), (-1, 0)),
        ConditionOperator.GT: ((-1, 0, 1), (-1,)),
        ConditionOperator.GE: ((-1, 0, 1), (-1, 0)),
        ConditionOperator.LT: ((1,), (-1, 0, 1)),
        ConditionOperator.LE: ((0, 1), (-1, 0, 1)),
    }

    def __attrs_post_init__(self):
        """Handle basic validation after class initialization.

        :raises InvalidExpression: When a minor constrained version does not include an
            explicit minor version
        """

        if self.operator == ConditionOperator.MINOR and self.version.minor is None:
            raise InvalidExpression(
                f"Condition version {self!s} with minor constraint "
                f"({ConditionOperator.MINOR.value!s}) must include an explicit "
                "minor version"
            )

    def __str__(self) -> str:
        """Produce a human readable string to describe this version condition.

        :return: A human readable string
        :rtype: str
        """

        return f"{self.operator.value!s}{self.version!s}"

    def _match_minor(self, version_condition: "VersionCondition") -> bool:
        """Match a given version condition agains the minor constrained version.

        :param VersionCondition version_condition: The version condition to match
            against the current minor constrained version
        :raises ValueError: If the current condition's operator is not set to
            :cvar:`~ConditionOperator.MINOR`
        :return: True if the current minor constrained condition does not conflict with
            the given condition
        :rtype: bool
        """

        if self.operator != ConditionOperator.MINOR:
            raise ValueError(
                f"Condition {self!s} is not constrained by a minor operator, "
                f"condition operator is {self.operator!s}"
            )

        if version_condition.operator == ConditionOperator.MAJOR:
            # Major comparisons only care about if major conditions are satisfied
            # between the minor constraint. Since a minor constraint implies a major
            # constraint we need to just be sure that a comparison against a major
            # constrained version is using the exact same major version
            # An example of this condition can be seen in the example `~1.2 ^1`
            return self.version.__major__(version_condition.version)
        elif version_condition.operator == ConditionOperator.MINOR:
            # Minor comparisons depend on both the implicit major constraint as well as
            # the explicit minor constraint. These both must be exactly equal to
            # eachother for the conditions to not be in conflict with eachother
            # An example of this condition can be seen in the example `~1.2 ~1.5`
            return self.version.__minor__(version_condition.version)
        elif self.version.major == version_condition.version.major:
            # When comparing two conditions using the same major version, we really only
            # care about the minor comparisons satisfying the normal condition
            # comparisons against the target's minor version. Note that since these are
            # partial versions, the given condition's minor version may not exist such
            # as in the example `~1.2 <1`.

            # NOTE: There should never be an instance where the current condition's
            # minor version does not exist as we are ensuring we are always comparing a
            # MINOR constrained version which has validation against this in the
            # condition class initialization
            return (
                cmp(self.version.minor, version_condition.version.minor or 0)
                in self.__condition_comparisons[version_condition.operator]
            )
        else:
            # When comparing two conditions using different major veresions, we should
            # just be checking the full version against the normal condition comparisons
            # since we can't verify that all version fragments are valid if our major
            # versions are not the same. Such an example of this comparison can be seen
            # in the example `~1 <4.2`.
            return (
                self.version.compare(version_condition.version)
                in self.__condition_comparisons[version_condition.operator]
            )

    def _match_major(self, version_condition: "VersionCondition") -> bool:
        """Match a given version condition against the major constrained version.

        :param VersionCondition version_condition: The version condition to match
            against the current major constrainted version
        :raises ValueError: If the current condition's operator is not set to
            :cvar:`~ConditionOperator.MAJOR`
        :return: True if the current major constrained condition does not conflict with
            the given condition
        :rtype: bool
        """

        if self.operator != ConditionOperator.MAJOR:
            raise ValueError(
                f"Condition {self!s} is not constrained by a major operator, "
                f"condition operator is {self.operator!r}"
            )

        if version_condition.operator in (
            ConditionOperator.MAJOR,
            ConditionOperator.MINOR,
        ):
            # Major comparisons only really care about if the major conditions are
            # satisfied between conditions when either dealing with major or minor
            # conditions. For example in `^1 ~1.2`, the `^1` condition really only cares
            # if the `~1.2` condition is using the same major version
            return self.version.major == version_condition.version.major
        else:
            # Doing normal comparisons (not MAJOR / MINOR) against a MAJOR condition
            # really only cares about the normal condition comparison against the
            # target's major version. We also must always allow for the major version
            # to match exactly which is why we must extend any comparison result set
            # with the (0,) tuple. Such an example of why this extended result is
            # necessary can be seen in the example `^1.2 >1`.
            return cmp(
                self.version.major, version_condition.version.major
            ) in self.__condition_comparisons[version_condition.operator] + (0,)

    def _match_condition(self, version_condition: "VersionCondition") -> bool:
        """Match the current version condition against another condition.

        :param VersionCondition version_condition: Another version condition to match
            against this condition
        :return: True if the current condition does not conflict with the given
            version condition
        :rtype: bool
        """

        # NOTE: We must handle MAJOR / MINOR comparisons separately from the normal
        # equality and ordering operators provided by the partial version instance.
        # Since major and minor comparisons require context into if the compared version
        # is major or minor, these two types of matches must be handled separately

        # TODO: or until I find a better way to make this work with PartialVersion
        if self.operator == ConditionOperator.MAJOR:
            return self._match_major(version_condition)
        elif self.operator == ConditionOperator.MINOR:
            return self._match_minor(version_condition)

        if self.operator not in self.__condition_comparisons:
            warn(
                f"Operator {self.operator!r} cannot be applied for condition "
                f"{version_condition!r}, from {self!r}"
            )
            return False

        return (
            self.version.compare(version_condition.version)
            in self.__condition_comparisons[self.operator]
        )

    def _match_range(self, version_range: "VersionRange") -> bool:
        """Match a the current version condition against a given version range.

        :param VersionRange version_range: A version range instance to match against
            this condition
        :return: True if the current condition does not conflict with the given
            version range
        :rtype: bool
        """

        if self.operator == ConditionOperator.MAJOR:
            # For major range comparisons we only really care that the starting and
            # ending versions fall within the appropriate major version
            # An example of this condition can be seen in the example `1 - 3.2 ^2`
            return self.version.__major__(
                version_range.version_start
            ) or self.version.__major__(version_range.version_end)
        elif self.operator == ConditionOperator.MINOR:
            # For minor range comparisons we care that the starting and ending versions
            # fall within the appropriate minor version
            # An example of this condition can be seen in the example `1.2 - 1.6 ~1.3`
            return self.version.__minor__(
                version_range.version_start
            ) or self.version.__minor__(version_range.version_end)

        if self.operator not in self.__range_comparisons:
            warn(
                f"Operator {self.operator!r} cannot be applied for range "
                f"{version_range!r}, from {self!r}"
            )
            return False

        start_possibilities, end_possibilities = self.__range_comparisons[self.operator]
        return (
            self.version.compare(version_range.version_start) in start_possibilities
            and self.version.compare(version_range.version_end) in end_possibilities
        )

    def match(self, other: Union["VersionCondition", "VersionRange"]) -> bool:
        """Match a given version condition against another condition or range.

        :param Union[VersionCondition, VersionRange] other: Another condition or range
            to use for matching against this condition
        :return: True if the current condition does not conflict with the given
            condition or range
        :rtype: bool
        """

        return (
            self._match_range(other)
            if isinstance(other, VersionRange)
            else self._match_condition(other)
        )


@attr.s(cmp=False)
class VersionRange:
    """Describes a version set constrained by a range of versions.

    These versions are delimited by a hypen with whitespace on boths sides like
    ``1.0.0 - 1.2.0``. This range would constrain any possible versions greater than
    or equal to ``1.0.0`` and less than or equal to ``1.2.0``.

    .. note:: Similar to the above :class:`~VersionRange` class, this is an attr's class
        that has had comparison and order magic methods removed as these instances
        should not be directly compared with eacother. Instead, use the included
        :meth:`~VersionRange.match` method for match comparaisons between conditions
        and other ranges.
    """

    version_start: PartialVersion = attr.ib()
    version_end: PartialVersion = attr.ib()

    def __attrs_post_init__(self):
        """Handle basic validation after class initialization.

        :raises InvalidExpression: If the provided ``version_end`` is less than or equal
            to the provided ``version_start``. In this case the statement would be
            equivalent and better suited as an *equals* condition rather than a range
            statement.
        """

        if self.version_end <= self.version_start:
            raise InvalidExpression(
                f"Ending version {self.version_end!s} is less or equal to the "
                f"starting version {self.version_start!s} in '{self!s}'"
            )

    def __str__(self) -> str:
        """Produce a human readable string to describe this version range.

        :return: A human readable string
        :rtype: str
        """

        return f"{self.version_start!s} - {self.version_end!s}"

    def _match_condition(self, version_condition: "VersionCondition") -> bool:
        """Match a the current version range against a given version condition.

        :param VersionCondition version_condition: A version condition instance to
            match against this range
        :return: True if the current version range does not conflict with the given
            version condition
        :rtype: bool
        """

        # NOTE: since all this logic alreay exists within the VersionCondition class we
        # just delegate to it
        return version_condition._match_range(self)

    def _match_range(self, version_range: "VersionRange") -> bool:
        """Match the current version range against a given version range.

        :param VersionRange version_range: A version range instance to match
            against the current version range
        :return: True if the current version range does not conflict with the
            given version range
        :rtype: bool
        """

        return (
            self.version_start <= version_range.version_end
            and version_range.version_start <= self.version_end
        )

    def match(self, other: Union["VersionCondition", "VersionRange"]) -> bool:
        """Match the current range against a given range or condition.

        :param Union[VersionCondition, VersionRange] other: Another range or condition
            to use for matching against this range
        :return: True if the current range does not conflict with the given condition
            or range, otherwise False
        :rtype: bool
        """

        return (
            self._match_condition(other)
            if isinstance(other, VersionCondition)
            else self._match_range(other)
        )


@attr.s
class VersionSelector:
    """Describes a group of condition / range clauses that make up a selector expression.

    The selector is a list of **AND** version range or condition clauses which are
    grouped as **OR** clauses. There are only two levels available for the clause group
    strucutre. AND clauses joined by OR clauses. For example, the selector syntax
    ``>1 <1.3 || =1.5.2`` is strucrtured as two and clauses
    (``>1 AND <1.3``, ``=1.5.2``) which are applied with an OR clause.
    So either a version greater than 1 AND less than 1.3 OR a version exactly equal to
    1.5.2 wil satisfy this selector.

    The data within this selector is structured as a list of lists containing either
    :class:`~VersionCondition` or :class:`~VersionRange` instances which are used for
    comparison and evaluation. The top-level list is the applicable OR clauses while the
    nested lists are the applicable AND clauses.
    """

    clauses: List[List[Union[VersionCondition, VersionRange]]] = attr.ib()

    def __attrs_post_init__(self):
        """Handle clause validation after class initialization.

        :raises InvalidExpression: When an clause expression is found to conflict with
            another expression in the selector statement
        """

        for clause in self.clauses:
            for source, target in combinations(clause, 2):
                if not source.match(target):
                    raise InvalidExpression(
                        f"Expression {source!s} conflicts with expression {target!s} "
                        f"in clause {self._format_clause(clause)!r}"
                    )

    def _format_clause(
        self, clause: List[Union[VersionCondition, VersionRange]]
    ) -> str:
        """Format a given clause as a human readable string.

        :param List[Union[VersionCondition, VersionRange]] clause: The list of
            conditions or ranges to format
        :return: A human readable string representation of a clause
        :rtype: str
        """

        return " ".join([str(expression) for expression in clause])

    def _format_clause_group(
        self, clause_group: List[List[Union[VersionCondition, VersionRange]]]
    ) -> str:
        """Format a given list of clauses (caluse group) as a human readable string.

        :param List[List[Union[VersionCondition, VersionRange]]] clause_group: The list
            of clauses to format
        :return: A human readable string representation of a clause group
        :rtype: str
        """

        return " || ".join([self._format_clause(clause) for clause in clause_group])

    def __str__(self) -> str:
        """Produce a human readable string to describe this version selector.

        :return: A human readable string
        :rtype: str
        """

        return self._format_clause_group(self.clauses)
