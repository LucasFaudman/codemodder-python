import argparse
import sys

from codemodder import __VERSION__
from codemodder.codemods import CODEMODS


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        """If there is an argument parsing error, print the `--help` message and the error."""
        self.print_help(sys.stderr)
        sys.exit(f"CLI error: {message}")


class ListAction(argparse.Action):
    """ """

    def _print_codemods(self):
        for codemod_name in CODEMODS:
            print(f"pixee:python/{codemod_name}")

    def __call__(self, parser, *args, **kwargs):
        """
        Print codemod(s) metadata in the following format:

        pixee:python/secure-random
        pixee:python/url-sandbox
        ...

        and exit gracefully.
        """
        self._print_codemods()
        parser.exit()


class CsvListAction(argparse.Action):
    """
    argparse Action to convert "a,b,c" into ["a", "b", "c"]
    """

    def __call__(self, parser, namespace, values, option_string=None):
        self.items = values.split(",")
        self.validate_items()
        setattr(namespace, self.dest, self.items)

    def validate_items(self):
        """Basic Action does not validate the items"""


class ValidatedCodmods(CsvListAction):
    """
    argparse Action to convert "codemod1,codemod2,codemod3" into a list
    representation and validate against existing codemods
    """

    def validate_items(self):
        unrecognized_codemods = [name for name in self.items if name not in CODEMODS]
        if unrecognized_codemods:
            args = {
                "values": unrecognized_codemods,
                "choices": ", ".join(map(repr, CODEMODS.keys())),
            }
            msg = "invalid choice(s): %(values)r (choose from %(choices)s)"
            raise argparse.ArgumentError(self, msg % args)


def parse_args(argv):
    """
    Parse CLI arguments according to:
    https://www.notion.so/pixee/Codemodder-CLI-Arguments
    """
    parser = ArgumentParser(description="Run codemods and change code.")

    parser.add_argument("directory", type=str, help="path to find files")
    parser.add_argument(
        "--output",
        type=str,
        help="name of output file to produce",
        default="stdout",
        required=True,
    )

    codemod_args_group = parser.add_mutually_exclusive_group()
    codemod_args_group.add_argument(
        "--codemod-exclude",
        action=ValidatedCodmods,
        help="Comma-separated set of codemod ID(s) to exclude",
    )
    codemod_args_group.add_argument(
        "--codemod-include",
        action=ValidatedCodmods,
        help="Comma-separated set of codemod ID(s) to include",
    )

    parser.add_argument("--version", action="version", version=__VERSION__)
    parser.add_argument(
        "--list", action=ListAction, nargs=0, help="Print codemod(s) metadata"
    )
    parser.add_argument(
        "--output-format",
        type=str,
        help="the format for the data output file",
        default="codetf",
        choices=["codetf", "diff"],
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        help="do everything except make changes to files",
    )

    parser.add_argument("--verbose", type=bool, help="print more to stdout")
    parser.add_argument(
        "--path-exclude",
        action=CsvListAction,
        help="Comma-separated set of UNIX glob patterns to exclude",
    )
    parser.add_argument(
        "--path-include",
        action=CsvListAction,
        help="Comma-separated set of UNIX glob patterns to include",
    )

    # At this time we don't do anything with the sarif arg.
    parser.add_argument(
        "--sarif",
        help="Comma-separated set of path(s) to SARIF file(s) to feed to the codemods",
    )
    return parser.parse_args(argv)
