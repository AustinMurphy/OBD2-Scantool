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

import pprint



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
    

    print ""
    with open(tracefile, 'rb') as f:
      while 1:
        print "code:"
        #l = obd2.decode_obd2_reply( read_result_from_trace(f) )
        eof, reply = read_result_from_trace(f) 
        if eof == 1:
          break
        if reply != []:
          pprint.pprint(reply)
          print "decoded:"
          pprint.pprint(obd2.decode_obd2_reply( reply[1:] ) )





def read_result_from_trace(tf):
    """ read response from trace into array of arrays """
    eof = 0
    eor = 0
    reply = []
    #  reply is a list of non-empty strings, 
    #  each string is a line of info from the reader
    buffer = ''
    while len(reply) < 1 and eof == 0 and eor == 0 :
      # we need to have something to reply.. 
      while 1:
          # read 1 char at a time 
          #   until we get to the '>' prompt
          c = tf.read(1)
          if len(c) != 1:
              eof = 1
              break
          if c == '>':
              eor = 1
              break
          elif c != '\r' and c != '\n':
              buffer = buffer + c
          elif c == '\n':
              buffer.rstrip()
              reply.append(buffer)
              buffer = ''
      time.sleep(0.001)

    # reply is now an array like this:
    #  [0] = the cmd sent
    #  [1] = first line of the response
    #  [2] = second line of the response
    #  ...

    #  parse lines into arrays of hexbytes
    result = []
    #for line in reply[1:]:
    for line in reply:
        #print "DEBUG: LINE --", line, "--"
        #  NO DATA and empty lines should not be passed along
        l = line.rstrip()
        if l == 'NO DATA':
          result.append(l.split('_'))
        elif l != '':
          temp = l.split(' ')
          if len(temp) > 0:
              result.append(temp)
    
    return eof, result



   
if __name__ == "__main__":
    sys.exit(main()) 

