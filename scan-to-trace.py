#!/usr/bin/env python
############################################################################
#
# scan-to-trace.py  
#
# Copyright 2011-2012 Austin Murphy (austin.murphy@gmail.com)
#
# This file is part of OBD2 Scantool.
#
# OBD2 Scantool is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# OBD2 Scantool is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OBD2 Scantool; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
############################################################################


#
#  This is a basic scan script to capture readings from all supported PIDs to a trace for later analysis
#

#
#  With vehicle ON (Engine can be either OFF or RUNNING)
#  Attach OBD2 interface to computer and vehicle
#  Run this scan script
#


import sys, os, time

# req'd by obd2_reader
import serial

# req'd by obd2
import obd2_reader

# main OBD2 object
import obd2


# debug
import pprint


def main():
    
    
    print "=================================================================="
    print ""
    print "OBD2 vehicle scan to trace"
    print "--------------------------"
    print ""
    print "Scan date: ", time.ctime()
    
    
    
    print ""
    print "=================================================================="
    print ""
    print "Serial port attributes"
    print "----------------------"
    
    #ser_device = '/dev/pts/7'
    ser_device = '/dev/ttyUSB0'
    
    ser_settings = {
     'baudrate': 38400,
     'bytesize': serial.EIGHTBITS,
     'parity'  : serial.PARITY_NONE,
     'stopbits': serial.STOPBITS_ONE,
     'xonxoff' : False,
     'rtscts'  : False,
     'dsrdtr'  : False,
     'timeout' : 2,
     'writeTimeout'    : None
     'interCharTimeout': None,
    }
    
    # create serial port (closed)
    port = serial.Serial(None)
    port.port = ser_device
    port.applySettingsDict(ser_settings)
    
    print "Device".rjust(16), ": ",  port.name
    #pprint.pprint( port.getSettingsDict() )
    #print ""
    
    settings = port.getSettingsDict()
    for k in sorted(settings.keys()):
        print k.rjust(16), ": ", settings[k]
    
    
    
    print ""
    print "=================================================================="
    print ""
    print "OBD2 reader device"
    print "------------------"
    
    TYPE   = 'SERIAL'
    READER = 'ELM327'
    
    # create reader object (disconnected)
    reader = obd2_reader.OBD2reader( TYPE, READER )
    reader.Port = port
    reader.Headers = 1
    reader.debug = 2

    # we want a record of what we pulled
    reader.record_trace()

    reader.connect()   # this also opens the serial port
    
    print "Device".rjust(16), ": ", str(reader.Device)
    print "State".rjust(16), ": ", str(reader.State)
    print "Style".rjust(16), ": ", str(reader.Style)
    print "Headers".rjust(16), ": ", str(reader.Headers)

    #pprint.pprint( reader.attr )
    for k in sorted(reader.attr.keys()):
        print k.rjust(16), ": ", reader.attr[k]

    # TODO
    #   notice that ELM327 is not connected and throw exception
    
    
    
    #print ""
    #print "OBD2 initialization"
    #print "-------------------"
    
    vehicle = obd2.OBD2( reader )
    
    #print ""
    #print "Loading default PID definitions from CSV file..."
    obd2.load_pids_from_csv( 'obd2_std_PIDs.csv' )
    #print ""
    #print "Loading default DTC definitions from CSV file..."
    obd2.load_dtcs_from_csv( 'obd2_std_DTCs.csv' )


    
    
    print ""
    print "=================================================================="
    # debug
    #reader.RTRV_record()
    print ""
    print "Scanning vehicle for supported features..."
    vehicle.scan_features()
    
    print ""
    print "Supported PIDs - DEBUG"
    print "----------------------"
    pprint.pprint(vehicle.suppPIDs)
    
    
    
    print ""
    print "=================================================================="
    print " "
    print "All PIDs"
    print "--------------------"
    for spid in vehicle.suppPIDs:
        pprint.pprint( reader.OBD2_cmd(spid) )

    print ""
    print ""
    print "=================================================================="
    
    
    


if __name__ == "__main__":
    sys.exit(main()) 

