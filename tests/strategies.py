# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://opensource.org/licenses/isc>

"""
"""

from typing import List, Union, Optional

from lark import Tree, Token
from hypothesis.strategies import (
    SearchStrategy,
    none,
    text,
    lists,
    one_of,
    integers,
    composite,
    from_regex,
    sampled_from,
)

from semsel.parser import SemselParser
from semsel.version import BUILD_PATTERN, PRERELEASE_PATTERN, PartialVersion
from semsel.selector import (
    VersionRange,
    VersionSelector,
    VersionCondition,
    ConditionOperator,
)

PARSER = SemselParser()


@composite
def pythonic_name(draw, name_strategy: Optional[SearchStrategy[str]] = None) -> str:
    """Composite strategy for building a Python valid variable / class name."""

    return draw(
        from_regex(r"\A[a-zA-Z]+[a-zA-Z0-9\_]*\Z")
        if not name_strategy
        else name_strategy
    )


@composite
def lark_token(
    draw,
    type_strategy: Optional[SearchStrategy[str]] = None,
    value_strategy: Optional[SearchStrategy[str]] = None,
) -> Token:
    """Composite strategy for building a :class:`lark.Token`."""

    return Token(
        type_=draw(pythonic_name() if not type_strategy else type_strategy),
        value=draw(text() if not value_strategy else value_strategy),
    )


@composite
def lark_tree(
    draw,
    data_strategy: Optional[SearchStrategy[str]] = None,
    children_strategy: Optional[SearchStrategy[List[Token]]] = None,
) -> Tree:
    """Composite strategy for building a :class:`lark.Tree`."""

    return Tree(
        draw(pythonic_name() if not data_strategy else data_strategy),
        draw(
            lists(lark_token(), min_size=1)
            if not children_strategy
            else children_strategy
        ),
    )


@composite
def condition_operator(
    draw, condition_strategy: Optional[SearchStrategy[ConditionOperator]] = None
) -> ConditionOperator:
    """Composite strategy for seleting a :class:`semsel.selector.ConditionOperator`."""

    return draw(
        sampled_from(ConditionOperator)
        if not condition_strategy
        else condition_strategy
    )


@composite
def partial_version(
    draw,
    major_strategy: Optional[SearchStrategy[int]] = None,
    minor_strategy: Optional[SearchStrategy[int]] = None,
    patch_strategy: Optional[SearchStrategy[int]] = None,
    prerelease_strategy: Optional[SearchStrategy[str]] = None,
    build_strategy: Optional[SearchStrategy[str]] = None,
) -> PartialVersion:
    """Composite strategy for building a :class:`semsel.version.PartialVersion`."""

    major = draw(integers(min_value=0) if not major_strategy else major_strategy)
    minor = draw(
        one_of(integers(min_value=0), none()) if not minor_strategy else minor_strategy
    )
    patch = None
    if minor is not None:
        patch = draw(
            one_of(integers(min_value=0), none())
            if not patch_strategy
            else patch_strategy
        )
    prerelease = None
    if patch is not None:
        prerelease = draw(
            one_of(from_regex(r"\A" + PRERELEASE_PATTERN + r"\Z"), none())
            if not prerelease_strategy
            else prerelease_strategy
        )
    build = None
    if patch is not None:
        build = draw(
            one_of(from_regex(r"\A" + BUILD_PATTERN + r"\Z"), none())
            if not build_strategy
            else build_strategy
        )
    return PartialVersion(
        major=major, minor=minor, patch=patch, prerelease=prerelease, build=build
    )


@composite
def lark_version_tree(draw, *args, **kwargs) -> Tree:
    """Composite strategy for building a :class:`lark.Tree` for a parital version"""

    selector = SemselParser().tokenize(str(draw(partial_version(*args, **kwargs))))
    version_clause = selector.children[0]
    version_condition = version_clause.children[0]
    version = version_condition.children[0]
    return version


@composite
def version_condition(
    draw,
    operator_strategy: Optional[SearchStrategy[ConditionOperator]] = None,
    version_strategy: Optional[SearchStrategy[PartialVersion]] = None,
) -> VersionCondition:
    """Composite strategy for buliding a :class:`semsel.selector.VersionCondition`."""

    operator = draw(
        condition_operator() if not operator_strategy else operator_strategy
    )
    version = (
        draw(partial_version(minor_strategy=integers(min_value=0)))
        if operator == ConditionOperator.MINOR
        else draw(partial_version() if not version_strategy else version_strategy)
    )

    return VersionCondition(operator=operator, version=version)


@composite
def version_range(
    draw,
    start_version_strategy: Optional[SearchStrategy[PartialVersion]] = None,
    end_version_strategy: Optional[SearchStrategy[PartialVersion]] = None,
) -> VersionRange:
    """Composite strategy for building a :class:`semsel.selector.VersionRange`."""

    start_version = draw(
        partial_version() if not start_version_strategy else start_version_strategy
    )

    # TODO: this needs to be updated so that we are fully generating a valid end version
    # without assuming that incrementing the major version is always valid
    return VersionRange(
        version_start=start_version,
        version_end=draw(
            partial_version(major_strategy=integers(min_value=start_version.major + 1))
            if not end_version_strategy
            else end_version_strategy
        ),
    )


@composite
def version_selector_clause(
    draw,
    selector_clause_strategy: Optional[
        SearchStrategy[List[Union[VersionCondition, VersionRange]]]
    ] = None,
) -> List[Union[VersionCondition, VersionRange]]:
    """Composite strategy for building a version selector clause."""

    return draw(
        lists(one_of(version_condition(), version_range()), min_size=1, max_size=3)
        if not selector_clause_strategy
        else selector_clause_strategy
    )


@composite
def version_selector(
    draw,
    selector_clause_strategy: Optional[
        SearchStrategy[List[List[Union[VersionCondition, VersionRange]]]]
    ] = None,
) -> VersionSelector:
    """Composite selector for buliding a :class:`semsel.selector.VersionSelector`."""

    return VersionSelector(
        clauses=draw(
            lists(version_selector_clause(), min_size=1, max_size=3)
            if not selector_clause_strategy
            else selector_clause_strategy
        ),
        validate=False,
    )
