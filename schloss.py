#!/usr/bin/python2
# -*- coding: utf-8 -*-
import pyinotify
from threading import Thread, Lock
from os.path import expanduser
import logging

import subprocess
import re
import os
import sys
import distutils.spawn
from optparse import OptionParser

hcitool_cmd = "hcitool cc {0} && hcitool auth {0} && hcitool dc {0}"

parser = OptionParser()
parser.add_option("-t", "--test", action="store_true", default=False, help="dummy GPIO files emulieren")
parser.add_option("-d", "--debug", action="store_true", default=False, help="enable debug output")
options, args = parser.parse_args()

#gpio_in_file = "/root/fake_in_gpio"
if options.test:
    gpio_in_file = expanduser("~/fake_in_gpio")
    gpio_out_file = expanduser("~/fake_out_gpio")
else:
    gpio_in_file = "/sys/class/gpio/gpio24/value"
    gpio_out_file = "/sys/class/gpio/gpio18/value"
checking_proximity = False
light_lock = Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
if (options.debug):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
logger.setLevel(logging.DEBUG)
# logger.setLevel(logging.INFO)

btdevice_path = distutils.spawn.find_executable("bt-device")
bluetoothctl_path = distutils.spawn.find_executable("bluetoothctl")
hcitool_path = distutils.spawn.find_executable("hcitool")

if not os.geteuid() == 0:
    sys.exit("This program needs root rights to work")

def switch_door_state():
    global door_state
    door_state = not door_state
    set_door_state()

def paired_device_btadapter():
    "Listed die gepairten Geräte per 'bt-adapter -l'"
    out = subprocess.check_output([btdevice_path, "-l"])
    device = re.compile("(\S*) \((\S*)\)").findall(out)  # ABCDEF (ww:xx:yy:zz)
    switched = [(mac, name) for name, mac in device]
    return switched

def paired_device_bluetoothctl():
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
    if s:
        return s[0]
    else:
        return "0"

light_state = read_state()
door_state = True  # true == Open

def set_door_state():
    global door_state
    logger.info("Setting doorstate to {0}".format(door_state))
    f = file(gpio_out_file, "w")
    if door_state:
        f.write("1")
    else:
        f.write("0")
    f.close()

set_door_state()

def test_device(mac):
    "Testen ob eine Verbindung aufgebaut werden kann und ob diese auch authentifiziert"
    p = subprocess.Popen([hcitool_cmd.format(mac, hcitool=hcitool_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out, err = p.communicate()
    code = p.wait()
    if code == 0:
        return True
    else:
        if len(out) or len(err):
            logger.debug("hcitool exited with: " + out + err)
    return False

def proximity():
    dev = paired_device()
    found = False
    logger.debug("Known Devices: {0}".format(dev))

    for mac, name in dev:
        logger.debug("Testing: {0}, {1}".format(mac, name))
        if test_device(mac):
            logger.debug("Found: {0}, {1}".format(mac, name))
            found = True
            break
    if found:
        return mac, name
    else:
        return None, None

class ProcessTransientFile(pyinotify.ProcessEvent):
    def process_IN_MODIFY(self, event):
        Thread(target=light_react).start()

def light_react():
    global checking_proximity, light_state
    light_lock.acquire()
    if checking_proximity:
        logger.debug("Allready checking. Giving up")
        light_lock.release()
        return
    else:
        checking_proximity = True
        try:
            cur_state = read_state()
            if cur_state == light_state:
                logger.debug("State is the same as before")
                light_lock.release()
                return
            light_state = cur_state
            light_lock.release()

            logger.info("Light switched. Checking Bluetooth proximity")
            mac, name = proximity()
            if mac:
                logger.debug("Found. Opening door")
                switch_door_state()

            logger.debug("Done checking")
        finally:
            checking_proximity = False

wm = pyinotify.WatchManager()
notifier = pyinotify.Notifier(wm, ProcessTransientFile())

wm.add_watch(gpio_in_file, pyinotify.IN_MODIFY)

notifier.loop()
