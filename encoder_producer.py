from RPi import GPIO
import argparse
import boto3
import datetime
import json
import time


"""
This program will send the state of the encoder as fast as possible.
This code should be used in a Raspberry Pi connected to an encoder.

In my case, I am using the JGA25-371 motor with encoder. This code only uses the encoder.
This motor has 6 wires:
    * Motor GND (Black): DO NOT CONNECT TO RPi, USE H-BRIDGE GND
    * Motor Vcc (Red):   DO NOT CONNECT TO RPi, USE H-BRIDGE Vcc
    * GND (Green):       Connect to RPi Gnd
    * Vcc (Blue):        Connect to RPi 5V
    * A Vout (Yellow):   Connect to RPi GPIO17
    * B Vout (White):    Connect to RPi GPIO18
"""


def create_parser():
    parser = argparse.ArgumentParser("Send encoder data as json objects into a selected stream.")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default "
                        "is 'us-east-1'", metavar="REGION_NAME",)
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

    # Select where the two data channels are connected
    clk = 17
    dt = 18

    # Initialize the GPIO's that will be used in the Raspberry Pi
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # Read the encoder and send position to stream
    n = 0
    position = 0
    clkLastState = GPIO.input(clk)
    sleep_s = None if args.period is None else args.period / 1000
    try:
        while True:
            # Update encoder position
            clkState = GPIO.input(clk)
            dtState = GPIO.input(dt)
            if clkState != clkLastState:
                if dtState != clkState:
                    position += 1
                else:
                    position -= 1
            clkLastState = clkState

            # Create json object that will be sent
            obj = {}
            obj["sensor"] = 1
            obj["value"] = position
            obj["timestamp"] = str(datetime.datetime.now())
            obj["sequence"] = n
            n += 1

            # Convert dictionary to json
            json_str = json.dumps(obj)

            # Send into stream
            try:
                kinesis_client.put_record(StreamName=stream_name, Data=json_str, PartitionKey=":)")
                print("{}. Sent encoder position {} into stream '{}'.".format(n, obj["value"],
                                                                              stream_name))
            except Exception as e:
                print("Encountered an exception while trying to put record sensor data into "
                      "stream '{}'.".format(stream_name))
                print("Exception: {}.".format(e))

            if sleep_s is not None:
                # print("Sleeping for {} milliseconds.".format(args.period))
                time.sleep(sleep_s)
    # When the program ends (because Ctrl+C or other), make sure to clean GPIOs
    finally:
        GPIO.cleanup()


if __name__ == '__main__':
    main()
