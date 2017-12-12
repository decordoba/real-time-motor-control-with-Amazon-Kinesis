from RPi import GPIO
from time import sleep


"""
Setup:
Your encoder should have 4 wires:
    * GND: Connect to GND
    * Vcc: Connect to 5V
    * A Vout: Connect to clk
    * B Vout: Connect to dt

In my case, I am using the JGA25-371 motor, which has an encoder and a motor.
This motor has 6 wires:
    * Motor GND (Black): DO NOT CONNECT TO Raspberry Pi, USE H-BRIDGE
    * Motor Vcc (Red):   DO NOT CONNECT TO RPi, USE H-BRIDGE
    * GND (Green):       Connect to RPi Gnd
    * Vcc (Blue):        Connect to RPi 5V
    * A Vout (Yellow):   Connect to RPi GPIO17
    * B Vout (White):    Connect to RPi GPIO18

Then, run the program. The position that the program starts with is position 0,
and as the encoder turns, the number is increased or decreaded, depending on the
direction. Every time the position changes, the new number is printed.
"""

# select where the two data channels are connected
clk = 17
dt = 18

# initialize GPIO's that will be used
GPIO.setmode(GPIO.BCM)
GPIO.setup(clk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(dt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# loop forever to monitor encoder position
counter = 0
clkLastState = GPIO.input(clk)
try:
    print("Encoder monitor started!")
    print("Position: {}".format(counter))
    while True:
        clkState = GPIO.input(clk)
        dtState = GPIO.input(dt)
        if clkState != clkLastState:
            if dtState != clkState:
                counter += 1
            else:
                counter -= 1
            print("Position: {}".format(counter))
        clkLastState = clkState
finally:
    GPIO.cleanup()
