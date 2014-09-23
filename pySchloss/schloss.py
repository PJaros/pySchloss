#!/usr/bin/python2
# -*- coding: utf-8 -*-
from threading import Thread, Lock
from os.path import expanduser
from string import strip
import logging

import subprocess
import re
import os
import sys
import distutils.spawn
from optparse import OptionParser
import threading
import time

hcitool_cmd =["cc", "auth", "dc"]

gpio_in_file = "/sys/class/gpio/gpio24/value"
gpio_out_file = "/sys/class/gpio/gpio18/value"

checking_proximity = False
light_lock = Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

btdevice_path = distutils.spawn.find_executable("bt-device")
bluetoothctl_path = distutils.spawn.find_executable("bluetoothctl")
hcitool_path = distutils.spawn.find_executable("hcitool")

if not os.geteuid() == 0:
    sys.exit("This program needs root rights to work")

def switch_door_state():
    global door_state
    door_state = not door_state
    set_door_state()

def paired_device_btadapter(btdevice_path=btdevice_path):
    "Listed die gepairten Geräte per 'bt-adapter -l'"
    out = subprocess.check_output([btdevice_path, "-l"])
    device = re.compile("(\S*) \((\S*)\)").findall(out)  # ABCDEF (ww:xx:yy:zz)
    switched = [(mac, name) for name, mac in device]
    return switched

def paired_device_bluetoothctl(bluetoothctl_path=bluetoothctl_path):
    "Listed die gepairten Geräte per 'bluetoothctl'"
    p = subprocess.Popen([bluetoothctl_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.communicate("quit\n")[0]
    device = re.compile("Device (\S*) (\S*)").findall(out)  # Device ww:xx:yy:zz ABCDEF
    return device

if bluetoothctl_path:
    paired_device = paired_device_bluetoothctl
elif btdevice_path:
    paired_device = paired_device_btadapter
else:
    sys.exit("Either bluetoothctl or bt-adapter needs to be installed")
if not hcitool_path:
    sys.exit("hcitool not found")

def read_state():
    s = file(gpio_in_file).read()
    if s:  # Fake GPIO can be empty. Only read a Char if we are sure it isn't
        return s[0]  
    else:
        return "0"

light_state = 0  # Updated in main()

def set_door_state(door_state):
    "True == Open, False == Close"
    logger.info("Setting doorstate to {0}".format(door_state))
    f = file(gpio_out_file, "w")
    if door_state:
        f.write("1")
    else:
        f.write("0")
    f.close()

def call(*args):
    p = subprocess.Popen(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    code = p.wait()
    return out, err, code

def test_device(mac):
    "Testen ob eine Verbindung aufgebaut werden kann und ob diese auch authentifiziert"
    for cmd in hcitool_cmd:
        out, err, code = call([hcitool_path, cmd, mac])
        if code > 0:
            logger.debug("hcitool exited with: out={0} err={1} code={2}".format(strip(out), strip(err), code))
            return False
    return True

def light_react():
    global checking_proximity

    logger.info("light_react called. Checking Bluetooth proximity")
    for mac, name in paired_device():
        logger.debug("Checking {0} {1}".format(mac, name))
        if test_device(mac):
            logger.debug("Found. Switching door state")
            set_door_state(True)

def main():
    global gpio_in_file, gpio_out_file
    global light_state, door_state

    parser = OptionParser()
    parser.add_option("-t", "--test", action="store_true", default=False, help="dummy GPIO files emulieren")
    parser.add_option("-d", "--debug", action="store_true", default=False, help="enable debug output")
    options, args = parser.parse_args()

    if (options.debug):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if options.test:
        gpio_in_file = expanduser("~/fake_in_gpio")
        gpio_out_file = expanduser("~/fake_out_gpio")

    set_door_state(False)

    while True:
        cur_state = read_state()
        if not cur_state == light_state:
            light_state = cur_state
            logger.debug("Light_state changed, it is now {0}".format(cur_state))
            if light_state == "1":
                light_react()
            else:
                set_door_state(False)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
