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

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

btdevice_path = distutils.spawn.find_executable("bt-device")
bluetoothctl_path = distutils.spawn.find_executable("bluetoothctl")
hcitool_path = distutils.spawn.find_executable("hcitool")

light_state = False  # Updated in main()

blink_on = False  # Blink state
set_blink = None

if not os.geteuid() == 0:
    sys.exit("This program needs root rights to work")

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

for mac, name in paired_device():
    if test_device(mac):
        print("Device %s from user %s here" % (mac, name))
    else:
        print("Device %s from user %s not found" % (mac, name))
