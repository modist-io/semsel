# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""
"""

import re
from typing import Any, Dict, List, Type, Tuple, Union, Optional

import attr

from .utils import cmp

MAJOR_PATTERN = r"(?P<major>0|[1-9][0-9]*)"
MINOR_PATTERN = r"(?P<minor>0|[1-9][0-9]*)"
PATCH_PATTERN = r"(?P<patch>0|[1-9][0-9]*)"
PRERELEASE_PATTERN = (
    r"(?P<prerelease>(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*)"
)
BUILD_PATTERN = r"(?P<build>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)"

PARTIAL_VERSION_PATTERN = (
    MAJOR_PATTERN
    + r"(?:\."
    + MINOR_PATTERN
    + r"(?:\."
    + PATCH_PATTERN
    + r"(?:-"
    + PRERELEASE_PATTERN
    + r")?(?:\+"
    + BUILD_PATTERN
    + r")?)?)?"
)

VersionTuple_T = Tuple[int, int, int, Optional[str], Optional[str]]
VersionDict_T = Dict[str, Union[int, Optional[str]]]


@attr.s(eq=False, order=False)
class PartialVersion:

    major: int = attr.ib()
    minor: int = attr.ib(default=None)
    patch: int = attr.ib(default=None)
    prerelease: Optional[str] = attr.ib(default=None)
    build: Optional[str] = attr.ib(default=None)

    _pattern = re.compile(PARTIAL_VERSION_PATTERN)

    def __str__(self) -> str:
        version = str(self.major)
        if self.minor is not None:
            version += f".{self.minor!s}"
        if self.patch is not None:
            version += f".{self.patch!s}"
        if self.prerelease is not None:
            version += f"-{self.prerelease!s}"
        if self.build is not None:
            version += f"+{self.build!s}"

        return version

    def __eq__(self, other: Any) -> bool:
        return self.compare(other) == 0

    def __ne__(self, other: Any) -> bool:
        return self.compare(other) != 0

    def __lt__(self, other: "PartialVersion") -> bool:
        return self.compare(other) < 0

    def __le__(self, other: "PartialVersion") -> bool:
        return self.compare(other) <= 0

    def __gt__(self, other: "PartialVersion") -> bool:
        return self.compare(other) > 0

    def __ge__(self, other: "PartialVersion") -> bool:
        return self.compare(other) >= 0

    def __major__(self, other: "PartialVersion") -> bool:
        return other.major == self.major

    def __minor__(self, other: "PartialVersion") -> bool:
        return other.major == self.major and (other.minor or 0) <= (self.minor or 0)

    @staticmethod
    def prerelease_compare(source: Optional[str], target: Optional[str]) -> int:
        def cast_fragment(fragment_value: str) -> Union[int, str]:
            return (
                int(fragment_value)
                if re.match(r"^[0-9]+$", fragment_value)
                else fragment_value
            )

        def get_fragments(value: str) -> List[Union[int, str]]:
            return [cast_fragment(fragment) for fragment in value.split(".")]

        def compare_part(
            source: Optional[Union[int, str]], target: Optional[Union[int, str]]
        ) -> int:
            if isinstance(source, int) and isinstance(target, int):
                return cmp(source, target)
            elif isinstance(source, int):
                return -1
            elif isinstance(target, int):
                return 1
            else:
                return cmp(source, target)

        source, target = source or "", target or ""
        source_fragments, target_fragments = (
            get_fragments(source),
            get_fragments(target),
        )
        for source_part, target_part in zip(source_fragments, target_fragments):
            part_comparision = compare_part(source_part, target_part)
            if part_comparision != 0:
                return part_comparision
        else:
            return cmp(len(source), len(target))

    @classmethod
    def from_dict(cls, version_dict: VersionDict_T) -> "PartialVersion":
        return cls(**version_dict)  # type: ignore

    @classmethod
    def from_string(cls, version: str) -> "PartialVersion":
        match = cls._pattern.fullmatch(version)
        if not match:
            raise ValueError(f"{version!r} is not a valid partial semantic version")

        return cls.from_dict(
            {
                key: (
                    int(value)
                    if value and key in ("major", "minor", "patch",)
                    else value
                )
                for key, value in match.groupdict().items()
            }
        )

    @classmethod
    def from_tuple(cls, version_tuple: VersionTuple_T) -> "PartialVersion":
        major, minor, patch = version_tuple[:3]

        # TODO: refactor these magic numbers out
        prerelease = None
        if len(version_tuple) > 3:
            prerelease = version_tuple[3]

        build = None
        if len(version_tuple) > 4:
            build = version_tuple[4]

        return cls(
            major=major, minor=minor, patch=patch, prerelease=prerelease, build=build
        )

    def compare(
        self, version: Union[str, VersionDict_T, VersionTuple_T, "PartialVersion"]
    ) -> int:
        other: "PartialVersion"
        cls: Type["PartialVersion"] = type(self)
        if isinstance(version, str):
            other = cls.from_string(version)
        elif isinstance(version, dict):
            other = cls.from_dict(version)
        elif isinstance(version, (tuple, list,)):
            other = cls.from_tuple(version)

        if not isinstance(version, cls):
            raise TypeError(
                f"Expected str or {cls.__name__!s} instance, but got {type(version)!s}"
            )
        else:
            other = version

        source = self.to_tuple()[:3]
        target = other.to_tuple()[:3]

        comparision = cmp(source, target)
        if comparision:
            return comparision

        source_prerelease, target_prerelease = self.prerelease, other.prerelease
        prerelease_comparison = PartialVersion.prerelease_compare(
            source_prerelease, target_prerelease
        )

        if not prerelease_comparison:
            return 0
        if not source_prerelease:
            return 1
        if not target_prerelease:
            return -1

        return prerelease_comparison

    def to_tuple(self) -> VersionTuple_T:
        return (
            self.major,
            self.minor or 0,
            self.patch or 0,
            self.prerelease,
            self.build,
        )

    def to_dict(self) -> VersionDict_T:
        return attr.asdict(self)

    def to_semver(self) -> str:
        semver = f"{self.major!s}.{self.minor or 0!s}.{self.patch or 0!s}"
        if self.prerelease:
            semver += f"-{self.prerelease!s}"
        if self.build:
            semver += f"+{self.build!s}"
        return semver
