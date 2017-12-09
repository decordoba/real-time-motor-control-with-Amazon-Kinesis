import argparse
import json
import datetime
import time
import numpy as np
import boto3
from matplotlib_utils import plotLine, plotPlotBox, plt_ion, plt_ioff


def create_parser():
    parser = argparse.ArgumentParser("""
Read and print the contents of a selected stream as fast as possible, and plot performance.
The plots will also be saved into the figures folder.
""")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default is "
                        "'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("-p", "--period", dest="period", type=int, default=None,
                        help="How often to read stream. Default is 0.", metavar="MILLISECONDS",)
    parser.add_argument("-t", "--timeout", dest="timeout", type=int, default=60,
                        help="When to timeout and plot results. Default waits 1 minute.",
                        metavar="SECONDS",)
    parser.add_argument("-m", "--max_records", dest="max_records", type=int, default=None,
                        help="If set, stop monitoring stream after reading N records.",
                        metavar="RECORDS",)
    choices = ["LATEST", "TRIM_HORIZON"]
    parser.add_argument("-sit", "--shard_iterator_type", dest="shard_iterator_type", type=str,
                        default=choices[0], choices=choices, help="Select what data will be "
                        "returned from stream every query. Options are "
                        "{}. Default is '{}'.".format(choices, choices[0]),
                        metavar="SHARD_ITERATOR_TYPE")
    parser.add_argument("--noplot", dest="noplot", action="store_true", help="Do not plot "
                        "or save any figure.",)
    parser.add_argument("-f", "--filename", dest="filename", default=None,
                        help="Choose file name to save data recorded. If unset, the data will"
                        " not be saved.", metavar="FILE_NAME",)
    return parser.parse_args()


def main():
    args = create_parser()
    stream_name = args.stream_name

    print("Connecting to stream '{}' in region '{}'.".format(stream_name, args.region))
    kinesis_client = boto3.client('kinesis', region_name=args.region)
    try:
        # The stream does exist already (if no Exception occurs)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name)
        status = stream_description["StreamDescription"]["StreamStatus"]
        if status != "ACTIVE":
            print("The stream '{}' has status {}, please rerun the script when the stream "
                  "is ACTIVE.".format(stream_name))
            return
        else:
            shard_id = stream_description["StreamDescription"]["Shards"][0]["ShardId"]
    except:
        # We assume the stream didn't exist so we will try to create it with just one shard
        print("The stream '{}' was not found, please rerun the script when the stream has "
              "been created.".format(stream_name))
        return

    # If we reach this point, the string is active
    shard_iterator_type = args.shard_iterator_type
    shard_iterator = kinesis_client.get_shard_iterator(StreamName=stream_name, ShardId=shard_id,
                                                       ShardIteratorType=shard_iterator_type)["ShardIterator"]

    # Calculate termination time
    terminate_time = datetime.datetime.now() + datetime.timedelta(seconds=args.timeout)

    # Read stream until timeout
    max_num_records = 10000
    start_end_times = []
    sleep_time = 0.0 if args.period is None else args.period / 1000.0
    number_exceptions = 0
    num_records = 0
    try:
        print("Monitoring data in stream for {} seconds.".format(args.timeout))
        while datetime.datetime.now() < terminate_time:
            try:
                records = kinesis_client.get_records(ShardIterator=shard_iterator,
                                                     Limit=max_num_records)
                now_time = datetime.datetime.now()
                for r in records["Records"]:
                    start_end_times.append((r["Data"], now_time))
                    num_records += 1
                shard_iterator = records["NextShardIterator"]  # Update shard_iterator
                if args.max_records is not None and num_records >= args.max_records:
                    break
                time.sleep(sleep_time)
            except Exception as e:
                number_exceptions += 1
                time.sleep(0.01)
        print("Finished data monitoring.")
    except KeyError:
        print("Ctrl+C interrupt received, prematurely halting data monitoring.")

    # Calculate delay and print some data about them
    delays = []
    for json_obj0, time1 in start_end_times:
        time0 = json.loads(json_obj0.decode("utf-8"))["timestamp"]
        delay = time1 - datetime.datetime.strptime(time0, "%Y-%m-%d %H:%M:%S.%f")
        delays.append(delay)
    if args.max_records is not None:
        delays = delays[:args.max_records]
    delays = np.array(delays)
    delays_ms = [1000.0 * d.total_seconds() for d in delays]
    print("Samples: {}".format(len(delays)))
    if len(delays) == 0:
        return
    print("Min: {:.3f} ms".format(np.min(delays_ms)))
    print("Max: {:.3f} ms".format(np.max(delays_ms)))
    print("Med: {:.3f} ms".format(np.median(delays_ms)))
    print("Avg: {:.3f} ms".format(np.mean(delays_ms)))
    print("Std: {:.3f} ms".format(np.std(delays_ms)))
    print("Err: {}".format(number_exceptions))

    # Convert data to historiogram and cumulative format
    bucket_delays_ms = [0] * int(np.max(delays_ms) + 1)
    for d in delays_ms:
        bucket_delays_ms[int(d)] += 1
    cum_delays_ms = []
    prev_delay = 0
    for d in bucket_delays_ms:
        prev_delay += d
        cum_delays_ms.append(prev_delay)

    if args.filename is not None:
        np.save(args.filename, delays_ms)

    if not args.noplot:
        # Plot 4 figures
        plt_ion()
        plotLine(delays_ms, x_label="samples", y_label="ms", title="Delays", figure=0, color="r")
        plotLine(bucket_delays_ms, x_label="ms", y_label="# cases", title="Historiogram delays",
                 figure=1, color="b")
        plotLine(cum_delays_ms, x_label="ms", y_label="# cases", title="Cumulative delays",
                 figure=2, color="m")
        plotPlotBox(delays_ms, y_label="ms", title="Box plot delays", figure=3)
        plt_ioff()
        input("Type ENTER to close all figures.")


if __name__ == '__main__':
    main()
