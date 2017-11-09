import argparse
import datetime
import time
import numpy as np
import boto3
from matplotlib_utils import plotLine, plt_ion, plt_ioff


def create_parser():
    parser = argparse.ArgumentParser("""
Read and print the contents of a selected stream as fast as possible, and plot performance.
""")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default is "
                        "'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("-p", "--period", dest="period", type=int, default=None,
                        help="How often to read stream. Default is 0. This number will increase"
                        " if the stream is read too often.", metavar="MILLISECONDS",)
    parser.add_argument("-t", "--timeout", dest="timeout", type=int, default=60,
                        help="When to timeout and plot results. Default waits 1 minute.",
                        metavar="SECONDS",)
    choices = ["LATEST", "TRIM_HORIZON"]
    parser.add_argument("-sit", "--shard_iterator_type", dest="shard_iterator_type", type=str,
                        default=choices[0], choices=choices, help="Select what data will be "
                        "returned from stream every query. Options are "
                        "{}. Default is '{}'.".format(choices, choices[0]),
                        metavar="SHARD_ITERATOR_TYPE")
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
    try:
        print("Monitoring data in stream for {} seconds.".format(args.timeout))
        while datetime.datetime.now() < terminate_time:
            try:
                records = kinesis_client.get_records(ShardIterator=shard_iterator,
                                                     Limit=max_num_records)
                now_time = datetime.datetime.now()
                for r in records["Records"]:
                    start_end_times.append((r["Data"], now_time))
                shard_iterator = records["NextShardIterator"]  # Update shard_iterator
                time.sleep(sleep_time)
            except Exception as e:
                number_exceptions += 1
                # print(e)
                # sleep_time += 0.001
                # print(sleep_time)
                time.sleep(0.01)
            # time.sleep(sleep_time)
        print("Finished data monitoring.".format(args.timeout))
    except KeyError:
        print("Ctrl+C interrupt received, prematurely halting data monitoring.")

    delays = []
    for json_obj0, time1 in start_end_times:
        idx = json_obj0.index(b'"timestamp": "') + 14
        time0 = json_obj0[idx:idx + 26].decode("utf-8")
        delay = time1 - datetime.datetime.strptime(time0, "%Y-%m-%d %H:%M:%S.%f")
        delays.append(delay)
    delays = np.array(delays)
    delays_ms = [1000.0 * d.total_seconds() for d in delays]
    print("Samples: {}".format(len(delays)))
    if len(delays) == 0:
        return
    print("Min: {}".format(np.min(delays)))
    print("Max: {}".format(np.max(delays)))
    print("Avg: {}".format(np.mean(delays)))
    print("Std: {}".format(np.std(delays_ms)))
    print("Err: {}".format(number_exceptions))

    bucket_delays_ms = [0] * int(np.max(delays_ms) + 1)
    for d in delays_ms:
        bucket_delays_ms[int(d)] += 1
    cum_delays_ms = []
    prev_delay = 0
    for d in bucket_delays_ms:
        prev_delay += d
        cum_delays_ms.append(prev_delay)
    plt_ion()
    plotLine(delays_ms, x_label="samples", y_label="ms", title="Delays", figure=0, color="r")
    plotLine(bucket_delays_ms, x_label="ms", y_label="# cases", title="Historiogram delays",
             figure=1, color="b")
    plotLine(cum_delays_ms, x_label="ms", y_label="# cases", title="Cumulative delays", figure=2,
             color="m")
    plt_ioff()
    input("Type ENTER to close all figures.")


if __name__ == '__main__':
    main()
