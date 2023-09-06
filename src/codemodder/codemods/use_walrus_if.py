from typing import List, Tuple

import libcst as cst
from libcst._position import CodeRange
from libcst import matchers as m
from libcst.metadata import ParentNodeProvider, ScopeProvider

from codemodder.change import Change
from codemodder.codemods.base_codemod import ReviewGuidance
from codemodder.codemods.utils_mixin import NameResolutionMixin
from codemodder.codemods.api import SemgrepCodemod


class UseWalrusIf(SemgrepCodemod, NameResolutionMixin):
    METADATA_DEPENDENCIES = SemgrepCodemod.METADATA_DEPENDENCIES + (
        ParentNodeProvider,
        ScopeProvider,
    )
    NAME = "use-walrus-if"
    SUMMARY = (
        "Replaces multiple expressions involving `if` operator with 'walrus' operator"
    )
    REVIEW_GUIDANCE = ReviewGuidance.MERGE_AFTER_CURSORY_REVIEW
    DESCRIPTION = (
        "Replaces multiple expressions involving `if` operator with 'walrus' operator"
    )

    @classmethod
    def rule(cls):
        return """
        rules:
          - patterns:
            - pattern: |
                $ASSIGN
                if $COND:
                  $BODY
            - metavariable-pattern:
                metavariable: $ASSIGN
                patterns:
                  - pattern: $VAR = $RHS
                  - metavariable-pattern:
                      metavariable: $COND
                      patterns:
                        - pattern: $VAR
                  - metavariable-pattern:
                      metavariable: $BODY
                      pattern: $VAR
            - focus-metavariable: $ASSIGN
        """

    _modify_next_if: List[Tuple[CodeRange, cst.Assign]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._modify_next_if = []

    def add_change(self, position: CodeRange):
        self.file_context.codemod_changes.append(
            Change(
                lineNumber=position.start.line,
                description=self.CHANGE_DESCRIPTION,
            ).to_json()
        )

    def leave_If(self, original_node, updated_node):
        if self._modify_next_if:
            position, if_node = self._modify_next_if.pop()
            is_name = m.matches(updated_node.test, m.Name())
            named_expr = cst.NamedExpr(
                target=if_node.targets[0].target,
                value=if_node.value,
                lpar=[] if is_name else [cst.LeftParen()],
                rpar=[] if is_name else [cst.RightParen()],
            )
            self.add_change(position)
            return (
                updated_node.with_changes(test=named_expr)
                if is_name
                else updated_node.with_changes(
                    test=updated_node.test.with_changes(left=named_expr)
                )
            )

        return original_node

    def _is_valid_modification(self, node):
        """
        Restricts the kind of modifications we can make to the AST.

        This is necessary since the semgrep rule can't fully encode this restriction.
        """
        if parent := self.get_metadata(ParentNodeProvider, node):
            if gparent := self.get_metadata(ParentNodeProvider, parent):
                if (idx := gparent.children.index(parent)) >= 0:
                    return m.matches(
                        gparent.children[idx + 1],
                        m.If(test=(m.Name() | m.Comparison(left=m.Name()))),
                    )
        return False

    def leave_Assign(self, original_node, updated_node):
        if self.node_is_selected(original_node):
            if self._is_valid_modification(original_node):
                position = self.node_position(original_node)
                self._modify_next_if.append((position, updated_node))
                return cst.RemoveFromParent()

        return original_node