#!/usr/bin/env python
###########################################################################
# odb2_reader.py
# 
# Copyright 2011 Austin Murphy (austin.murphy@gmail.com)
# Copyright 2009 Secons Ltd. (www.obdtester.com)
# Copyright 2004 Donour Sizemore (donour@uchicago.edu)
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
###########################################################################

#
# this object represents "the OBD2 reader" (a.k.a. ELM327 or similar)
#
#  it implements the SERIAL <--> CAN/PWM/etc communication layer
#    provides standardized repsonses to OBD2 object
#  it discovers/reports version/protocol/capabilities
#  it does not interpret the OBD2 messages & codes, 
#    just passes them along and reformats them as necessary



import serial  # 
import string  # split 
import time    # pause 
import sys     # write to stderr

#import pprint  # debug



class OBD2reader:
    """ OBD2reader abstracts the communication with the OBD-II vehicle."""
    def __init__(self, type, device):
        """Initializes port by resetting device and getting supported PIDs. """
        #
        self.Type     = type     # SERIAL, FILE, other?  
        self.Device   = device     # ELM327, other?  used to determine which reader commands to send (separate from OBD2 cmds)
        self.Port     = None       # connect later
        #
        self.State      = 0        # 1 is connected, 0 is disconnected/failed
        self.Headers    = 0        # ECU headers, 1 is on, 0 is off
        self.attr       = {}       # the list of device attributes and their values
        self.suppt_attr = {}       # the list of supported device attributes 
        #
        if self.Device == "SERIAL":
            pass
        elif self.Device == "TRACE":
            self.tf = None
            self.eof = 0
            pass
        else:
            pass
        #
        if self.Device == "ELM327":
            self.suppt_attr = {
            'Brand'   : 'at@1',
            'Brand2'  : 'at@2',
            'Firmware': 'ati',
            'Proto'   : 'atdp',
            'ProtoNum': 'atdpn',
            'Voltage' : 'atrv'
            }
        else:
            pass
        self.clear_attr()

    # 
    # Public Methods
    # 

    # besides these public methods, the above attributes can be directly queried and/or set. 
    #  it is currently required to manually set Port...

    def connect(self):
        """ Opens serial connection to reader device"""
        if (self.type == "SERIAL"):
            if (self.Port== None):
                raise self.ErrorNoPortDefined("Can't connect, no serial port defined.")
            elif self.State!=0:
                raise self.ErrorAlreadyConnected("Can't connect, already connected.")
            else:
                #try:
                    self.Port.open()
                    self.State = 1
                    self.flush_recv_buf()
                    self.reset()
                    self.rtrv_attr()
                #except serial.SerialException as inst:
                # self.State = 0
                # raise inst
        elif (self.type == "FILE"):
            print "Nothing to do.. not a serial port..."
            pass

    def open_trace(self, tracefile):
        """ Open tracefile for reading."""
        if (self.type == "SERIAL"):
            print "Nothing to do.. not a tracefile..."
            pass
        elif (self.type == "FILE"):
            self.tf = open(tracefile, 'rb')
            self.State = 1


    def disconnect(self):
        """ Resets reader device and closes serial connection"""
        if (self.Port!= None):
            if self.State==1:
                self.reset()
                self.Port.close()
            else:
                print "Can't disconnect, reader not connected"
                raise self.ErrorNotConnected("Can't disconnect")
        
        self.clear_attr()
        self.State = 0

    # TODO
    #def close_trace(self)


    def OBD2_cmd(self, cmd):
        """Send an OBD2 PID to the vehicle, get the result, and format it into a standard record"""
        #  should return this:
        #[
        #  [ ECU ID, MODE, PID, [ DATABYTES ] ],
        #  [ ECU ID, MODE, PID, [ DATABYTES ] ],
        #  ...
        #]

        result = []
        if self.State != 1:
            print "Can't send OBD2 command, reader not connected"
            raise self.ErrorNotConnected("Can't send OBD2 command")
        else:
          if self.Device == "ELM327":
              #result = self.ELM327_OBD2_cmd(cmd)
              #result = self.ELM327_cmd(cmd)
              record = self.triage_record( self.ELM327_cmd(cmd) )
          else:
              raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")

        return record

    def TRACE_cmd(self):
        """Read the next record from the trace file and format into a standard record."""
        if self.eof == 1:
            return []

        trace_record = self.TRACE_record()

        record = self.triage_record( trace_record )

        return record


    def triage_record(self, record):
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
          self.interpret_at_cmd(record)
          return []
 
        # format an OBD 2 command for further processing at a higher layer
        obd2_record = self.format_obd2_record(record)
    
        return obd2_record
    

    def interpret_at_cmd(self, record):
        """Record the results of an AT command"""

        cmd = str.upper(record[0][0])

        print "AT command:", cmd,
        #print "response:", record[1][0]
        print "--- response:", record[1]
        #pprint.pprint(record)
    
        if cmd == 'ATZ':
          self.Headers = 0
          print "AT: Reset reader"
    
        if cmd == 'ATH0' and record[1][0] == 'OK':
          self.Headers = 0
          print "AT: Headers OFF"
    
        if cmd == 'ATH1' and record[1][0] == 'OK':
          self.Headers = 1
          print "AT: Headers ON"
    
        return


    def format_obd2_record(self, record):
        """Format the results of an OBD2 command into a standard format for processing"""
    
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
    
    
        # 5 possibilities:  can/headers, can/no headers/multiline, can/no headers/singleline, old/headers, old/no headers
        print "Style:", style, " - Headers:", headers
    
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
    
    
        # TODO
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




    #
    #  Private functions  (don't call these except from within this context)
    #

    def clear_attr(self):
        """ Clears data attributes"""
        # data attributes that should get filled in when reader is working
        self.attr = {}
        for i in self.suppt_attr.keys():
            self.attr[i] = "Unknown"

    def rtrv_attr(self):
        """ Retrieves data attributes"""
        if self.State != 1:
            print "Can't retrieve reader attributes, reader not connected"
            raise self.ErrorNotConnected("Can't retrieve reader attributes")
        else:
            if self.Device == "ELM327":
                self.ELM327_rtrv_attr()
            else:
                raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")

    def reset(self):
        """ Resets device"""
        if self.State != 1:
            print "Can't reset reader, reader not connected"
            raise self.ErrorNotConnected("Can't reset reader")
        else:
            if self.Device == "ELM327":
                self.ELM327_reset()
            else:
                raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")

    def flush_recv_buf(self):
        """Internal use only: not a public interface"""
        time.sleep(0.2)
        while self.Port.inWaiting() > 0:
            tmp = self.Port.read(1)
            time.sleep(0.1)



    #
    #  ELM327 specific functions (private)
    #

    def ELM327_rtrv_attr(self):
        """ Retrieves data attributes"""
        for i in self.suppt_attr.keys():
            # fixme
            self.attr[i] = self.ELM327_cmd( self.suppt_attr[i] )

    def ELM327_reset(self):
        """ Resets device"""
        self.ELM327_cmd("atz")    # reset ELM327 firmware
        #self.ELM327_cmd("ate0")   # echo off
        #self.ELM327_cmd("atl0")   # linefeeds off
        if self.Headers == 1:
            self.ELM327_cmd("ath1")  # headers on

    def ELM327_cmd(self, cmd):
        """Private method for sending any CMD to an ELM327 style reader and getting the result"""
        #  SENDs a command and then RECVs the reply until it sees a ">"  ELM prompt
        #  Separates textlines into array
        #  returns array 
        #   
        #   TODO  logging to a trace file
        #   TODO  lock and unlock for thread safety
        
        # Must be connected & operational
        if self.State == 0:
            # a slightly more informative result might help
            return []


        # SEND
        if self.Port.writable():
            #print "\nwriting " + cmd + " to port..."
            for c in str(cmd):
                self.Port.write(c)
            self.Port.write("\r\n")


        # RECV
        raw_result = []
        #  raw_result is a list of non-empty strings, 
        #  each string is a line of info from the reader
        buffer = ''
        while len(raw_result) < 1 or self.Port.inWaiting() > 0:
            # we need to have something to reply.. 
            while 1:
                # read 1 char at a time 
                #   until we get to the '>' prompt
                c = self.Port.read(1)
                # 
                #  TODO: if logging==on, append c to trace file
                # 
                if c == '>':
                    break
                elif c != '\r' and c != '\n':
                    buffer = buffer + c
                elif c != '\n':
                    if buffer != '':
                        raw_result.append(buffer)
                        buffer = ''
            time.sleep(0.1)

        # raw_result is a 1D array
        #  [0] = the cmd sent
        #  [1] = first line of the response
        #  [2] = second line of the response
        #  ...

        # check that the ELM headers match the original cmd
        if raw_result[0] != cmd:
            print "PANIC! - cmd is different"

        # split each string in 1D array into a list of hexbytes, making a 2D array
        result = []
        for line in raw_result[1:]:
            #print "DEBUG: LINE --", line, "--"
            # if line has a trailing space, it adds an empty item in the hexbyte array
            if line != 'NO DATA':
              temp = line.rstrip().split(' ')
              if len(temp) > 0:
                  result.append(temp)

        #  2D array 
        return result



    #
    #  TRACE specific functions (private)
    #
    
    def TRACE_record(tf):
        """ get one data record from trace. return as an array """
        # output should look the same as ELM327_cmd()
        #eof = 0
        eor = 0
        raw_record = []
        record = []
        #  record is a list of non-empty strings, 
        #  each string is a line of info from the reader
        buffer = ''
        while len(raw_record) < 1 and self.eof == 0 and eor == 0 :
          # we need to have something to reply.. 
          while 1:
              # read 1 char at a time 
              #   until we get to the '>' prompt
              c = tf.read(1)
              if len(c) != 1:
                  self.eof = 1
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
        return record






    # 
    # Exceptions
    # 
      
    class ErrorNoPortDefined(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)

    class ErrorAlreadyConnected(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)

    class ErrorNotConnected(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)

    class ErrorReaderNotRecognized(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)






#    list_supported_features, (should be like the basic info)
#    just look at the attr or suppt_attr dicts


# Other ideas
# 
#  ELM327 can work at higher speeds by fiddling with the Baudrate divisor
#    new speed persists once set and survives resets
#    setting involves testing and saving
#  highspeed mode could update more sensors, more quickly, etc. 
#    not too much use for simple diagnostics
#
#    standard_speed,  (38400 or 9600)
#    high_speed_1m,  (1Mbit??)
#    high_speed_2m,  (2Mbit??)

# low power mode 

