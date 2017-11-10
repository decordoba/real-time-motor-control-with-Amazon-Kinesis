import argparse
import boto3
import socket
import time


"""
This program will send all messages received from an UDP connection into a selected stream.
"""


def create_parser():
    parser = argparse.ArgumentParser("Send encoder data as json objects into a selected stream.")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default "
                        "is 'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("--ip", dest="ip", default="localhost", help="Connection IP. Default is"
                        "localhost.", metavar="IP_ADDRESS")
    parser.add_argument("--port", dest="port", default=9999, type=int, help="Connection port. "
                        "Default is 9999.", metavar="PORT")
    parser.add_argument("-p", "--period", dest="period", type=int,
                        help="Period to wait between every encoder parse and stream transmition. "
                        "If not set, data will be sent as fast as possible.",
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

    # Create and connect to stream
    stream_name = args.stream_name
    print("Connecting to stream '{}' in region '{}'.".format(stream_name, args.region))
    kinesis_client = boto3.client('kinesis', region_name=args.region)
    if not connect_to_stream(kinesis_client, stream_name):
        return

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # SOCK_DGRAM means UDP
    sock.bind((args.ip, args.port))

    # Read the encoder and send position to stream
    sleep_s = None if args.period is None else args.period / 1000
    while True:
        udp_str, addr = sock.recvfrom(1024)
        udp_str = udp_str.decode("utf-8")

        # Send into stream
        try:
            kinesis_client.put_record(StreamName=stream_name, Data=udp_str, PartitionKey=":)")
            print("Sending '{}' into stream '{}'.".format(udp_str, stream_name))
        except Exception as e:
            print("Encountered an exception while trying to put '{}' into "
                  "stream '{}'.".format(udp_str, stream_name))
            print("Exception: {}.".format(e))

        if sleep_s is not None:
            # print("Sleeping for {} milliseconds.".format(args.period))
            time.sleep(sleep_s)


if __name__ == '__main__':
    main()
