# Copyright 2021 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).
from __future__ import annotations

from dataclasses import dataclass

from pants.backend.python.lint.pyupgrade.skip_field import SkipPyUpgradeField
from pants.backend.python.lint.pyupgrade.subsystem import PyUpgrade
from pants.backend.python.target_types import PythonSourceField
from pants.backend.python.util_rules import pex
from pants.backend.python.util_rules.pex import PexRequest, VenvPex, VenvPexProcess
from pants.core.goals.fmt import FmtRequest, FmtResult
from pants.engine.fs import Digest
from pants.engine.internals.native_engine import Snapshot
from pants.engine.process import FallibleProcessResult, Process
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.target import FieldSet, Target
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel
from pants.util.strutil import pluralize


@dataclass(frozen=True)
class PyUpgradeFieldSet(FieldSet):
    required_fields = (PythonSourceField,)

    source: PythonSourceField

    @classmethod
    def opt_out(cls, tgt: Target) -> bool:
        return tgt.get(SkipPyUpgradeField).value


class PyUpgradeRequest(FmtRequest):
    field_set_type = PyUpgradeFieldSet
    name = PyUpgrade.options_scope


@rule(level=LogLevel.DEBUG)
async def setup_pyupgrade_process(request: PyUpgradeRequest, pyupgrade: PyUpgrade) -> Process:
    pyupgrade_pex = await Get(VenvPex, PexRequest, pyupgrade.to_pex_request())

    process = await Get(
        Process,
        VenvPexProcess(
            pyupgrade_pex,
            argv=(*pyupgrade.args, *request.snapshot.files),
            input_digest=request.snapshot.digest,
            output_files=request.snapshot.files,
            description=f"Run pyupgrade on {pluralize(len(request.field_sets), 'file')}.",
            level=LogLevel.DEBUG,
        ),
    )

    return process


@rule(desc="Format with pyupgrade", level=LogLevel.DEBUG)
async def pyupgrade_fmt(request: PyUpgradeRequest, pyupgrade: PyUpgrade) -> FmtResult:
    if pyupgrade.skip:
        return FmtResult.skip(formatter_name=request.name)
    result = await Get(FallibleProcessResult, PyUpgradeRequest, request)
    output_snapshot = await Get(Snapshot, Digest, result.output_digest)
    return FmtResult.create(request, result, output_snapshot)


def rules():
    return [
        *collect_rules(),
        UnionRule(FmtRequest, PyUpgradeRequest),
        *pex.rules(),
    ]
