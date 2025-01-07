#!/usr/bin/python2
# -*- coding: utf-8 -*-
from threading import Thread, Lock
from os.path import expanduser, isfile
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
import urllib2
import collections

hcitool_cmd =["cc", "auth", "dc"]
reboot_cmd = ["/usr/sbin/reboot"]

gpio_in_file = "/sys/class/gpio/gpio24/value"  # Light-Switch state
gpio_out_file = "/sys/class/gpio/gpio18/value"  # Door-Switch

gpio_status_file = "/sys/class/gpio/gpio23/value"  # Status-LED

priorize_list_path = "prio_list.txt"

checking_proximity = False
light_lock = Lock()

# url_on = "http://deepthoughtplex.ruum42:8080/on"
# url_off = "http://deepthoughtplex.ruum42:8080/off"
url_on = None
url_off = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

btdevice_path = distutils.spawn.find_executable("bt-device")
bluetoothctl_path = distutils.spawn.find_executable("bluetoothctl")
hcitool_path = distutils.spawn.find_executable("hcitool")

light_state = False  # Updated in main()

blink_on = False  # Blink state
set_blink = None
err_count = 0
time_last_error = None

if not os.geteuid() == 0:
    sys.exit("This program needs root rights to work")

def switch_door_state():
    global door_state
    door_state = not door_state
    set_door_state()

def paired_device_bluetoothctl(bluetoothctl_path=bluetoothctl_path):
    "Listed die gepairten Geräte per 'bluetoothctl'"
    p = subprocess.Popen([bluetoothctl_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.communicate("quit\n")[0]
    device = re.compile("Device (\S*) (\S*)").findall(out)  # Device ww:xx:yy:zz ABCDEF
    return device

def fake_paired_device():
    return [("00:00:00:00:00:00", "Fake1"), ("00:00:00:00:00:02", "Fake2"), ("00:00:00:00:00:03", "Fake3")]

def load_list(path):
    l = []
    if isfile(path):
        with open(path, 'r') as f:
            for line in f.read().splitlines():
                l.append(line)
    return l

def write_list(l, path):
    # logger.info("Writing prio_list.txt with content " + repr(l))
    with open(path, 'w') as f:
        for item in l:
            f.write(item + "\n")

def add_priorize(mac):
    l = load_list(priorize_list_path)
    paired_device_bt = {m for m, text in paired_device_bluetoothctl()}

    # Neue Mac-Adresse vorne einfügen und hinten löschen (falls vorhanden)
    if mac in l:
        l.remove(mac)
    l.insert(0, mac)

    # logger.info("prio_list.txt before mac removal: " + repr(l))
    # Prio-Liste von nicht gepairten Mac-Adressen bereinigen
    for mac in l:
        if mac not in paired_device_bt:
            l.remove(mac)

    write_list(l, priorize_list_path)

def priorize(all_devices):
    prio_list = load_list(priorize_list_path)
    h_all_device = collections.OrderedDict()
    for mac, name in all_devices:
        h_all_device[mac] = name
    prio_mac_name = []
    for mac in prio_list:
        if mac in h_all_device:
            name = h_all_device[mac]
            prio_mac_name.append((mac, name))
            del h_all_device[mac]

    for mac, name in h_all_device.items():
        prio_mac_name.append((mac, name))
    return prio_mac_name

def priorized_device():
    pd = paired_device_bluetoothctl()
    logger.info("pd-before: " + repr(pd))
    priorized_list = priorize(pd)
    logger.info("pd-after: " + repr(priorized_list))
    return priorized_list

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
        if url_off:
            try:
                response = urllib2.urlopen(url_off).read()
                logger.info("Reported to Website, resulting. Answer: " + repr(response))
            except:
                logger.error("Error while accessing: {}. Error: {}".format(
                    repr(url_off), sys.exc_info()[0]))
    else:
        f.write("0")
        if url_on:
            try:
                response = urllib2.urlopen(url_on).read()
                logger.info("Reported to Website, resulting. Answer: " + repr(response))
            except:
                logger.error("Error while accessing: {}. Error: {}".format(
                    repr(url_on), sys.exc_info()[0]))
    f.close()

def call(*args):
    p = subprocess.Popen(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    code = p.wait()
    return out, err, code

def test_device(mac):
    "Testen ob eine Verbindung aufgebaut werden kann und ob diese auch authentifiziert"
    global err_count
    global time_last_error
    for cmd in hcitool_cmd:
        out, err, code = call([hcitool_path, cmd, mac])
        if code > 0:
            cur_time = time.time()
            short_time_passed = False
            if time_last_error == None:
                time_last_error = cur_time
            elif (cur_time - time_last_error) < 1:
                short_time_passed = True
                time_last_error = cur_time
            logger.debug("hcitool exited with: out={0} err={1} code={2} err_count={3}".format(strip(out), strip(err), code, err_count))
            if strip(err) in ("Device is not available.", "Not connected.") and short_time_passed:
                err_count += 1
            if err_count > 50:
                call(reboot_cmd)
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
            for mac, name in priorized_device():
                switch_blink()
                logger.debug("Checking {0} {1}".format(mac, name))
                if test_device(mac):
                    logger.debug("Found. Switching door state")
                    set_door_state(True)
                    add_priorize(mac)
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
