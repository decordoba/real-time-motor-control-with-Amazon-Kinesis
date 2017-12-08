# real-time-motor-control-with-Amazon-Kinesis

Create streams, send and receive data from them, and find out what they can do using Python!

This repository contains a lot of codes to play with streams (in general producers write into a stream, and consumers read from them),
and it also contains some instructions to install aws in your system.

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

This is just so you can get started. Create a new stream with `python3 stream_producer.py -s my_stream`, send data to it with `python3 json_producer.py -s my_stream -p 500` and
read from it with `python3 stream_consumer.py -s my_stream -p 100`.