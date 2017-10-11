import argparse
import time
import boto3


def create_parser():
    parser = argparse.ArgumentParser("""
Puts words into a selected stream, or numbers if no words are given. If p is set, send words or numbers every p milliseconds.
# Send WORD1, WORD2 and WORD3 every 1 second into STREAM_NAME stream
stream_producer.py -s STREAM_NAME -w WORD1 -w WORD2 -w WORD3 -p 1000
# Send numbers from 0 to 'infinity' every 500 ms, one at a time, into STREAM_NAME stream
stream_producer.py -s STREAM_NAME -p 500
""")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default is 'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("-w", "--word", dest="words", default=[], action="append",
                        help="A word to add to the stream. Can be specified multiple times to add multiple words.", metavar="WORD",)
    parser.add_argument("-p", "--period", dest="period", type=int,
                        help="If you'd like to repeatedly put words into the stream, this option provides the period for putting "
                            + "words into the stream in SECONDS. If no period is given then the words are put once.",
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
        print("Stream '{}' has status {}, sleeping for {} seconds".format(stream_name, status, sleep_seconds))
        time.sleep(sleep_seconds)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name)
        status = stream_description["StreamDescription"]["StreamStatus"]


def put_words_in_stream(kinesis_client, stream_name, words, partition_key="123"):
    # Put each word in the provided list of words into the stream.
    for w in words:
        try:
            kinesis_client.put_record(StreamName=stream_name, Data=w, PartitionKey=partition_key, SequenceNumberForOrdering=str(1))
            print("Put record '{}' into stream '{}'".format(w, stream_name))
        except Exception as e:
            print("Encountered an exception while trying to put record '{}' into stream '{}'".format(w, stream_name))
            print("Exception: {}".format(e))


def put_words_in_stream_periodically(kinesis_client, stream_name, words, period_seconds):
    # Put words into stream, then wait for the period, then put same words again.
    # There is no strict guarantee about how frequently we put each word into the stream, just that we will wait between iterations.
    while True:
        put_words_in_stream(kinesis_client, stream_name, words)
        print("Sleeping for {} milliseconds".format(period_seconds))
        time.sleep(period_seconds / 1000.0)


def put_numbers_in_stream_periodically(kinesis_client, stream_name, period_seconds):
    # Put number into stream, then wait for the period, then put next number, etc.
    # There is no strict guarantee about how frequently we put each number into the stream, just that we will wait between iterations.
    n = 0;
    while True:
        put_words_in_stream(kinesis_client, stream_name, [str(n)])
        n += 1
        print("Sleeping for {} milliseconds".format(period_seconds))
        time.sleep(period_seconds / 1000.0)


def main():
    args = create_parser()
    stream_name = args.stream_name

    print("Connecting to stream '{}' in region '{}'.".format(stream_name, args.region))
    kinesis_client = boto3.client('kinesis', region_name=args.region)
    try:
        # The stream does exist already (if no Exception occurs)
        stream_description = kinesis_client.describe_stream(StreamName=stream_name)
        status = stream_description["StreamDescription"]["StreamStatus"]
        if status == "DELETING":
            print("The stream '{}' is being deleted, please rerun the script.".format(stream_name))
            return
        elif status != "ACTIVE":
            wait_for_stream(kinesis_client, stream_name)
    except:
        # We assume the stream didn't exist so we will try to create it with just one shard
        print("Creating stream '{}'".format(stream_name))
        kinesis_client.create_stream(StreamName=stream_name, ShardCount=1)
        wait_for_stream(kinesis_client, stream_name)
 
    # Now the stream should exist
    words = args.words
    if len(words) > 0:
        if args.period != None:
            put_words_in_stream_periodically(kinesis_client, stream_name, words, args.period)
        else:
            put_words_in_stream(kinesis_client, stream_name, words)
    else:
        if args.period != None:
            put_numbers_in_stream_periodically(kinesis_client, stream_name, args.period)
        else:
            put_words_in_stream(kinesis_client, stream_name, [str(0)])
    
    # Delete stream when we finish
    #kinesis_client.delete_stream(StreamName=stream_name)


if __name__ == '__main__':
    main()

