import argparse
import datetime
import time
import boto3


def create_parser():
    parser = argparse.ArgumentParser("""
Read and print the contents of a selected stream every p milliseconds. It will only print up to 10000 records every iteration.
""")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default is 'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("-p", "--period", dest="period", type=int, default=None,
                        help="How often to read stream", metavar="MILLISECONDS",)
    choices=["TRIM_HORIZON", "LATEST", "AT_SEQUENCE_NUMBER", "AFTER_SEQUENCE_NUMBER", "AT_TIMESTAMP"]
    parser.add_argument("-sit", "--shard_iterator_type", dest="shard_iterator_type", type=str, default=choices[0],
                        choices=choices, help="Select what data will be returned from stream every query. "
                        "Options are {}. Default is '{}'.".format(choices, choices[0]), metavar="SHARD_ITERATOR_TYPE")
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
            print("The stream '{}' has status {}, please rerun the script when the stream is ACTIVE.".format(stream_name))
            return
        else:
            shard_id = stream_description["StreamDescription"]["Shards"][0]["ShardId"]
    except:
        # We assume the stream didn't exist so we will try to create it with just one shard
        print("The stream '{}' was not found, please rerun the script when the stream has been created.".format(stream_name))
        return

    # If we reach this point, the string is active
    shard_iterator_type = args.shard_iterator_type
    if shard_iterator_type == "TRIM_HORIZON" or shard_iterator_type == "LATEST":
        shard_iterator = kinesis_client.get_shard_iterator(StreamName=stream_name, ShardId=shard_id,
                                                           ShardIteratorType=shard_iterator_type)["ShardIterator"]
    elif shard_iterator_type == "AT_SEQUENCE_NUMBER" or shard_iterator_type == "AFTER_SEQUENCE_NUMBER":
        sequence_number = str(0)  # This crashes, we need to use a valid sequence_number
        shard_iterator = kinesis_client.get_shard_iterator(StreamName=stream_name, ShardId=shard_id,
                                                           ShardIteratorType=shard_iterator_type,
                                                           StartingSequenceNumber=sequence_number)["ShardIterator"]
    elif shard_iterator_type == "AT_TIMESTAMP":
        timestamp = datetime.datetime.now()  # Because timestamp is now, this acts like LATEST
        shard_iterator = kinesis_client.get_shard_iterator(StreamName=stream_name, ShardId=shard_id,
                                                           ShardIteratorType=shard_iterator_type,
                                                           Timestamp=timestamp)["ShardIterator"]
    else:
        print("Unknown shard iterator type {}.".format(shard_iterator_type))
        return

    max_num_records = 10000
    # Get records, print them and sleep (forever)
    if args.period is not None:
        sleep_time = args.period / 1000.0
        while True:
            records = kinesis_client.get_records(ShardIterator=shard_iterator, Limit=max_num_records)
            shard_iterator = records["NextShardIterator"]  # Update shard_iterator
            millis_behind = records["MillisBehindLatest"]
            if millis_behind != 0:
                print("We are {} ms behind".format(millis_behind))
                sleep(3)
            for r in records["Records"]:
                print(r["Data"])

            time.sleep(sleep_time)
    
    # Get records and print them once
    records = kinesis_client.get_records(ShardIterator=shard_iterator, Limit=max_num_records)
    for r in records["Records"]:
        print(r["Data"])


if __name__ == '__main__':
    main()

