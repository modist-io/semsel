# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""
"""

import pytest
from hypothesis import given
from hypothesis.strategies import none, integers, sampled_from

from semsel.version import PartialVersion
from semsel.selector import VersionCondition, ConditionOperator
from semsel.exceptions import InvalidExpression

from .strategies import partial_version, version_condition


@given(partial_version(minor_strategy=none()))
def test_fails_creating_VersionCondition_with_minor_operator_and_no_minor_version(
    version: PartialVersion,
):
    """
    Ensures initializing a ``VersionCondition`` instance with a
    ``ConditionOperator.MINOR`` operator will raise an ``InvalidExpression`` exception
    if the provided ``PartialVersion`` does not explicitly declare a
    minor version number.
    """

    with pytest.raises(InvalidExpression) as exc:
        VersionCondition(operator=ConditionOperator.MINOR, version=version)

    assert "must include an explicit minor version" in str(exc.value)


@given(
    version_condition(
        operator_strategy=sampled_from(
            [_ for _ in ConditionOperator if _ != ConditionOperator.MINOR]
        ),
        version_strategy=partial_version(minor_strategy=integers(min_value=0)),
    ),
    version_condition(),
)
def test_fails_match_minor_if_VersionCondition_not_using_minor_operator(
    condition: VersionCondition, other: VersionCondition
):
    """
    Ensures calling minor matching will fail if the current ``VersionCondition`` is not
    using a ``ConditionOperator.MINOR`` condition.
    """

    with pytest.raises(ValueError) as exc:
        condition._match_minor(other)

    assert "not constrained by a minor operator" in str(exc.value)
