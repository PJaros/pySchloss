#!/bin/bash

#inputs
echo "24" > /sys/class/gpio/export
echo "25" > /sys/class/gpio/export
#outputs
echo "18" > /sys/class/gpio/export
echo "23" > /sys/class/gpio/export

sleep 1

#inputs
echo "in" > /sys/class/gpio/gpio24/direction
echo "in" > /sys/class/gpio/gpio25/direction
#invert values
echo 1 > /sys/class/gpio/gpio24/active_low
echo 1 > /sys/class/gpio/gpio25/active_low

#outputs
echo "out" > /sys/class/gpio/gpio18/direction
echo "out" > /sys/class/gpio/gpio23/direction
