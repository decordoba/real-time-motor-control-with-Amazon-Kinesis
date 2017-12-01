from Adafruit_MotorHAT import Adafruit_MotorHAT
from RPi import GPIO
import argparse
import boto3
import datetime
import json
import numpy as np
import threading
import time


"""
This program will send random values to the motor, and read what the encoder receives.
Then, it will send ipairs of values (motors and encoders) to a stream.
The encoder needs to be read as fast as possible to make sure that we don't miss any frame.
For this reason, we are using a separate thread to read the encoder and update its position.
Then we have another thread to write a position into the motor every ms and read the encoder
value. Finally, we will stream such values at a periodic, lower-frequency rate.
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
    parser.add_argument("--motor", "-m", dest="motor", default=1, type=int, help="The motor "
                        "that is being controlled. Default is 1.", choices=[1, 2, 3, 4])
    parser.add_argument("-mp", "--motor_period", dest="motor_period", type=int,
                        help="Period to wait between every time we write to the motor. "
                        "Default is 1 ms.", default=1, metavar="MILLISECONDS",)
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
    # Parse encoder as fast as possible
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

    def get_angle(self):
        pos = self.position % 360
        if pos > 180:
            return 360 - pos
        return pos

    def status(self):
        # Create json object that will be sent
        obj = {}
        obj["msg_type"] = self.message_type
        obj["value"] = self.get_angle()
        obj["timestamp"] = str(datetime.datetime.now())
        obj["sequence"] = self.message_number
        obj["counter"] = self.counter
        self.message_number += 1

        # Convert dictionary to json and return it
        return json.dumps(obj)

    def value(self):
        # Return value in degrees
        return self.get_angle(), self.counter

    def stop(self):
        self.stop_event.set()


class motor_writer(threading.Thread):
    # Write motor and read encoder, and save both values into a list
    def __init__(self, motor, encoder_reader, num_samples=10000, period_ms=1, message_type=3):
        threading.Thread.__init__(self)

        # Save inputs
        self.motor_number = motor
        self.reader = encoder_reader
        self.num_samples = num_samples
        self.period = period_ms / 1000  # self.period is in seconds
        self.message_type = message_type

        # Create default object to control the motor using the MototrHAT (I2C)
        self.mh = Adafruit_MotorHAT(addr=0x60)

        # Create motor variable
        self.motor = self.mh.getMotor(self.motor_number)

        # Create motor values (vector of values that will be sent to motor)
        self.create_motor_values(length_values=self.num_samples)

        # Create variable to store motor and encoder data
        self.json_list = []
        self.json_idx = 0
        self.message_number = 0

        # Create variables to move motor more efficiently
        self.prev_direction = None
        self.prev_speed = None

        # Create variable to stop thread
        self.stop_event = threading.Event()

    def turn_off_motors(self):
        # Stop all motors
        self.mh.getMotor(1).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(2).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(3).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(4).run(Adafruit_MotorHAT.RELEASE)

    def move_motor(self, speed):
        dire = 1
        if speed < 0:
            speed = -speed
            dire = -1
        if speed > 255:
            speed = 255
        if dire != self.prev_direction:
            self.motor.run(Adafruit_MotorHAT.FORWARD if dire == 1 else Adafruit_MotorHAT.BACKWARD)
            self.prev_direction = dire
        if speed != self.prev_speed:
            self.motor.setSpeed(speed)
            self.prev_speed = speed

    def create_motor_values(self, length_values=10000, num_sine_waves=5, range_values=(-255, 255)):
        # Create random motor values vector using several sine waves
        self.motor_values = np.zeros(length_values)
        t = np.arange(0.0, 1, 1 / length_values)
        for i in range(num_sine_waves):
            period = np.random.rand() * 9 + 1
            self.motor_values += np.sin(2 * np.pi * t * period)
        minv = np.min(self.motor_values)
        self.motor_values -= minv
        maxv = np.max(self.motor_values)
        self.motor_values *= ((range_values[1] - range_values[0]) / maxv)
        self.motor_values += range_values[0]

    def run(self):
        # Move motor pseudo-randomly and save encoder and motor values
        self.counter = 0
        try:
            while not self.stop_event.is_set():
                # Calculate termination time
                terminate_time = datetime.datetime.now() + datetime.timedelta(seconds=self.period)
                # Active wait, but apparently time.sleep has an accuracy of ~1ms
                while datetime.datetime.now() < terminate_time:
                    pass
                encoder_value, i = self.reader.value()
                motor_value = self.motor_values[self.counter]
                self.move_motor(motor_value)
                print(motor_value, encoder_value)
                self.add_json_to_list(encoder_value, motor_value, i)
                self.counter += 1
                if self.counter > self.num_samples:
                    break
            self.turn_off_motors  # Release motors when stopped
        finally:
            # When the program ends after an exception (Ctrl+C or other), release motors
            self.turn_off_motors()

    def add_json_to_list(self, encoder_value, motor_value, encoder_counter=0):
        # Create json object that will be sent
        obj = {}
        obj["msg_type"] = self.message_type
        obj["encoder"] = encoder_value
        obj["motor"] = motor_value
        obj["timestamp"] = str(datetime.datetime.now())
        obj["encoder_counter"] = encoder_counter
        obj["motor_counter"] = self.counter
        self.json_list.append(obj)

    def status(self):
        last = self.counter
        obj = self.json_list[self.json_idx:self.counter]
        self.json_idx = last
        self.message_number += 1
        # Convert dictionary to json and return it
        return json.dumps(obj)

    def value(self):
        # Return motor value
        return self.motor_values[self.counter], self.counter

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
    reader = encoder_reader(args.clk, args.dt)
    reader.start()

    # Start thread to change motor's position
    writer = motor_writer(args.motor, reader, period_ms=args.motor_period)
    writer.start()

    # Send encoder values into stream at args.period rate
    sleep_s = 0.0 if args.period is None or args.period < 0 else args.period / 1000.0
    try:
        while True:
            encoder_motor_str = writer.status()
            try:
                kinesis_client.put_record(StreamName=stream_name, Data=encoder_motor_str,
                                          PartitionKey=";P")
                print("Sent encoder message {} into stream '{}'.".format(encoder_motor_str,
                                                                         stream_name))
            except Exception as e:
                print("Encountered an exception while trying to put record sensor data into "
                      "stream '{}'.".format(stream_name))
                print("Exception: {}.".format(e))
            time.sleep(sleep_s)
    finally:
        writer.stop()
        reader.stop()


if __name__ == '__main__':
    main()
