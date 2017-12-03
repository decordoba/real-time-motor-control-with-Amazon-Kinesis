from Adafruit_MotorHAT import Adafruit_MotorHAT
from RPi import GPIO
import argparse
import boto3
import datetime
import json
import threading
import time


"""
This program will implement a PID controller for a motor and an encoder.
The goal position of the motor will be obtained from a stream, as well as the pid constants.
It will also send pairs of values (motors and encoders) to a stream.
The encoder needs to be read as fast as possible to make sure that we don't miss any frame.
For this reason, we are using a separate thread to read the encoder and update its position.
We have another thread to write a position into the motor according to the PID controller.
Finally, we will stream such values at a periodic, lower-frequency rate.
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
                        help="Period to wait between every stream transmition. "
                        "If not set, data will be sent as fast as possible.",
                        metavar="MILLISECONDS",)
    parser.add_argument("--clk", dest="clk", default=17, help="The GPIO where our encoder's clk "
                        "wire will be connected. Default is 17.", metavar="GPIO_NUMBER",)
    parser.add_argument("--dt", dest="dt", default=18, help="The GPIO where our encoder's dt "
                        "wire will be connected. Default is 18.", metavar="GPIO_NUMBER",)
    parser.add_argument("-m", "--motor", dest="motor", default=1, type=int, help="The motor "
                        "that is being controlled. Default is 1.", choices=[1, 2, 3, 4])
    parser.add_argument("-mp", "--motor_period", dest="motor_period", type=int,
                        help="Period to wait every time we write to the motor. "
                        "Default is 1 ms.", default=1, metavar="MILLISECONDS",)
    defaults = (1.0, 0.0, 0.0)  # For P, I, D
    parser.add_argument("-pc", "--p_constant", dest="p_constant", default=defaults[0],
                        type=float, help="Initial P constant. Default is {}.".format(defaults[0]))
    parser.add_argument("-ic", "--i_constant", dest="i_constant", default=defaults[1],
                        type=float, help="Initial I constant. Default is {}.".format(defaults[1]))
    parser.add_argument("-dc", "--d_constant", dest="d_constant", default=defaults[2],
                        type=float, help="Initial D constant. Default is {}.".format(defaults[2]))
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
    def __init__(self, clk, dt, one_turn_value=500, message_type=0):
        threading.Thread.__init__(self)

        # Save inputs
        self.clk = clk
        self.dt = dt
        self.message_type = message_type
        self.one_turn_value = one_turn_value

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
        finally:
            # When the program ends after an exception (Ctrl+C or other), make sure to clean GPIOs
            GPIO.cleanup()

    def get_angle(self):
        # Calculate angle in degrees (from -180 to 180)
        pos = int((self.position % self.one_turn_value) / self.one_turn_value * 360)
        if pos > 180:
            return pos - 360
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
    def __init__(self, motor, encoder_reader, period_ms=1, encoder_sample_diff=1, p=1, i=0, d=0):
        threading.Thread.__init__(self)

        # Save inputs
        self.motor_number = motor
        self.reader = encoder_reader
        self.period_ms = period_ms
        self.period = datetime.timedelta(seconds=self.period_ms / 1000)

        # Create default object to control the motor using the MototrHAT (I2C)
        self.mh = Adafruit_MotorHAT(addr=0x60)

        # Create motor variable
        self.motor = self.mh.getMotor(self.motor_number)

        # Create variable to store motor and encoder data
        self.message_number = 0

        # Create variables to move motor more efficiently
        self.prev_direction = None
        self.prev_speed = None

        # Create variables PID motor
        self.p = p
        self.i = i
        self.d = d
        self.goal_value, _ = self.reader.value()  # set initial goal to current encoder position
        self.min_encoder_sample_difference = encoder_sample_diff if encoder_sample_diff > 0 else 1

        # Create variable to stop thread
        self.stop_event = threading.Event()

    def turn_off_motors(self):
        # Stop all motors
        self.mh.getMotor(1).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(2).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(3).run(Adafruit_MotorHAT.RELEASE)
        self.mh.getMotor(4).run(Adafruit_MotorHAT.RELEASE)

    def move_motor(self, speed):
        # Make motor move in selected speed and direction
        dire = 1
        speed = int(speed)
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

    def update_pid_constants(self, p=None, i=None, d=None):
        if p is not None:
            self.p = p
        if i is not None:
            self.i = i
        if d is not None:
            self.d = d

    def update_goal_value(self, goal):
        if goal > 180:
            goal = 180
        if goal < -180:
            goal = -180
        self.goal_value = goal

    def get_pid(self):
        # Get encoder value 1 and timestamp 1
        encoder_value1, id1 = self.reader.value()
        time1 = datetime.datetime.now()
        # Calculate termination time
        terminate_time = time1 + self.period
        # Active wait, because apparently time.sleep has an accuracy of ~1ms
        while datetime.datetime.now() < terminate_time:
            pass
        id2 = id1 - 1
        # Wait until self.min_encoder_sample_difference samples have gone
        while id2 - id1 < self.min_encoder_sample_difference:
            # Get encoder value 2 and timestamp 2
            encoder_value2, id2 = self.reader.value()
            time2 = datetime.datetime.now()
        # Calculate PID values and return motor speed
        time_diff = (time2 - time1).total_seconds()
        proportional = self.p * (encoder_value2 - self.goal_value)
        derivative = self.d * (encoder_value2 - encoder_value1) / (time_diff)
        integral = 0 * self.i
        # print("FINAL IDS", id1, id2)
        # print(self.p, self.i, self.d)
        # print(self.goal_value)
        # print("Diff time", time_diff)
        # print(proportional, derivative, integral)
        print(encoder_value1, encoder_value2)
        return proportional + derivative + integral

    def run(self):
        # Move motor pseudo-randomly and save encoder and motor values
        self.counter = 0
        try:
            while not self.stop_event.is_set():
                motor_value = self.get_pid()
                self.move_motor(motor_value)
                # self.add_json_to_list(motor_value)
                self.counter += 1
        finally:
            # When the program ends after an exception or naturally, release motors
            self.turn_off_motors()
            self.stop()

    def status(self):
        obj = self.counter
        self.message_number += 1
        # Convert dictionary to json and return it
        return json.dumps(obj)

    def stop(self):
        self.stop_event.set()

    def finished(self):
        return self.stop_event.is_set()


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

    # Start thread to monitor encoder's position
    reader = encoder_reader(args.clk, args.dt)
    reader.start()

    # Start thread to change motor's position according to PID
    writer = motor_writer(args.motor, reader, period_ms=args.motor_period,
                          p=args.p_constant, i=args.i_constant, d=args.d_constant,
                          encoder_sample_diff=1)
    writer.start()

    # Receive pid config from 'stream in' and send pid progress into 'stream out'
    max_num_records = 10000
    sleep_s = 0.0 if args.period is None or args.period < 0 else args.period / 1000.0
    try:
        while not writer.finished():
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

                # If we receive goal_postion (if we get a message of type 2)
                if obj["msg_type"] == 2:
                    goal_pos = obj["value"]
                    writer.update_goal_value(goal_pos)
                # If we receive pid information (if we get a message of type 4)
                elif obj["msg_type"] == 4:
                    p = obj["p"]
                    i = obj["i"]
                    d = obj["d"]
                    writer.update_pid_constants(p, i, d)

                # # Send data
                # obj["value"] = (obj["value"] % 360)  # transform values from linear to degrees
                # obj["value"] = obj["value"] - 360 if obj["value"] > 180 else obj["value"]
                # obj["value"] = (obj["value"] - goal_pos) * p_constant  # P transformation
                # obj["msg_type"] = 1  # type 1 refers to motor data
                # obj["timestamp2"] = str(datetime.datetime.now())  # Add new timestamp

                # # Send object in output stream
                # json_str_out = json.dumps(obj)

                # # Send into stream
                # try:
                #     kinesis_client.put_record(StreamName=stream_name_out, Data=json_str_out,
                #                               PartitionKey="123")
                #     print("Received: '{}' from stream '{}'.".format(json_str_in, stream_name_in))
                #     print("Sent:     '{}' into stream '{}'.".format(json_str_out, stream_name_out))
                # except Exception as e:
                #     print("Encountered an exception while trying to put record '{}'"
                #           " into stream '{}'.".format(stream_name_out))
                #     print("Exception: {}.".format(json_str_out, e))

                # Wait delay
                time.sleep(sleep_s)
    finally:
        writer.stop()
        reader.stop()


if __name__ == '__main__':
    main()
