from RPi import GPIO
import argparse
import datetime
import json
import socket
import time


"""
This program will send the state of the encoder as fast as possible through an UDP connection.
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
    parser = argparse.ArgumentParser("Send encoder data as json objects through a UDP connection.")
    parser.add_argument("-p", "--period", dest="period", type=int, default=None,
                        help="Period to wait between every encoder parse. If not set, the encoder"
                        " will be parsed as fast as possible.", metavar="MILLISECONDS",)
    parser.add_argument("--ip", dest="ip", default="localhost", help="Connection IP. Default is"
                        "localhost.", metavar="IP_ADDRESS")
    parser.add_argument("--port", dest="port", default=9999, type=int, help="Connection port. "
                        "Default is 9999.", metavar="PORT")
    return parser.parse_args()


def main():
    args = create_parser()

    # Create UDP socket
    addr = (args.ip, args.port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # SOCK_DGRAM means UDP

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

            # Send to UDP connection
            sock.sendto(json_str.encode(), addr)
            print("{}. Sent encoder position {} into address {}:{}.".format(n, obj["value"],
                                                                            addr[0], addr[1]))

            if sleep_s is not None:
                time.sleep(sleep_s)
    # When the program ends (because Ctrl+C or other), make sure to clean GPIOs
    finally:
        GPIO.cleanup()


if __name__ == '__main__':
    main()
