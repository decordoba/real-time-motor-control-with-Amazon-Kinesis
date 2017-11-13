import argparse
import atexit
import boto3
import json
import time
from Adafruit_MotorHAT import Adafruit_MotorHAT


def create_parser():
    parser = argparse.ArgumentParser("""
Read and print the contents of a selected stream as fast as possible, and plot performance.
""")
    parser.add_argument("-s", "--stream", dest="stream_name", required=True,
                        help="The stream you'd like to create.", metavar="STREAM_NAME",)
    parser.add_argument("-r", "--regionName", "--region", dest="region", default="us-east-1",
                        help="The region you'd like to make this stream in. Default is "
                        "'us-east-1'", metavar="REGION_NAME",)
    parser.add_argument("-p", "--period", dest="period", type=int, default=None,
                        help="How often to read stream. Default is 0.", metavar="MILLISECONDS",)
    choices = ["LATEST", "TRIM_HORIZON"]
    parser.add_argument("-sit", "--shard_iterator_type", dest="shard_iterator_type", type=str,
                        default=choices[0], choices=choices, help="Select what data will be "
                        "returned from stream every query. Options are "
                        "{}. Default is '{}'.".format(choices, choices[0]),
                        metavar="SHARD_ITERATOR_TYPE")
    parser.add_argument("--motor", "-m", dest="motor", default=1, type=int, help="The motor "
                        "that is being controlled. Default is 1.", choices=[1, 2, 3, 4])
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
            print("The stream '{}' has status {}, please rerun the script when the stream "
                  "is ACTIVE.".format(stream_name))
            return
        else:
            shard_id = stream_description["StreamDescription"]["Shards"][0]["ShardId"]
    except:
        # We assume the stream didn't exist so we will try to create it with just one shard
        print("The stream '{}' was not found, please rerun the script when the stream has "
              "been created.".format(stream_name))
        return

    # If we reach this point, the string is active
    shard_iterator_type = args.shard_iterator_type
    shard_iterator = kinesis_client.get_shard_iterator(StreamName=stream_name, ShardId=shard_id,
                                                       ShardIteratorType=shard_iterator_type)["ShardIterator"]

    # Create default object to control the motor using the MototrHAT (I2C)
    mh = Adafruit_MotorHAT(addr=0x60)

    # Create motor variable
    motor = mh.getMotor(args.motor)

    # Make sure all motors will be auto-disable on shutdown
    def turnOffMotors():
        mh.getMotor(1).run(Adafruit_MotorHAT.RELEASE)
        mh.getMotor(2).run(Adafruit_MotorHAT.RELEASE)
        mh.getMotor(3).run(Adafruit_MotorHAT.RELEASE)
        mh.getMotor(4).run(Adafruit_MotorHAT.RELEASE)
    atexit.register(turnOffMotors)

    # Read stream forever and move motor at the received speed
    max_num_records = 10000
    sleep_s = 0.0 if args.period is None or args.period < 0 else args.period / 1000.0
    prev_speed = None
    prev_direction = None
    while True:
        try:
            records = kinesis_client.get_records(ShardIterator=shard_iterator,
                                                 Limit=max_num_records)
            shard_iterator = records["NextShardIterator"]  # Update shard_iterator
            # Move motor at speed received
            if len(records["Records"]) > 0:
                last_record = records["Records"][-1]["Data"]
                speed = int(json.loads(last_record.decode("utf-8"))["value"])
                direction = 1
                if speed < 0:
                    speed = -speed
                    direction = -1
                if speed == 999:
                    # 999 speed will release the motors
                    motor.run(Adafruit_MotorHAT.RELEASE)
                    prev_speed = speed
                    prev_direction = 0
                else:
                    if speed > 255:
                        speed = 255
                    if direction != prev_direction:
                        motor.run(Adafruit_MotorHAT.FORWARD if direction == 1 else Adafruit_MotorHAT.BACKWARD)
                    prev_direction = direction
                    if speed != prev_speed:
                        motor.setSpeed(speed)
                    prev_speed = speed
            time.sleep(sleep_s)
        except Exception as e:
            time.sleep(0.01)


if __name__ == '__main__':
    main()
