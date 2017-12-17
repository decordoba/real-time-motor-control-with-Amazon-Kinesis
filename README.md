# real-time-motor-control-with-Amazon-Kinesis

Create streams, send and receive data from them, and find out what they can do using Python 3 and the boto 3 library!

This repository contains a lot of codes to play with streams (in general producers write into a stream, and consumers read from them),
and it also contains some instructions to install aws in your system.

You  will also find several programs to work with an encoder and a DC motor in a Raspberry Pi. This program can be used to build a distributed control system on the cloud,
where the motor can be controlled and monitored remotely using streams.

## Steps to install

1. Make sure you can run the commands in `my_first_stream.sh`. For this, you will need to install awscli and configure keys, region and format using 'aws configure'.
Read this to get started: https://docs.aws.amazon.com/streams/latest/dev/kinesis-tutorial-cli-installation.html

2. If you are in a Raspberry Pi and want to use our motor- encoder pair system, follow the instructions in `getting_started.txt` to install all required packages to control
the motor and encoder. We recommend using some kind of motor shield to connect the motor to the board, although it can also be done directly. Remember to power the motor from
an external source!

3. If you installed everything, you should be able to run all codes using Python 3. Remember you can always use the `-h` option to learn more about every code.
For example: `python3 my_code.py -h`.

4. `instructions_for_demo.txt` shows some of the codes with the best options, and what codes work best together. A better explanation about what every program does can be found there.

## Getting started

This is just so you can get started. Create a new stream with `python3 stream_producer.py -s my_stream`, send data to it every 500 ms with `python3 json_producer.py -s my_stream -p 500`
and read its contents and print them every 100 ms with `python3 stream_consumer.py -s my_stream -p 100`.

## Files

### Stream Specific Files

**`stream_producer.py`:** Creates a stream, whose name can be chosen with the `-s` argument. A region can be selected with the `-r` argument. If one or more words are passed to it with the `-w` argument,
it will send these words once into the stream. A period in ms can be set with the `-p` argument, which will make it send the selected words every period. If no words are given it will send increasing numbers.

**`stream_consumer.py`:** Reads a stream, whose name can be selected with the `-s` argument, and prints its contents in the terminal. A region can be selected with the `-r` argument.
If a period in ms is chosen with the `-p` argument, it will continue to read the stream at the selected rate and print the new data received. The `-sit` argument can be used to choose the
shard iterator type. Use `"LATEST"` to see only the data received after starting to read the stream, or omit this parameter to see all the data pushed to the stream since its creation.

**`delete_streams.py`:** Deletes all existing streams, or deletes only one stream using the `-s` argument followed by the name of the stream that will be deleted. A region can be specified with the `-r` argument.

**`json_producer.py`:** Creates a stream, and sends a json object with random data into it. The object has four fields: a `msg_type`, a `value`, a `sequence` number and a `timestamp`.
Again, the stream name is chosen with `-s`, and the region with `-r`. The `-p` argument can be used to set a constant rate at which to send messages into the stream, in ms. The `--silent` flag
can be used to mute the notification every time a message is sent.

**`json_consumer.py`:** Monitors a stream for a number of seconds, and plots graphs with statistics about the delay observed. Expects a stream receiving json objects with the field `timestamp`
in them, like the ones sent by `json_producer.py`. Again, the stream name is chosen with `-s`, and the region with `-r`. The `-p` argument can be used to set a constant rate at which
to get the contents of the stream, in ms. This rate will (obviously) affect the results shown in the statistics. Choose the time in seconds to monitor the stream before plotting with the `-t` argument.
Choose the number of json objects to read before stopping monitoring with the `-m` argument. Use the `--noplot` flag to stop plotting, and the `-f` argument to select the filename to save the data as
an `.npy` file. If `-f` is not set, the data will not be saved.

### Files aimed to be used with a Motor and/or the Encoder

**`encoder_demo.py`:** Demonstration code to print the values of an encoder. Plug your encoder to a Raspberry Pi, connect the DT and CLK wires to the 17 and 18 GPIOs of the RPi, and
make sure that the values printed make sense. This program does not take arguments.

**`encoder_thread_producer.py`:** Reads encoder constantly in a thread, and sends its position into a selected stream in a json object (similar to the one described in `json_producer.py`). Again, the stream name is chosen with `-s`, and the region with `-r`.
The `-p` argument can be used to set the period in ms at which to send data, if unset data will be sent as fast as possible. The CLK and DT connection GPIO numbers can be selected with the arguments
`-clk` and `-dt`.

**`motor_consumer.py`:** Reads a stream and sends the received voltage to a DC motor. Again, the stream name is chosen with `-s`, and the region with `-r`.
The `-p` argument can be used to set the period in ms at which to read the stream, if unset the stream will be read as fast as possible. The motor number (supposing a motor shield is used)
can be chosen with the argument `--motor`. Use `motor_producer.py` to move the motor at a chosen speed manually.

**`motor_producer.py`:** Prompts the user with a dialogue to choose the speed to move a motor listening to a stream. Start a `motor_consumer` listening at a stream and use
this program to send the speed and direction that we want to make the motor go to such stream, selecting a number from -255 to 255.
Again, the stream name is chosen with `-s`, and the region with `-r`.

**`encoder_motor_converter.py`:** Listens to a stream `-sin` where encoder values will be sent, converts these values into motor values with a simple PID control system,
and sends those values to a stream `-sout`, to move the motor accordingly. Regions can be selected with `-rin` and `-rout`. The rate at which the input stream is read
can be controlled with `-p`, or it will be read as fast as possible if `-p` is omitted. To omit the program prints when receiving encoder data, use the `--silent` flag.

**`pid_controller.py`:** PID motor controller, receives encoder values, applies a PID transformation and moves the motor accordingly trying to reach an angular goal position of the DC motor.
Listens to a stream (chosen with `-sin`, in region `-rin`) constantly to update the motor goal position and PID constants it uses. The rate at which the input stream is read
can be controlled with `-p`, or it will be read as fast as possible if `-p` is omitted. The encoder's CLK and DT connection GPIO numbers can be selected with the arguments
`-clk` and `-dt`, and the motor number can be selected with the `-m` argument. The initial P, I and D constants can be chosen using `-pc`, `-ic` and `-dc`. Works best with 
`pid_producer.py` and `goal_producer.py`, which can be used to manually change the PID constants and goal position respectively.

**`pid_producer.py`:** Prompts the user with a dialogue to change the P, I and D constants used in the PID controller, and sends those changes into a stream.
Start a `pid_controller` listening at this stream and use this program to modify the PID constants used by it.
Again, the stream name is chosen with `-s`, and the region with `-r`.

**`goal_producer.py`:** Prompts the user with a dialogue to change the goal position used in the PID controller, and sends such value into a stream.
Start a `pid_controller` listening at this stream and use this program to modify the goal position where we want to move the motor.
Again, the stream name is chosen with `-s`, and the region with `-r`.

**`motor_encoder_producer.py`:** Program for system identification in a motor-encoder system. Assigns random values to the motor, reads the encoder values, and
sends both values into a stream constantly for `-ns` samples.

This repository contains other files not mentioned here, but all of them are variations of the ones described above. To learn how to use these, please use the `-h` option or look into their code
(often the comments are useful to see my success with them, or their goal).