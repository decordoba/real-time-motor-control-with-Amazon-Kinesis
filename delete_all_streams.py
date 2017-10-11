import boto3
import argparse

def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default is 'us-east-1'", metavar="REGION_NAME",)
    return parser.parse_args()

def main():
    args = create_parser()
    kinesis_client = boto3.client('kinesis', region_name=args.region)
    
    response = kinesis_client.list_streams()
    
    # Delete all stream
    for stream_name in response["StreamNames"]:
        print("Deleting stream {}".format(stream_name))
        kinesis_client.delete_stream(StreamName=stream_name)

if __name__ == '__main__':
    main()

