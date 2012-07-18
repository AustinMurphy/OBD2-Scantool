#!/usr/bin/env python
############################################################################
#
# decode-trace.py  
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
#headers = 1
#style = can/old
#style = 'old'
style = 'can'
    
# 0=off, 
# 1+ - show raw & decoded records
# 2+ - show record as triaged
debug = 2



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
    
    reader.debug = debug

    # open tracefile
    reader.open_trace(tracefile)

    # manually set since we can't query the tracefile
    #reader.Style   = 'can'
    #reader.Headers = 1
    #reader.Style   = 'old'
    #reader.Headers = 0
    reader.Style   = style
    reader.Headers = headers


    vehicle = obd2.OBD2( reader )


    print ""
    print "Reading from tracefile..."
    print ""

    while 1:
        record = reader.RTRV_record()
        if debug > 0:
            print "-----------------------------------"
            print "Raw Record: ",
            pprint.pprint(record)

        obd2_record = reader.triage_record( record )
        if obd2_record == []:
            # then this must have been something other than an obd2_record, nothing to do
            pass
        else:
            if debug > 1:
                print "--"
                print "Triaged Record: ",
                pprint.pprint(obd2_record)
                print "--"

            dec_rec =  obd2.decode_obd2_record( obd2_record )
            if debug > 0 :
                print "--"
                print "Decoded Record: ",
                pprint.pprint( dec_rec )
                print " "
                print "=================================="
                print " "

            # do something with the decoded obd2_record
            vehicle.store_info( dec_rec )

        if reader.eof == 1:
            break


    print "-----------------------------------"
    print ""
    print ""
    print "Reader Attributes:"
    print "------------------"
    pprint.pprint( reader.attr )
    print ""

    #
    print "Reader State:"
    print "-------------"
    print "      Type:", reader.Type         
    print "    Device:", reader.Device       
    print "     debug:", reader.debug        
    print "     State:", reader.State        
    #print "recwaiting", reader.recwaiting   
    print "     Style:", reader.Style        
    print "   Headers:", reader.Headers      
    #reader.attr         
    #print reader.attr_cmds 
    print "    Trace?:", reader.RecordTrace  
    print "Trace file:", reader.tf_out
    #



    print ""
    print "Vehicle Basic Info:"
    print "-------------------"
    pprint.pprint( vehicle.info )
    print ""
    vehicle.show_basic_info()
    print ""
    print ""
    print "Vehicle OBD2 Status:"
    print "--------------------"
    pprint.pprint( vehicle.obd2status )
    print ""
    print "-----------------------------------"
    print ""
    print "Vehicle supported PIDs:"
    print "-----------------------"
    pprint.pprint( vehicle.suppPIDs )
    print ""
    print "-----------------------------------"
    print ""
    print "Vehicle Sensor readings:"
    print "--------------------"
    pprint.pprint( vehicle.sensor_readings )
    print ""
    print "-----------------------------------"
    print "END"




   
if __name__ == "__main__":
    sys.exit(main()) 

