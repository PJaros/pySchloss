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

gpio_in_file = "/sys/class/gpio/gpio24/value"  # Light-Switch state
gpio_out_file = "/sys/class/gpio/gpio18/value"  # Door-Switch

gpio_status_file = "/sys/class/gpio/gpio23/value"  # Status-LED

checking_proximity = False
light_lock = Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

btdevice_path = distutils.spawn.find_executable("bt-device")
bluetoothctl_path = distutils.spawn.find_executable("bluetoothctl")
hcitool_path = distutils.spawn.find_executable("hcitool")

light_state = False  # Updated in main()

blink_on = False  # Blink state
set_blink = None

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

def fake_paired_device():
    return [("00:00:00:00:00:00", "Fake1"), ("00:00:00:00:00:02", "Fake2"), ("00:00:00:00:00:03", "Fake3")]

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
    if not s:  # Fake GPIO can be empty. Only read a Char if we are sure it isn't
        return False
    elif s[0] is "0":
        return False
    else:
        return True

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

def set_fake_blink(light):
    global blink_on
    blink_on = light
    logger.info("Setting blink LED to {0}".format(blink_on))

def set_real_blink(light):
    global blink_on
    blink_on = light
    with file(gpio_status_file, "w") as f:
        if light:
            f.write("1")
        else:
            f.write("0")

set_blink = set_real_blink

def switch_blink():
    global blink_on
    blink_on = not blink_on
    set_blink(blink_on)

def light_react(search_till_found=False):
    global checking_proximity, light_state

    light_lock.acquire()
    if checking_proximity:
        logger.info("light_react() already running. Canceling this Call")
        light_lock.release()
        return
    logger.info("light_react() called. Checking Bluetooth proximity")
    try:
        checking_proximity = True
        light_lock.release()
        while light_state:
            for mac, name in paired_device():
                switch_blink()
                logger.debug("Checking {0} {1}".format(mac, name))
                if test_device(mac):
                    logger.debug("Found. Switching door state")
                    set_door_state(True)
                    return
                if not light_state:
                    break
            if not search_till_found:
                return
        if not light_state and search_till_found:
            logger.debug("light_state switched off. Stopping Scan.")
    finally:
        checking_proximity = False
        set_blink(False)

def main():
    global gpio_in_file, gpio_out_file
    global light_state, door_state
    global paired_device
    global set_blink

    parser = OptionParser()
    parser.add_option("-t", "--test", action="store_true", default=False, help="dummy GPIO files emulieren")
    parser.add_option("-d", "--debug", action="store_true", default=False, help="enable debug output")
    parser.add_option("-m", action="store_true", default=False, help="fake mac adresses")
    options, args = parser.parse_args()

    if (options.debug):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if options.test:
        gpio_in_file = expanduser("~/fake_in_gpio")
        gpio_out_file = expanduser("~/fake_out_gpio")
        set_blink = set_fake_blink

    if options.m:
        paired_device = fake_paired_device

    set_door_state(False)
    set_blink(False)

    try:
        while True:
            cur_state = read_state()
            if not cur_state == light_state:
                light_state = cur_state
                logger.debug("Light_state changed, it is now {0}".format(cur_state))
                if light_state:
                    threading.Thread(target=light_react, args=[True]).start()
                else:
                    set_door_state(False)
            time.sleep(0.1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Caught a exit signal. Exiting")
        light_state = False  # exiting possible running light_react while loop

if __name__ == "__main__":
    main()
