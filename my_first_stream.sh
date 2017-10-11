#!/bin/bash

# For this to work, you have to install awscli, and configure keys, region and format using 'aws configure'
# Read this to get started: https://docs.aws.amazon.com/streams/latest/dev/kinesis-tutorial-cli-installation.html

# Source code: https://docs.aws.amazon.com/streams/latest/dev/learning-kinesis.html

stream_name="realtime1"

# create stream
echo "Creating stream $stream_name..."
aws kinesis create-stream --stream-name $stream_name --shard-count 1

# get description stream
echo -e "\nStream $stream_name description..."
aws kinesis describe-stream --stream-name $stream_name

# list all streams available
echo -e "\nStreams list..."
aws kinesis list-streams

# wait 30 seconds, because stream is being created
echo -e "\nSleeping 30 seconds, while stream $stream_name is being created..."
sleep 30

# put data in stream (in this case, 'testdata')
data_sent="testdata"
echo -e "\nPutting data $data_sent in stream $stream_data..."
aws kinesis put-record --stream-name $stream_name --partition-key 123 --data $data_sent

# get shard-iterator: identifier of my shard
shard_id="shardId-000000000000"
echo -e "\nGetting shard iterator from stream $stream_name and shard-id $shard_id..."
shard_iterator=$(aws kinesis get-shard-iterator --shard-id shardId-000000000000 --shard-iterator-type TRIM_HORIZON --stream-name $stream_name --query 'ShardIterator')
echo $shard_iterator

# get data from shard-iterator (returned in base64 encoding)
echo -e "\nReading data from shard-iterator..."
aws kinesis get-records --shard-iterator $shard_iterator

# delete stream
echo -e "\nDeleting stream $stream_name..."
aws kinesis delete-stream --stream-name $stream_name

# see how the stream is being deleted
echo -e "\nStream $stream_name description..."
aws kinesis describe-stream --stream-name $stream_name

