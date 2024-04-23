#!/bin/bash

while :
do
cat /sys/class/gpio/gpio24/value > /sys/class/gpio/gpio18/value
cat /sys/class/gpio/gpio25/value > /sys/class/gpio/gpio23/value
echo "the ultimate infinite enterprise loop"
sleep 1
done
