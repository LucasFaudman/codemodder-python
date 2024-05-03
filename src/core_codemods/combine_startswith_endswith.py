import libcst as cst
from libcst import matchers as m

from codemodder.codemods.utils_mixin import NameResolutionMixin
from core_codemods.api import Metadata, ReviewGuidance, SimpleCodemod


class CombineStartswithEndswith(SimpleCodemod, NameResolutionMixin):
    metadata = Metadata(
        name="combine-startswith-endswith",
        summary="Simplify Boolean Expressions Using `startswith` and `endswith`",
        review_guidance=ReviewGuidance.MERGE_WITHOUT_REVIEW,
        references=[],
    )
    change_description = "Use tuple of matches instead of boolean expression"

    args = [
        m.Arg(
            value=m.Tuple()
            | m.SimpleString()
            | m.ConcatenatedString()
            | m.FormattedString()
            | m.Name()
        )
    ]

    startswith_call_matcher = m.Call(
        func=m.Attribute(value=m.Name(), attr=m.Name("startswith")),
        args=args,
    )

    endswith_call_matcher = m.Call(
        func=m.Attribute(value=m.Name(), attr=m.Name("endswith")),
        args=args,
    )

    def leave_BooleanOperation(
        self, original_node: cst.BooleanOperation, updated_node: cst.BooleanOperation
    ) -> cst.CSTNode:
        if not self.filter_by_path_includes_or_excludes(
            self.node_position(original_node)
        ):
            return updated_node

        for call_matcher in (self.startswith_call_matcher, self.endswith_call_matcher):
            if self.matches_call_or_call(updated_node, call_matcher):
                self.report_change(original_node)
                return self.combine_calls(updated_node.left, updated_node.right)

            if self.matches_call_or_boolop(updated_node, call_matcher):
                self.report_change(original_node)
                return self.call_or_boolop_fold_right(updated_node)

            if self.matches_boolop_or_call(updated_node, call_matcher):
                self.report_change(original_node)
                return self.boolop_or_call_fold_left(updated_node)

        return updated_node

    def matches_call_or_call(
        self, node: cst.BooleanOperation, call_matcher: m.Call
    ) -> bool:
        # Check for simple case: x.startswith("...") or x.startswith("...")
        call_or_call = m.BooleanOperation(
            left=call_matcher, operator=m.Or(), right=call_matcher
        )
        return (
            m.matches(node, call_or_call)  # Same Func
            and node.left.func.value.value == node.right.func.value.value
        )  # Same Instance

    def matches_call_or_boolop(
        self, node: cst.BooleanOperation, call_matcher: m.Call
    ) -> bool:

        # Check for case when call on left and call on left of right boolop can be combined like:
        # x.startswith("...") or x.startswith("...") and/or <any>
        call_or_boolop = m.BooleanOperation(
            left=call_matcher,
            operator=m.Or(),
            right=m.BooleanOperation(left=call_matcher),
        )
        return (
            m.matches(node, call_or_boolop)  # Same Func
            and node.left.func.value.value == node.right.left.func.value.value
        )  # Same Instance

    def matches_boolop_or_call(
        self, node: cst.BooleanOperation, call_matcher: m.Call
    ) -> bool:

        # Check for case when call on right and call on right of left boolop can be combined like:
        # <any> and/or x.startswith("...") or x.startswith("...")
        boolop_or_call = m.BooleanOperation(
            left=m.BooleanOperation(right=call_matcher),
            operator=m.Or(),
            right=call_matcher,
        )
        return (
            m.matches(node, boolop_or_call)  # Same Func
            and node.left.right.func.value.value == node.right.func.value.value
        )  # Same Instance

    def combine_calls(self, *calls: cst.Call) -> cst.Call:
        elements = []
        seen_evaluated_values = set()
        for call in calls:
            arg_value = call.args[0].value
            arg_elements = (
                arg_value.elements
                if isinstance(arg_value, cst.Tuple)
                else (cst.Element(value=arg_value),)
            )

            for element in arg_elements:
                if (
                    evaluated_value := getattr(element.value, "evaluated_value", None)
                ) in seen_evaluated_values:
                    # If an element has a non-None evaluated value that has already been seen, continue to avoid duplicates
                    continue
                if evaluated_value is not None:
                    seen_evaluated_values.add(evaluated_value)
                elements.append(element)

        new_arg = cst.Arg(value=cst.Tuple(elements=elements))
        return cst.Call(func=call.func, args=[new_arg])

    def call_or_boolop_fold_right(
        self, node: cst.BooleanOperation
    ) -> cst.BooleanOperation:
        new_left = self.combine_calls(node.left, node.right.left)
        new_right = node.right.right
        return cst.BooleanOperation(
            left=new_left, operator=node.right.operator, right=new_right
        )

    def boolop_or_call_fold_left(
        self, node: cst.BooleanOperation
    ) -> cst.BooleanOperation:
        new_left = node.left.left
        new_right = self.combine_calls(node.left.right, node.right)
        return cst.BooleanOperation(
            left=new_left, operator=node.left.operator, right=new_right
        )
