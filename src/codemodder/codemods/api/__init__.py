import io
import os
import tempfile

import libcst as cst
from libcst.codemod import (
    CodemodContext,
)
import yaml

from codemodder.codemods.base_codemod import (
    CodemodMetadata,
    BaseCodemod as _BaseCodemod,
    SemgrepCodemod as _SemgrepCodemod,
)

from codemodder.codemods.base_visitor import BaseTransformer
from codemodder.codemods.change import Change
from codemodder.file_context import FileContext
from codemodder.semgrep import rule_ids_from_yaml_files
from .helpers import Helpers


def _populate_yaml(rule: str, metadata: CodemodMetadata) -> str:
    config = yaml.safe_load(io.StringIO(rule))
    # TODO: handle more than rule per config?
    assert len(config["rules"]) == 1
    config["rules"][0].setdefault("id", metadata.NAME)
    config["rules"][0].setdefault("message", "Semgrep found a match")
    config["rules"][0].setdefault("severity", "WARNING")
    config["rules"][0].setdefault("languages", ["python"])
    return yaml.safe_dump(config)


def _create_temp_yaml_file(orig_cls, metadata: CodemodMetadata):
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as ff:
        ff.write(_populate_yaml(orig_cls.rule(), metadata))

    return [path]


class _CodemodSubclassWithMetadata:
    def __init_subclass__(cls):
        # This is a pretty yucky workaround.
        # But it is necessary to get around the fact that these fields are
        # checked by __init_subclass__ of the other parents of SemgrepCodemod
        # first.
        if cls.__name__ not in ("BaseCodemod", "SemgrepCodemod"):
            # TODO: if we intend to continue to check class-level attributes
            # using this mechanism, we should add checks (or defaults) for
            # NAME, DESCRIPTION, and REVIEW_GUIDANCE here.

            cls.METADATA = CodemodMetadata(
                cls.DESCRIPTION,  # pylint: disable=no-member
                cls.NAME,  # pylint: disable=no-member
                cls.REVIEW_GUIDANCE,  # pylint: disable=no-member
            )

            # This is a little bit hacky, but it also feels like the right solution?
            cls.CHANGE_DESCRIPTION = cls.DESCRIPTION  # pylint: disable=no-member

        return cls


class BaseCodemod(
    _CodemodSubclassWithMetadata,
    _BaseCodemod,
    BaseTransformer,
    Helpers,
):
    CHANGESET_ALL_FILES: list = []

    def report_change(self, original_node):
        line_number = self.lineno_for_node(original_node)
        self.file_context.codemod_changes.append(
            Change(str(line_number), self.CHANGE_DESCRIPTION).to_json()
        )


# NOTE: this shadows base_codemod.SemgrepCodemod but I can't think of a better name right now
# At least it is namespaced but we might want to deconflict these things in the long term
class SemgrepCodemod(
    BaseCodemod,
    _CodemodSubclassWithMetadata,
    _SemgrepCodemod,
    BaseTransformer,
):
    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.YAML_FILES = _create_temp_yaml_file(cls, cls.METADATA)
        cls.RULE_IDS = rule_ids_from_yaml_files(cls.YAML_FILES)

    def __init__(self, codemod_context: CodemodContext, file_context: FileContext):
        _SemgrepCodemod.__init__(self, file_context)
        BaseTransformer.__init__(
            self,
            codemod_context,
            self._results,
            file_context.line_exclude,
            file_context.line_include,
        )

    # TODO: there needs to be a way to generalize this so that it applies
    # more broadly than to just a specific kind of node. There's probably a
    # decent way to do this with metaprogramming. We could either apply it
    # broadly to every known method (which would probably have a big
    # performance impact). Or we could allow users to register the handler
    # for a specific node or nodes by means of a decorator or something
    # similar when they define their `on_result_found` method.
    # Right now this is just to demonstrate a particular use case.
    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call):
        pos_to_match = self.node_position(original_node)
        if self.filter_by_result(
            pos_to_match
        ) and self.filter_by_path_includes_or_excludes(pos_to_match):
            self.report_change(original_node)
            if (attr := getattr(self, "on_result_found", None)) is not None:
                # pylint: disable=not-callable
                new_node = attr(original_node, updated_node)
                return new_node

        return updated_node

    def leave_Assign(self, original_node, updated_node):
        pos_to_match = self.node_position(original_node)
        if self.filter_by_result(
            pos_to_match
        ) and self.filter_by_path_includes_or_excludes(pos_to_match):
            self.report_change(original_node)
            if (attr := getattr(self, "on_result_found", None)) is not None:
                # pylint: disable=not-callable
                new_node = attr(original_node, updated_node)
                return new_node

        return updated_node