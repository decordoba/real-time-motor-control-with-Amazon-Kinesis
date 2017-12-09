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

**`stream_producer.py`:** Creates a stream, whose name can be chosen with the `-s` argument. A region can be selected with the `-r` argument. If one or more words are passed to it with the `-w` argument,
it will send these words once into the stream. A period in ms can be set with the `-p` argument, which will make it send the selected words every period. If no words are given it will send increasing numbers.

**`stream_consumer.py`:** Reads a stream, whose name can be selected with the `-s` argument, and prints its contents in the terminal. A region can be selected with the `-r` argument.
If a period in ms is chosen with the `-p` argument, it will continue to read the stream at the selected rate and print the new data received. The `-sit` argument can be used to choose the
shard iterator type. Use `"LATEST"` to see only the data received after starting to read the stream, or omit this parameter to see all the data pushed to the stream since its creation.

**`delete_stream.py`:** Deletes all existing streams, or deletes only one stream using the `-s` argument followed by the name of the stream that will be deleted. A region can be specified with the `-r` argument.

**`json_producer.py`:** Creates a stream, and sends a json object with random data into it. The object has four fields: a `msg_type`, a `value`, a `sequence` number and a `timestamp`.
Again, the stream name is chosen with `-s`, and the region with `-r`. The `-p` argument can be used to set a constant rate at which to send messages into the stream, in ms. The `--silent` flag
can be used to mute the notification every time a message is sent.

**`json_consumer.py`:** Monitors a stream for a number of seconds, and plots graphs with statistics about the delay observed. Expects a stream receiving json objects with the field `timestamp`
in them, like the ones sent by `json_producer.py`. Again, the stream name is chosen with `-s`, and the region with `-r`. The `-p` argument can be used to set a constant rate at which
to get the contents of the stream, in ms. This rate will (obviously) affect the results shown in the statistics. Choose the time in seconds to monitor the stream before plotting with the `-t` argument.
Choose the number of json objects to read before stopping monitoring with the `-m` argument. Use the `--noplot` flag to stop plotting, and the `-f` argument to select the filename to save the data as
an `.npy` file. If `-f` is not set, the data will not be saved.
