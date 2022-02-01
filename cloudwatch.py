import csv
import json
import os
from typing import Any, Dict, Final, Generator, List, Tuple, Union, TextIO, Optional, TypeVar, cast
import datetime as dt
from zoneinfo import ZoneInfo, available_timezones
from arguments import COMMAND_LOG_AUTO, COMMAND_LOG_MANUAL, COMMAND_TZ, app_args
from libs import ResultOfLogProcessing, post_results, process_log_file, read_prev_results
import sys
import dataclasses

# SPDX-FileCopyrightText: ©2022 Data Virtuality. Author Carlos Klapp <carlos.klapp@datavirtuality.de>
# SPDX-License-Identifier: MIT

LOG_GROUP_NAME: Final[str] = 'DataVirtualityETLLogGroup'
LOG_STREAM_BASE_NAME: Final[str] = 'dv-server.log-'  # dv-server.log-2021-12-21
APP_LOG_STREAM_NAME: Final[str] = 'DV_2_CW_logger'  # Log stream name for the application
RESULTS_JSON_FILE_NAME: Final[str] = './results'
RESULTS_CSV_FILE: Final[str] = './results.csv'

all_results: List[ResultOfLogProcessing] = []
if app_args.command_name.lower() == COMMAND_TZ:
    print(available_timezones())
    sys.exit(0)
elif app_args.command_name.lower() == COMMAND_LOG_MANUAL:
    results = process_log_file(
        skip_num_entries=app_args.skip,
        tzinfo=ZoneInfo(app_args.timezone),
        date_of_log_entries=app_args.date,
        server_log_base_file_path=app_args.server_log_base_file_path,
        process_server_log_file_path=app_args.process_server_log_file_path,
        log_stream_base_name=LOG_STREAM_BASE_NAME,
        log_group_name=LOG_GROUP_NAME
    )
    all_results.append(results)
elif app_args.command_name.lower() == COMMAND_LOG_AUTO:
    previous_results: ResultOfLogProcessing = read_prev_results(
        args=app_args,
        path_results=RESULTS_JSON_FILE_NAME + '.json',
        log_stream_base_name=LOG_STREAM_BASE_NAME,
        log_group_name=LOG_GROUP_NAME
    )
    today: dt.date = dt.date.today()
    previous_date: dt.date = dt.datetime.strptime(previous_results.date_used, '%Y-%m-%d').date()

    # Handle the case when the server.log has been rotated to a new file server.log.2021-12-21
    if previous_date < today:
        rotated_server_log_path: str = str(previous_results.server_log_base_file_path) + '.' + str(previous_results.date_used)
        if os.path.isfile(rotated_server_log_path):
            results = process_log_file(
                skip_num_entries=previous_results.num_events_processed + previous_results.num_events_skipped,
                tzinfo=ZoneInfo(previous_results.tzinfo),
                date_of_log_entries=previous_date,
                server_log_base_file_path=previous_results.server_log_base_file_path,
                process_server_log_file_path=rotated_server_log_path,
                log_stream_base_name=LOG_STREAM_BASE_NAME,
                log_group_name=LOG_GROUP_NAME
            )
            all_results.append(results)

        # The server log has been rotated. Process the new server log and don't skip any entries
        previous_results.num_batches = 0
        previous_results.num_events_processed = 0
        previous_results.num_events_skipped = 0
        previous_results.processed_server_log_file_path = previous_results.server_log_base_file_path

    # Process the current server.log
    results = process_log_file(
        skip_num_entries=previous_results.num_events_processed + previous_results.num_events_skipped,
        tzinfo=ZoneInfo(previous_results.tzinfo),
        date_of_log_entries=today,
        server_log_base_file_path=previous_results.server_log_base_file_path,
        process_server_log_file_path=previous_results.processed_server_log_file_path,
        log_stream_base_name=LOG_STREAM_BASE_NAME,
        log_group_name=LOG_GROUP_NAME
    )
    all_results.append(results)
else:
    raise ValueError(f'Invalid command name: {app_args.command_name}')


results_json_file: str = ''
if app_args.command_name.lower() == COMMAND_LOG_MANUAL:
    results_json_file = RESULTS_JSON_FILE_NAME + '-' + str(dt.date.today()) + '.json'
elif app_args.command_name.lower() == COMMAND_LOG_AUTO:
    results_json_file = RESULTS_JSON_FILE_NAME + '.json'

with open(results_json_file, 'wt', encoding='UTF8') as f:
    json.dump(dataclasses.asdict(results), f, sort_keys=True, indent=4)


with open(RESULTS_CSV_FILE, 'at', encoding='UTF8', newline='') as f:
    results_as_dict: Dict = dataclasses.asdict(results)
    fieldnames = list(results_as_dict)
    fieldnames.sort()
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    if os.path.getsize(RESULTS_CSV_FILE) == 0:
        writer.writeheader()
    writer.writerows([dataclasses.asdict(x) for x in all_results])

post_results(all_results, APP_LOG_STREAM_NAME, LOG_GROUP_NAME)
print()
