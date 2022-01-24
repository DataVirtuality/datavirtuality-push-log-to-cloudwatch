from argparse import Namespace
import json
import os
from typing import Any, Dict, Final, Generator, List, Tuple, Union, TextIO, Optional, TypeVar, cast
import boto3
from botocore.client import Config
import re
import datetime as dt
from more_itertools import locate
import operator
from zoneinfo import ZoneInfo
from dataclasses import dataclass
import dataclasses


# SPDX-FileCopyrightText: ©2022 Data Virtuality. Author Carlos Klapp <carlos.klapp@datavirtuality.de>
# SPDX-License-Identifier: MIT


T = TypeVar('T')  # Any type.


@dataclass
class ResultOfLogProcessing:
    log_group_name: str
    log_stream_name: str
    server_log_base_file_path: str
    processed_server_log_file_path: str
    date_used: str
    num_events_processed: int
    num_events_skipped: int
    tzinfo: str
    num_batches: int
    start_time: str
    end_time: str
    elapsed_time: str
    rejected_events: List[Dict[str, Any]]


def rem_opt(arg: Optional[T]) -> T:
    """
    Removes the optional argument.
    """
    assert arg is not None
    return arg


def matchDate(line: str) -> Tuple[bool, Optional[dt.time]]:
    """
    Matches the start of a line to the known timestamp format in the log.

    Args:
        line (str): Line from log file

    Returns:
        Tuple[bool, Optional[datetime.time]]:
            False, None - If the beginning of string does NOT match.
            True, time - Beginning of string matches. The parsed time.

    """
    parsed_time: Optional[dt.time] = None
    matched = re.match(r'^\d{2}:\d{2}:\d{2},\d{3}\s', line)
    if matched:
        matchThis = matched.group().strip()
        parsed_time = dt.datetime.strptime(matchThis, "%H:%M:%S,%f").time()
    return matched is not None, parsed_time


# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/logs.html#CloudWatchLogs.Client.put_log_events
#   The batch of events must satisfy the following constraints:
#       The maximum batch size is 1,048,576 bytes. This size is calculated as the sum of all event messages in UTF-8,
#           plus 26 bytes for each log event.
#       None of the log events in the batch can be more than 2 hours in the future.
#       None of the log events in the batch can be older than 14 days or older than the retention period of the log group.
#       The log events in the batch must be in chronological order by their timestamp. The timestamp is the time the event
#           occurred, expressed as the number of milliseconds after Jan 1, 1970 00: 00: 00 UTC.
#           (In Amazon Web Services Tools for PowerShell and the Amazon Web Services SDK for .NET, the timestamp is
#           specified in .NET format: yyyy-mm-ddThh: mm: ss. For example, 2017-09-15T13: 45: 30.)
#       A batch of log events in a single request cannot span more than 24 hours. Otherwise, the operation fails.
#       The maximum number of log events in a batch is 10,000.
#       There is a quota of 5 requests per second per log stream. Additional requests are throttled. This quota can't be changed.
#       If a call to PutLogEvents returns "UnrecognizedClientException" the most likely cause is an invalid
#           Amazon Web Services access key ID or secret key.
def generate_dicts(log_fh: TextIO, date_of_log_entries: dt.date, skip_num_entries: int, tzinfo: ZoneInfo) -> Generator[Dict[str, Union[str, int]], None, None]:
    """
    Generate a list of dictionaries from the log file.

    Args:
        log_fh (TextIO): server log
        date_of_log_entries (datetime.date): date of log entries
        skip_num_entries (int): skip this many entries
        tzinfo (ZoneInfo): timezone used to process the timestamps

    Yields:
        Generator[dict[str, str], None, None]: [description]
    """
    SKIP_CHARS: Final[int] = 13  # len('00:58:09,612') = 12. Add +1 for the space.
    currentDict: Optional[Dict[str, Union[str, int]]] = None
    line_num = 0
    for line in log_fh:
        matched, parsed_time = matchDate(line)
        if matched:
            line_num += 1
            if line_num <= skip_num_entries:
                continue
            if currentDict:
                yield currentDict
            currentDict = {
                "timestamp": local_to_utc_timestamp(date_of_log_entries, rem_opt(parsed_time), tzinfo),
                "message": line[SKIP_CHARS:]
            }
        else:
            if line_num <= skip_num_entries:
                continue
            if currentDict is None:
                raise ValueError("currentDict should not be None.")
            else:
                currentDict["message"] = str(currentDict["message"]) + line
    if currentDict:
        yield currentDict


def local_to_utc_timestamp(date_of_log_entries: dt.date, entry_time: dt.time, tzinfo: ZoneInfo) -> int:
    local = dt.datetime.combine(date=date_of_log_entries, time=entry_time, tzinfo=tzinfo)
    utc = local.astimezone(dt.timezone.utc)
    return int(utc.timestamp() * 1000)


def init_aws_stream(client: Any, log_group_name: str, log_stream_name: str) -> Optional[str]:
    """
    Initialize AWS log stream.

    Args:
        client (Any): boto3 client
        log_stream_name (str): Name of the log stream

    Returns:
        next_token: used in calls for put_log_events

    """
    # Get the data about the logstream we're targeting.
    # Multiple logs may have been retrieved.
    next_token: Optional[str] = None
    response = client.describe_log_streams(
        logGroupName=log_group_name,
        logStreamNamePrefix=log_stream_name,
        orderBy='LogStreamName',  # 'LogStreamName' or 'LastEventTime'
        descending=False
    )

    # Locate the exact log we are looking for
    streams = response.get('logStreams')
    indexes = locate(streams, lambda x: x.get('logStreamName') == log_stream_name)
    idx = next(indexes, None)
    if idx is not None:
        s = streams[idx]
        next_token = s.get('uploadSequenceToken')
    else:
        # Create the log stream we're looking for
        client.create_log_stream(
            logGroupName=log_group_name,
            logStreamName=log_stream_name
        )

    return next_token


def create_batches(events: List[Dict]) -> List[List[Dict[str, Union[str, int]]]]:
    EVENT_OVERHEAD: Final[int] = 26  # plus 26 bytes for each log event.
    MAX_BYTES: Final[int] = 1048576  # 1 MB max cumulative size
    MAX_EVENTS: Final[int] = 10000  # 10,000 max events per batch
    batches: List[List[Dict[str, Union[str, int]]]] = []

    start_pos = 0
    num_events = 0
    cumulative_size = 0
    for idx, val in enumerate(events):
        num_events += 1
        ev = cast(Dict[str, Union[str, int]], val)
        size = len(cast(str, ev['message'])) + EVENT_OVERHEAD

        if idx + 1 == len(events):
            # last event
            batches.append(events[start_pos:])
        elif num_events > MAX_EVENTS or (cumulative_size + size) > MAX_BYTES:
            # we need to go back one to include the last event
            batches.append(events[start_pos: idx])
            start_pos = idx
            num_events = 1
            cumulative_size = size
        else:
            cumulative_size += size

    test_batches(batches, len(events), EVENT_OVERHEAD, MAX_BYTES, MAX_EVENTS)

    return batches


def test_batches(
    batches: List[List[Dict[str, Union[str, int]]]],
    TOTAL_NUM_EVENTS: int,
    EVENT_OVERHEAD: int,
    MAX_BYTES: int,
    MAX_EVENTS: int
) -> None:
    """
    Test the batches.

    Args:
        batches (List[List[Dict[str, Union[str, int]]]]): [description]
    """
    total_events = 0
    for batch in batches:
        assert len(batch) <= MAX_EVENTS
        total_events += len(batch)
        sum_bytes = 0
        sum_events = 0
        for event in batch:
            assert isinstance(event['timestamp'], int)
            assert isinstance(event['message'], str)
            sum_bytes += len(event['message']) + EVENT_OVERHEAD
            sum_events += 1
        assert sum_bytes <= MAX_BYTES
        assert sum_events <= MAX_EVENTS
        assert sum_events == len(batch)
    assert total_events == TOTAL_NUM_EVENTS


def post_log_events(
        client: Any,
        log_group_name: str,
        log_stream_name: str,
        next_token: Optional[str],
        log_event_batches: List[List[Dict[str, Union[str, int]]]]
) -> List[Dict[str, Any]]:
    """
    Post log events to AWS CloudWatch.

    Args:
        client (Any): boto3 client
        next_token (str): used in calls for put_log_events
        log_event_batch (List[Dict[str, str]]): Log events to post to AWS CloudWatch
    """
    # Post the log events to CloudWatch
    rejected_events: List[Dict[str, Any]] = []
    for log in log_event_batches:
        # Put an event
        response: Dict
        if next_token is None:
            response = client.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=log
            )
        else:
            response = client.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=log,
                sequenceToken=next_token
            )

        # Update the next token
        next_token = response.get('nextSequenceToken')
        rejected_log_events_info = response.get('rejectedLogEventsInfo')
        # rejected_log_events_info: Dict[str, Any] = cast(Dict[str, Any], response.get('rejectedLogEventsInfo'))
        if rejected_log_events_info is not None:
            rejected_events.append(rejected_log_events_info)
    return rejected_events


def process_log_file(
    skip_num_entries: int,
    tzinfo: ZoneInfo,
    date_of_log_entries: dt.date,
    server_log_base_file_path: str,
    process_server_log_file_path: str,
    log_stream_base_name: str,
    log_group_name: str,
) -> ResultOfLogProcessing:
    start_time = dt.datetime.today()

    with open(process_server_log_file_path) as f:
        log_events = list(generate_dicts(f, date_of_log_entries, skip_num_entries, tzinfo))

    # sort chronologically
    log_events.sort(key=operator.itemgetter('timestamp'))

    log_event_batches = create_batches(log_events)

    # Create CloudWatchEvents client
    #
    # See docs https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
    # config = Config(connect_timeout=5, retries={'max_attempts': 0}, read_timeout=5)
    # client = boto3.client('logs', config=config)
    client = boto3.client('logs')

    curr_log_stream = log_stream_base_name + date_of_log_entries.strftime("%Y-%m-%d")

    next_token = init_aws_stream(client, log_group_name, curr_log_stream)

    rejected_events = post_log_events(
        client=client,
        log_group_name=log_group_name,
        log_stream_name=curr_log_stream,
        log_event_batches=log_event_batches,
        next_token=next_token
    )

    end_time = dt.datetime.today()

    return ResultOfLogProcessing(
        log_stream_name=curr_log_stream,
        log_group_name=log_group_name,
        server_log_base_file_path=server_log_base_file_path,
        processed_server_log_file_path=process_server_log_file_path,
        date_used=str(date_of_log_entries),
        num_events_processed=len(log_events),
        num_events_skipped=skip_num_entries,
        rejected_events=rejected_events,
        tzinfo=str(tzinfo),
        num_batches=len(log_event_batches),
        start_time=str(start_time),
        end_time=str(end_time),
        elapsed_time=str(end_time - start_time)
    )


def read_prev_results(
    args: Namespace,
    path_results: str,
    log_stream_base_name: str,
    log_group_name: str,
) -> ResultOfLogProcessing:
    """
    Read previous results from a file. Else use the default.
    """
    if os.path.isfile(path_results) and os.path.getsize(path_results) > 0:
        with open('./results.json', 'rt', encoding='UTF8') as f:
            prev_results = json.load(f)
        return ResultOfLogProcessing(**prev_results)
    else:
        curr_log_stream: str = log_stream_base_name + args.date.strftime("%Y-%m-%d")
        return ResultOfLogProcessing(
            log_stream_name=curr_log_stream,
            log_group_name=log_group_name,
            server_log_base_file_path=args.server_log_base_file_path,
            processed_server_log_file_path=args.process_server_log_file_path,
            date_used=str(args.date),
            num_events_processed=0,
            num_events_skipped=int(args.skip),
            rejected_events=[],
            tzinfo=str(args.timezone),
            num_batches=0,
            start_time=str(dt.datetime.combine(args.date, dt.time.min)),
            end_time=str(dt.datetime.combine(args.date, dt.time.min)),
            elapsed_time='0=00=00.000000'
        )


def post_results(
    all_results: List[ResultOfLogProcessing],
    log_stream_name: str,
    log_group_name: str,
) -> None:
    # Create CloudWatchEvents client
    client = boto3.client('logs')

    next_token = init_aws_stream(client, log_group_name, log_stream_name)

    log_event_batches: List[List[Dict[str, Union[str, int]]]] = [[
        {
            "timestamp": int(dt.datetime.fromisoformat(results.end_time).timestamp() * 1000),
            "message": json.dumps(dataclasses.asdict(results))
        } for results in all_results
    ]]

    rejected_events = post_log_events(client=client, log_group_name=log_group_name, log_stream_name=log_stream_name, log_event_batches=log_event_batches, next_token=next_token)
    if len(rejected_events) > 0:
        print(f'Rejected events: {rejected_events} posting to {log_stream_name}')
