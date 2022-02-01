
import argparse
import datetime as dt
from datetime import date
from distutils import util
from typing import Final
from zoneinfo import ZoneInfo
from tzlocal import get_localzone


# SPDX-FileCopyrightText: ©2022 Data Virtuality. Author Carlos Klapp <carlos.klapp@datavirtuality.de>
# SPDX-License-Identifier: MIT


COMMAND_LOG_MANUAL: Final[str] = 'log_manual'
COMMAND_LOG_AUTO: Final[str] = 'log_auto'
COMMAND_TZ: Final[str] = 'tz'


def get_local_tz() -> ZoneInfo:
    tzname = str(get_localzone())
    tzinfo: ZoneInfo = ZoneInfo(tzname)
    return tzinfo


def str2bool(s: str) -> bool:
    return bool(util.strtobool(s.lower()))


class _HelpAction(argparse._HelpAction):

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()

        # retrieve subparsers from parser
        subparsers_actions = [
            action for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)]
        # there will probably only be one subparser_action,
        # but better save than sorry
        for subparsers_action in subparsers_actions:
            # get all subparsers and print help
            for choice, subparser in subparsers_action.choices.items():
                print("Subparser '{}'".format(choice))
                print(subparser.format_help())

        parser.exit()


def add_common_options(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument('server_log_base_file_path', type=str, help='Base path to server log. Eg: /opt/datavirtuality/dvserver/standalone/log/server.log')
    subparser.add_argument(
        "--timezone", type=str, default=get_local_tz(), help="Specify the timezone (default: local time zone). "
        + "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones for a list of valid timezones. "
        + "Note that the timezone must be specified as a string, e.g. 'America/Los_Angeles'."
    )
    subparser.add_argument(
        "--skip", type=int, default=0, help="Skip a specified number of lines (default: 0). "
        + "This is useful if you have a large number of lines in the log file and you want to skip a few lines at the beginning."
    )
    subparser.add_argument(
        "--date", type=date.fromisoformat, default=date.today(), help="Date used to process the file (default: now). Format: YYYY-MM-DD"
    )


parser = argparse.ArgumentParser(description="Parse Data Virtuality server logs", add_help=False)  # here we turn off default help action
parser.add_argument('-h', '--help', action=_HelpAction, help='show this help message and exit')  # add custom help

subparsers = parser.add_subparsers(dest="command_name", help='sub-command help')

# create the parser for the "COMMAND_LOG_OVERRIDE" command
subparser_log_manual = subparsers.add_parser(COMMAND_LOG_MANUAL, description="Process a log file by specifying configuration info", help=f'${COMMAND_LOG_MANUAL} --help')
add_common_options(subparser_log_manual)
subparser_log_manual.add_argument('--process_server_log_file_path', type=str, help='Path to server log you want to process. Eg: /opt/datavirtuality/dvserver/standalone/log/server.log.2021-12-21')

# create the parser for the "COMMAND_LOG_TZ" command
subparser_tz = subparsers.add_parser(COMMAND_TZ, description="List all of the available time zones.", help=f'${COMMAND_TZ} --help')

# create the parser for the "COMMAND_LOG_AUTO" command
subparser_log_auto = subparsers.add_parser(COMMAND_LOG_AUTO, description="Process a log file and use previous information", help=f'${COMMAND_LOG_AUTO} --help')
add_common_options(subparser_log_auto)


if __name__ == '__main__':
    # app_args = parser.parse_args([])
    # app_args = parser.parse_args(["-h"])
    # app_args = parser.parse_args([f"${COMMAND_TZ}"])
    # app_args = parser.parse_args([f"${COMMAND_TZ}", "--help"])
    app_args = parser.parse_args(["log", "--help"])
    # app_args = parser.parse_args(["log"])
    if app_args.command_name in [COMMAND_LOG_MANUAL]:
        if 'process_server_log_file_path' not in app_args._get_kwargs():
            app_args.__dict__['process_server_log_file_path'] = app_args.server_log_base_file_path
    print(app_args)
else:
    app_args = parser.parse_args()
    if app_args.command_name in [COMMAND_LOG_MANUAL, COMMAND_LOG_AUTO]:
        if 'process_server_log_file_path' not in app_args._get_kwargs():
            app_args.__dict__['process_server_log_file_path'] = app_args.server_log_base_file_path
