#!/usr/bin/python2
# -*- coding: utf-8 -*-
import pyinotify
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

hcitool_cmd =["cc", "auth", "dc"]

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
hci_lock = Lock()

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

def call(*args):
    p = subprocess.Popen(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    code = p.wait()
    return out, err, code


def test_device(mac):
    "Testen ob eine Verbindung aufgebaut werden kann und ob diese auch authentifiziert"
    try:
        hci_lock.acquire()
        for cmd in hcitool_cmd:
            out, err, code = call([hcitool_path, cmd, mac])
            #print out, err, code, [hcitool_path, cmd, mac]
            if code > 0 or "Not connected" in out:
                if out or err:
                    logger.debug("hcitool exited with: " + strip(out) + strip(err))
                return False
        return True
    finally:
        hci_lock.release()
        # pass

class Proximity(object):
    def __init__(self, devices, thread_count=4):
        self.devices = devices
        self.thread_count = thread_count
        self.status = {'alive': [], 'dead': []}
        self.lock = threading.Lock()

    def next(self):
        try:
            self.lock.acquire()
            if self.devices:
                return self.devices.pop()
            else:
                return None, None
        finally:
            self.lock.release()

    def work(self):
        while True:
            mac, name = self.next()
            if not mac:
                break

            if test_device(mac):
                self.status['alive'].append((mac, name))
            else:
                self.status['dead'].append((mac, name))

    def start(self):
        threads = []

        for i in range(self.thread_count):
            t = threading.Thread(target=self.work)
            t.start()
            threads.append(t)

        [t.join() for t in threads]

class ProcessFile(pyinotify.ProcessEvent):
    def process_IN_MODIFY(self, event):
        Thread(target=light_react).start()

def light_react():
    global checking_proximity, light_state
    light_lock.acquire()
    if checking_proximity:
        logger.debug("Already checking. Giving up")
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
            bt_tester = Proximity(paired_device())
            # bt_tester = Proximity([('F8:E0:79:49:F8:F3', 'XT1032')])

            bt_tester.start()
            logger.debug("Found: {0}".format(bt_tester.status['alive']))
            logger.debug("Dead: {0}".format(bt_tester.status['dead']))

            if bt_tester.status['alive']:
                logger.debug("Found. Opening door")
                switch_door_state()
        finally:
            checking_proximity = False

wm = pyinotify.WatchManager()
notifier = pyinotify.Notifier(wm, ProcessFile())

wm.add_watch(gpio_in_file, pyinotify.IN_MODIFY)

notifier.loop()
