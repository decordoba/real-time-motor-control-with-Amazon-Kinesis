import argparse
import time
import datetime
import boto3
import json


def create_parser():
    parser = argparse.ArgumentParser("""
Receive encoder data from input stream and send it to output stream transformed
""")
    parser.add_argument("-sin", "--stream_in", dest="stream_in_name", required=True,
                        help="The stream you'd like to read from.", metavar="STREAM_NAME",)
    parser.add_argument("-sout", "--stream_out", dest="stream_out_name", required=True,
                        help="The stream you'd like to write to.", metavar="STREAM_NAME",)
    parser.add_argument("-rin", "--region_in", dest="region_in", default="us-east-1",
                        help="The region where stream_in is. Default is 'us-east-1'",
                        metavar="REGION_NAME",)
    parser.add_argument("-rout", "--region_out", dest="region_out", default="us-east-1",
                        help="The region where stream_out is. Default is 'us-east-1'",
                        metavar="REGION_NAME",)
    parser.add_argument("-p", "--period", dest="period", type=int,
                        help="Period to wait between reading the stream. If not set, data will "
                        "be iread and sent as fast as possible.",
                        metavar="MILLISECONDS",)
    return parser.parse_args()


def wait_for_stream(kinesis_client, stream_name, sleep_seconds=3):
    # Wait for the provided stream to become active
    describe_stream_error = True
    while describe_stream_error:
        try:
            stream_description = kinesis_client.describe_stream(StreamName=stream_name)
            status = stream_description["StreamDescription"]["StreamStatus"]
            describe_stream_error = False
        except KeyError:
            pass
    while status != 'ACTIVE':
        print("Stream '{}' has status {}, sleeping for {} seconds.".format(stream_name, status,
                                                                           sleep_seconds))
        time.sleep(sleep_seconds)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name)
        status = stream_description["StreamDescription"]["StreamStatus"]


def connect_to_stream(kinesis_client, stream_name):
    # Connect to stream, and if it does not exist, create it and wait until it is ACTIVE
    try:
        # The stream does exist already (if no Exception occurs)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name)
        status = stream_description["StreamDescription"]["StreamStatus"]
        if status == "DELETING":
            print("The stream '{}' is being deleted, please rerun the script.".format(stream_name))
            return False
        elif status != "ACTIVE":
            wait_for_stream(kinesis_client, stream_name)
    except:
        # We assume the stream didn't exist so we will try to create it with just one shard
        print("Creating stream '{}'.".format(stream_name))
        kinesis_client.create_stream(StreamName=stream_name, ShardCount=1)
        wait_for_stream(kinesis_client, stream_name)
    return True


def main():
    args = create_parser()

    # Create and connect to output stream
    stream_name_out = args.stream_out_name
    print("Connecting to output stream '{}' in region '{}'.".format(stream_name_out,
                                                                    args.region_out))
    kinesis_client = boto3.client('kinesis', region_name=args.region_out)
    if not connect_to_stream(kinesis_client, stream_name_out):
        return

    # Create and connect to input stream
    stream_name_in = args.stream_in_name
    print("Connecting to input stream '{}' in region '{}'.".format(stream_name_in, args.region_in))
    kinesis_client = boto3.client('kinesis', region_name=args.region_in)
    try:
        # The stream does exist already (if no Exception occurs)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name_in)
        status = stream_description["StreamDescription"]["StreamStatus"]
        if status != "ACTIVE":
            print("The stream '{}' has status {}, please rerun the script when the stream "
                  "is ACTIVE.".format(stream_name_in))
            return
        else:
            shard_id = stream_description["StreamDescription"]["Shards"][0]["ShardId"]
    except:
        # We assume the stream doesn't exist so we will interrupt the program
        print("The stream '{}' was not found, please rerun the script when the stream has "
              "been created.".format(stream_name_in))
        return

    # If we reach this point, both strings are active
    shard_iterator_type = "LATEST"
    shard_iterator = kinesis_client.get_shard_iterator(StreamName=stream_name_in,
                                                       ShardId=shard_id,
                                                       ShardIteratorType=shard_iterator_type)["ShardIterator"]

    # Send messages from 'stream in' to 'stream out' after transforming them
    max_num_records = 10000
    sleep_s = 0.0 if args.period is None else args.period / 1000
    p_constant = 255 / 180
    goal_pos = 0
    while True:
        try:
            records = kinesis_client.get_records(ShardIterator=shard_iterator,
                                                 Limit=max_num_records)
            shard_iterator = records["NextShardIterator"]  # Update shard_iterator
        except Exception as e:
            time.sleep(0.01)
            continue

        for record in records["Records"]:
            # Receive object from input stream
            json_str_in = record["Data"].decode("utf-8")
            obj = json.loads(json_str_in)

            # Update goal_postion if we get a message of type 2
            if obj["msg_type"] == 2:
                goal_pos = obj["value"]

            # If object is not encoder ob
            if obj["msg_type"] != 0:
                continue

            # Transform data
            obj["value"] = (obj["value"] % 360)  # transform values from linear to degrees
            obj["value"] = obj["value"] - 360 if obj["value"] > 180 else obj["value"]
            obj["value"] = (obj["value"] - goal_pos) * p_constant  # P transformation
            obj["msg_type"] = 1  # type 1 refers to motor data
            obj["timestamp2"] = str(datetime.datetime.now())  # Add new timestamp

            # Send object in output stream
            json_str_out = json.dumps(obj)

            # Send into stream
            try:
                kinesis_client.put_record(StreamName=stream_name_out, Data=json_str_out,
                                          PartitionKey="123")
                print("Received: '{}' from stream '{}'.".format(json_str_in, stream_name_in))
                print("Sent:     '{}' into stream '{}'.".format(json_str_out, stream_name_out))
            except Exception as e:
                print("Encountered an exception while trying to put record '{}'"
                      " into stream '{}'.".format(stream_name_out))
                print("Exception: {}.".format(json_str_out, e))

            # Wait delay
            time.sleep(sleep_s)


if __name__ == '__main__':
    main()
