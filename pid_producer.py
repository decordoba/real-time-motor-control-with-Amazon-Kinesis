import argparse
import time
import datetime
import boto3
import json


def create_parser():
    parser = argparse.ArgumentParser("""
Send random sensor data as json objects into a selected stream.
""")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default "
                        "is 'us-east-1'", metavar="REGION_NAME",)
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

    # Create and connect to stream
    stream_name = args.stream_name
    print("Connecting to stream '{}' in region '{}'.".format(stream_name, args.region))
    kinesis_client = boto3.client('kinesis', region_name=args.region)
    if not connect_to_stream(kinesis_client, stream_name):
        return

    # Now the stream should exist
    usr_input = ""
    counter = 0
    constant = "P"
    while len(usr_input) == 0 or usr_input[0].lower() != "q":
        usr_input = input("Enter {} constant. Type 'p', 'i', 'd' to change constant sent. "
                          "Type q to exit.\n>> ".format(constant))
        if len(usr_input) == 0:
            continue
        if usr_input[0].lower() == "q":
            continue
        elif usr_input[0].lower() == "p":
            constant = "P"
            print("Constant set to: {}".format(constant))
            continue
        elif usr_input[0].lower() == "i":
            constant = "I"
            print("Constant set to: {}".format(constant))
            continue
        elif usr_input[0].lower() == "d":
            constant = "D"
            print("Constant set to: {}".format(constant))
            continue
        try:
            value = float(usr_input)
        except ValueError:
            print("Error in speed value.")
            continue

        # Create object
        obj = {}
        obj["msg_type"] = 4  # type 4 refers to pid data
        obj["p"] = 999
        obj["i"] = 999
        obj["d"] = 999
        obj[constant.lower()] = value
        obj["sequence"] = counter
        obj["timestamp"] = str(datetime.datetime.now())
        counter += 1

        # Convert to json
        json_str = json.dumps(obj)

        # Send into stream
        try:
            kinesis_client.put_record(StreamName=stream_name, Data=json_str, PartitionKey="123")
            print("{}. Sent PID value {}: '{:.2f}' into stream '{}'.".format(obj["sequence"],
                                                                             constant,
                                                                             value,
                                                                             stream_name))
        except Exception as e:
            print("Encountered an exception while trying to put record '{}' into "
                  "stream '{}'.".format(json_str, stream_name))
            print("Exception: {}.".format(e))


if __name__ == '__main__':
    main()
