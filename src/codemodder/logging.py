from enum import Enum
import logging
import sys

logger = logging.getLogger("codemodder")


class OutputFormat(Enum):
    """
    Enum for the output format of the logger.
    """

    HUMAN = "human"
    JSON = "json"


def configure_logger(verbose: bool):
    """
    Configure the logger based on the verbosity level.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    # TODO: this should all be conditional on the output format
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.addFilter(lambda record: record.levelno <= logging.WARNING)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[stdout_handler, stderr_handler],
    )
