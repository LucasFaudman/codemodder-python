import json
from dataclasses import replace
from functools import cache
from pathlib import Path

import libcst as cst
from typing_extensions import Self

from codemodder.logging import logger
from codemodder.result import LineInfo, Location, Result, ResultSet


class SonarLocation(Location):
    @classmethod
    def from_result(cls, result) -> Self:
        location = result.get("textRange")
        start = LineInfo(location.get("startLine"), location.get("startOffset"), "")
        end = LineInfo(location.get("endLine"), location.get("endOffset"), "")
        file = Path(result.get("component").split(":")[-1])
        return cls(file=file, start=start, end=end)


class SonarResult(Result):

    @classmethod
    def from_result(cls, result) -> Self:
        # Sonar issues have `rule` as key while hotspots call it `ruleKey`
        if not (rule_id := result.get("rule", None) or result.get("ruleKey", None)):
            raise ValueError("Could not extract rule id from sarif result.")

        locations: list[Location] = [SonarLocation.from_result(result)]
        return cls(rule_id=rule_id, locations=locations)

    def match_location(self, pos, node):
        match node:
            case cst.Tuple():
                new_pos = replace(
                    pos,
                    start=replace(pos.start, column=pos.start.column - 1),
                    end=replace(pos.end, column=pos.end.column + 1),
                )
                return super().match_location(new_pos, node)
        return super().match_location(pos, node)


class SonarResultSet(ResultSet):
    @classmethod
    @cache
    def from_json(cls, json_file: str | Path) -> Self:
        try:
            with open(json_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            result_set = cls()
            for result in data.get("issues") or [] + data.get("hotspots") or []:
                if result["status"].lower() in ("open", "to_review"):
                    result_set.add_result(SonarResult.from_result(result))

            return result_set
        except Exception:
            logger.debug("Could not parse sonar json %s", json_file)
        return cls()
