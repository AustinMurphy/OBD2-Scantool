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
    

    print ""
    with open(tracefile, 'rb') as f:
      while 1:
        eof, trace_record = get_record_from_trace(f) 
        if eof == 1:
          break
        obd2_record = triage_record(trace_record)
        if obd2_record == []:
          # then this must have been something other than an obd2_record, nothing to do
          pass
        else:
          # do something with the obd2_record
          pprint.pprint(obd2_record)
      

def triage_record(record):
    """ Decide what to do with a data record."""
        #pprint.pprint(record)

        # We need to figure out whether this record is :
        #   - line noise / garbage "?"
        #   - the result of an "AT" command 
        #   - the result of an OBD2 command 

        # skip over garbage 
        if record == []           \
           or record[0] == []     \
           or record[0][0] == ''  \
           or record[0][0] == '?' \
           or record[1][0] == '?' \
           or record[1][0] == 'NO DATA':
          #print "Garbage record.  Skipping."
          return []

        # record the changes made by AT commands
        cmd = str.upper(record[0][0])
        if cmd[0:2] == 'AT':
          interpret_at_cmd(cmd, record)
          return []

        # format an OBD 2 command for further processing at a higher layer
        obd2_record = format_obd2_record(record)

        return obd2_record



def get_record_from_trace(tf):
    """ get one data record from trace. return as an array """
    eof = 0
    eor = 0
    raw_record = []
    record = []
    #  record is a list of non-empty strings, 
    #  each string is a line of info from the reader
    buffer = ''
    while len(raw_record) < 1 and eof == 0 and eor == 0 :
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
              raw_record.append(buffer)
              buffer = ''
      time.sleep(0.001)

    # raw_record is now an array like this:
    #  [0] = the cmd sent
    #  [1] = first line of the response
    #  [2] = second line of the response
    #  ...

    #  split raw_record lines on whitespace 
    for line in raw_record:
        l = line.rstrip()
        #  leave "NO DATA" as-is
        if l == 'NO DATA':
          record.append([l])
        #  empty lines should not be passed along
        elif l != '':
          temp = l.split(' ')
          if len(temp) > 0:
              record.append(temp)
    
    # record is a 2D representation of the record from the tracefile
    return eof, record


def interpret_at_cmd(cmd, record):
    """Record the results of an AT command"""
    print "AT command:", cmd,
    #print "response:", record[1][0]
    print "--- response:", record[1]
    #pprint.pprint(record)
    
    if cmd == 'ATZ':
      headers = 0
      print "AT: Reset reader"

    if cmd == 'ATH0' and record[1][0] == 'OK':
      headers = 0
      print "AT: Headers OFF"

    if cmd == 'ATH1' and record[1][0] == 'OK':
      headers = 1
      print "AT: Headers ON"

    return


#def format_obd2_record(record, style, headers):
def format_obd2_record(record):
    """Format the results of an OBD2 command into a standard format for processing"""

    print "OBD command"
    #print "OBD command:", cmd
 
    #style = main.style
    #headers = main.headers

    print "Style:", style, " - Headers:", headers

    # If it is an OBD2 command, we need to sort out the ecu IDs and reformat multiline messages
    #   - an ISO 15765-4 (CAN) reply with or without headers
    #   - an old style reply, with or without headers 
    #     (old style = ISO 9141-2 "ISO", ISO 14230-4 "KWP", SAE J1850 "PWM & VPW")

    # the timestamp of when the command was sent
    ts = '1333808134'
    # the command sent
    cmd = str.upper(record[0][0])
    # the results from each responding ECU
    ecuids = {}


    # This is what we will return
    obd2_record = {      \
       'timestamp': ts,  \
       'command': cmd,   \
       'results': {}    }

  
    # 4 possibilities:  can/headers, can/no headers, old/headers, old/no headers

    if style == 'can':
      if headers == 1:
        # CAN headers format:  ECUID, PCIbyte, more bytes...
        # if PCI byte starts with 0, then it is the bytecount of the single frame
        # if PCI byte starts with 1, then it is the first frame of 2 or more, then next byte is the bytecount
        # if PCI byte starts with 2, then it is a continuation frame, second digit of PCI byte is a sequence number
        #    frames will never arrive more than 16 frames out of sequence so the single sequence hexdigit is sufficient
        # if message is 16 frames or less, just sort on the seq #
        # if message is longer than 16 frames, ugh... more complicated sort needed

        lines = sorted(record[1:])
        # this is effective for up to 16 lines per ECU ID, past that the sort will be silly
        print "CAN w/H, lines:"
        pprint.pprint(lines)
        
        linenum = 1
        # first element of each line is the ECU ID
        for line in lines:
          if linenum > 16 :
            print "Oops.  Too many CAN Frames in this message."
            break
          linenum += 1
          ecu = line[0]
          if ecu not in ecuids:
            #print "New ECU"
            ecuids[ecu] = {}
            ecuids[ecu]['data'] = []
            ecuids[ecu]['count'] = 0
          # PCI byte
          pci1 = line[1][0]
          pci2 = line[1][1]

          if pci1 == '0':
            # single line of data
            ecuids[ecu]['count'] = pci2
            for b in line[2:]:
              if len(ecuids[ecu]['data']) < ecuids[ecu]['count']:
                ecuids[ecu]['data'].append(b)
          elif pci1 == '1':
            # first of multiple lines, next byte is the bytecount
            datacount = line[2]
            ecuids[ecu]['count'] = int(datacount, 16)
            for b in line[3:]:
              ecuids[ecu]['data'].append(b)
          elif pci1 == '2':
            # 2nd or later of multiple lines, just data
            for b in line[2:]:
              if len(ecuids[ecu]['data']) < ecuids[ecu]['count']:
                ecuids[ecu]['data'].append(b)
           
        # CAN / with headers
        #obd2_record['results'] = ecuids
        print "CAN w/Headers, ecuids:"
        pprint.pprint(ecuids)


      elif headers == 0:
        #pprint.pprint(record)
        # Since there are no headers, we will assume everything was from '7E8'
        ecu = '7E8'
        ecuids[ecu] = {}
        ecuids[ecu]['count'] = 0
        ecuids[ecu]['data'] = []

        # multiline CAN has a byte count on the first line, then each following line has a line num at the front
        if len(record) > 2 and len(record[1]) == 1 and len(record[1][0]) == 3:
          ecuids[ecu]['count'] = int(record[1][0], 16)
          print "count:", ecuids[ecu]['count']

          # strip the line numbers & any padding at the end
          #pprint.pprint(record[2:])
          for l in record[2:] :
              if len(l) == 1:
                # this can't handle out-of-order data, but will deal with multi-ecus
                ecu += 'A'
                ecuids[ecu] = {}
                ecuids[ecu]['data'] = []
                ecuids[ecu]['count'] = l[0]
                continue
                
              for d in l[1:] :
                 if len(ecuids[ecu]['data']) < ecuids[ecu]['count'] :
                     ecuids[ecu]['data'].append(d)

        # singleline CAN
        else :
          for l in record[1:] :
            if ecu not in ecuids:
              #print "New ECU"
              ecuids[ecu] = {}
              ecuids[ecu]['data'] = []
              ecuids[ecu]['count'] = 0
            for d in l :
              ecuids[ecu]['data'].append(d)
            ecuids[ecu]['count'] = len(ecuids[ecu]['data'])
            # fake ECU name for extra data
            ecu += 'A'


        # CAN / no headers
        #pprint.pprint(ecuids)


    elif style == 'old':
      #print "OLD Style -- ISO/PWM/VPW .."

      if headers == 1:
        # no trace of this to test
        #pprint.pprint(record)
        pass

      elif headers == 0:
        #print "cmd:", cmd
        #pprint.pprint(record)
        pass


    #obd2_record['results'] = ecuids
    #print "ecuids:"
    #pprint.pprint(ecuids )
    print "Results:"
    pprint.pprint(obd2_record['results'] )

    return obd2_record


   
if __name__ == "__main__":
    sys.exit(main()) 

