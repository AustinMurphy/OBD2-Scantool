#!/usr/bin/env python
############################################################################
#
# decode-trace.py  
#
# Copyright 2011 Austin Murphy (austin.murphy@gmail.com)
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
#  This is a development script to test the decoding of PIDs from a trace
#

#  by "trace" I mean a log of the raw hex & ascii passed over the serial connection.
#    a cut an paste of a serial session should work 



import time
import sys, os

# main OBD2 object
import obd2

import obd2_reader

import pprint


# headers on(1)/off(0)
headers = 0
#style = can/old
#style = 'old'
style = 'can'
    

def main():
    """ Decode a tracefile """

    if len(sys.argv) < 2:
        sys.exit('Usage: %s tracefile' % sys.argv[0])
    
    if not os.path.exists(sys.argv[1]):
        sys.exit('ERROR: Tracefile %s was not found!' % sys.argv[1])
    
    tracefile = sys.argv[1]
    
    
    print "=================================================================="
    print ""
    print "OBD2 trace decode"
    print "----------------------"
    print ""
    print "Date: ", time.ctime()
    print ""
    print "Trace: ", tracefile
    
    
    print ""
    print "Loading default PID definitions from CSV file..."
    obd2.load_pids_from_csv( 'obd2_std_PIDs.csv' )
    # Global: obd2.PIDs[]
    
    print ""
    print "Loading default DTC definitions from CSV file..."
    obd2.load_dtcs_from_csv( 'obd2_std_DTCs.csv' )
    # Global: obd2.DTCs[]
    

    # create OBD2_READER object 
    TYPE   = 'FILE'
    READER = 'ELM327'
    
    # create reader object (disconnected)
    reader = obd2_reader.OBD2reader( TYPE, READER )

    # open tracefile
    reader.open_trace(tracefile)

    # manually set since we can't query the tracefile
    reader.Style   = 'can'
    reader.Headers = 1


    print ""
    print "Reading from tracefile..."
    print ""

    while 1:
        print "-----------------------------------"
        record = reader.RTRV_record()
        pprint.pprint(record)
        obd2_record = reader.triage_record( record )
        if obd2_record == []:
            # then this must have been something other than an obd2_record, nothing to do
            pass
        else:
            # do something with the obd2_record
            pprint.pprint(obd2_record)
            print "--"
            pprint.pprint( obd2.decode_obd2_record( obd2_record) )

        if reader.eof == 1:
            break

    print "-----------------------------------"
    print "END"




   
if __name__ == "__main__":
    sys.exit(main()) 

