from RPi import GPIO
import argparse
import boto3
import datetime
import json
import threading
import time


"""
This program will send the state of the encoder at a selected rate.
The encoder needs to be read as fast as possible to make sure that we don't miss any frame.
For this reason, we are using a separate thread to read the encoder and update its position,
and we will stream such position at a periodic, lower-frequency rate.
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
                        help="Period to wait between every stream transmition. "
                        "If not set, data will be sent as fast as possible.",
                        metavar="MILLISECONDS",)
    parser.add_argument("--clk", dest="clk", default=17, help="The GPIO where our encoder's clk "
                        "wire will be connected. Default is 17.", metavar="GPIO_NUMBER",)
    parser.add_argument("--dt", dest="dt", default=18, help="The GPIO where our encoder's dt "
                        "wire will be connected. Default is 18.", metavar="GPIO_NUMBER",)
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


class encoder_reader(threading.Thread):
    # Parse encoder as fast as possible, and if
    def __init__(self, clk, dt, message_type=0):
        threading.Thread.__init__(self)

        # Save inputs
        self.clk = clk
        self.dt = dt
        self.message_type = message_type

        # Initialize the GPIO's that will be used in the Raspberry Pi
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.clk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.dt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        # Create required variables
        self.position = 0
        self.counter = 0
        self.message_number = 0

        # Create variable to stop thread
        self.stop_event = threading.Event()

    def run(self):
        clk_last_state = GPIO.input(self.clk)
        # Update encoder position
        try:
            while not self.stop_event.is_set():
                clk_state = GPIO.input(self.clk)
                dt_state = GPIO.input(self.dt)
                if clk_state != clk_last_state:
                    if dt_state != clk_state:
                        self.position += 1
                    else:
                        self.position -= 1
                clk_last_state = clk_state
                self.counter += 1
            GPIO.cleanup()  # Clean GPIOs when stopped
        finally:
            # When the program ends after an exception (Ctrl+C or other), make sure to clean GPIOs
            GPIO.cleanup()

    def status(self):
        # Create json object that will be sent
        obj = {}
        obj["msg_type"] = self.message_type
        obj["value"] = self.position
        obj["timestamp"] = str(datetime.datetime.now())
        obj["sequence"] = self.message_number
        obj["counter"] = self.counter
        self.message_number += 1

        # Convert dictionary to json and return it
        return json.dumps(obj)

    def stop(self):
        self.stop_event.set()


def main():
    args = create_parser()

    # Create and connect to stream
    stream_name = args.stream_name
    print("Connecting to stream '{}' in region '{}'.".format(stream_name, args.region))
    kinesis_client = boto3.client('kinesis', region_name=args.region)
    if not connect_to_stream(kinesis_client, stream_name):
        return

    # Start thread to monitor encoder's position
    reader = encoder_reader(args.clk, args.dt, message_type=0)  # type 0 refers to encoder data
    reader.start()

    # Send encoder values into stream at args.period rate
    sleep_s = 0.0 if args.period is None or args.period < 0 else args.period / 1000.0
    try:
        while True:
            encoder_str = reader.status()
            try:
                kinesis_client.put_record(StreamName=stream_name, Data=encoder_str,
                                          PartitionKey=";P")
                print("Sent encoder message {} into stream '{}'.".format(encoder_str, stream_name))
            except Exception as e:
                print("Encountered an exception while trying to put record sensor data into "
                      "stream '{}'.".format(stream_name))
                print("Exception: {}.".format(e))
            time.sleep(sleep_s)
    finally:
        reader.stop()


if __name__ == '__main__':
    main()
