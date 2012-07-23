#!/usr/bin/env python
###########################################################################
# odb2_reader.py
# 
# Copyright 2011-2012 Austin Murphy (austin.murphy@gmail.com)
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

import pprint  # debug



class OBD2reader:
    """ OBD2reader abstracts the communication with the OBD-II vehicle."""
    def __init__(self, devtype, device):
        """Initializes port by resetting device and getting supported PIDs. """
        #
        self.Type         = devtype  # SERIAL, FILE, other?  
        self.Device       = device   # ELM327, other?  used to determine which reader commands to send (separate from OBD2 cmds)
        #
        self.debug        = 0        # debug level, 0 = off, higher is more...
        #
        self.State        = 0        # 1 is connected, 0 is disconnected/failed
        self.recwaiting   = 0        # 0 = no record waiting (can send new cmd), 1 = record waiting to be retrieved
        #
        self.Style        = 'old'    # 'old', 'can'  used to determine how to interpret the results, gets updated by connect()
        self.Headers      = 0        # ECU headers, 1 is on, 0 is off
        #
        self.attr         = {}       # the list of device attributes and their values
        self.attr_cmds    = {}       # the list of supported attribute at commands, and the associated attribute
        #
        self.RecordTrace  = 0        # 0 = no, 1 = yes record a trace of the serial session
        self.tf_out       = None     # file to record trace to
        #
        if self.Type == "SERIAL":
            self.Port     = None     # connect later
        elif self.Type == "FILE":
            self.tf       = None     # open later
            self.eof      = 0
        else:
            pass
        #
        if self.Device == "ELM327":
            self.attr_cmds = {
            'AT@1'  :  "Brand",
            'AT@2'  :  "Brand2",
            'ATI'   :  "Firmware",
            'ATDP'  :  "Proto",
            'ATDPN' :  "ProtoNum",
            'ATRV'  :  "Voltage",
            }
        else:
            pass
        self.clear_attr()

    # 
    # Data structures - FYI
    # 


    # "raw_record"     -  a 2D array, 
    #             first index is line, 
    #             second index is word, 
    #             of particular interest are the "hexbytes" returned after obd2 commands
    #  
    #  This is a fully array addressible record of the command and response(s), verbatim


    # "obd2_record" - a dict that includes:
    #            - a timestamp
    #            - the command sent
    #            - an dict of responses from each ECU
    #               - key: ECU ID
    #               - value: array of databytes (response)
    #  
    #  This is what the higher level logic needs.  
    #  NOTE: multiple "line formats" are converted into a standard format to simplify the higher level decoding



    # 
    # Public Methods
    # 

    # besides these public methods, the above attributes can be directly queried and/or set. 
    #  it is currently required to manually set Port...

    def connect(self):
        """ Opens serial connection to reader device"""
        if (self.Type == "SERIAL"):
            if (self.Port== None):
                raise self.ErrorNoPortDefined("Can't connect, no serial port defined.")
            elif self.State!=0:
                raise self.ErrorAlreadyConnected("Can't connect, already connected.")
            else:
                #try:
                    self.Port.open()
                    self.State = 1
                    time.sleep(0.5)
                    #self.SERIAL_SEND_cmd( ' ' )
                    #self.flush_recv_buf()
                    self.SERIAL_FLUSH_buffers()
                    time.sleep(0.5)
                    self.SERIAL_SEND_cmd( ' ' )
                    time.sleep(0.5)
                    self.SERIAL_FLUSH_buffers()
                    if self.debug > 1:
                        print "Trying to send reset command..."
                    self.reset()
                    time.sleep(0.5)
                    # reset protocol to auto
                    self.reset_protocol()
                    time.sleep(0.5)
                    # report what protocol was discovered
                    self.rtrv_attr()
                #except serial.SerialException as inst:
                # self.State = 0
                # raise inst
        elif (self.Type == "FILE"):
            print "Nothing to do.. not a serial port..."
            pass

    def open_trace(self, tracefile):
        """ Open tracefile for reading."""

        if (self.Type == "SERIAL"):
            print "Nothing to do.. not a tracefile..."
            pass
        elif (self.Type == "FILE"):

            if self.State!=0:
                raise self.ErrorAlreadyConnected("Can't connect, already connected.")
            else:
                self.tf = open(tracefile, 'rb')
                self.State      = 1
                self.recwaiting = 1

    # TODO - maybe ... - combine above 2 functions, pass serial port/tracefile and (optional) settings dict to connect


    def disconnect(self):
        """ Resets reader device and closes serial connection. """
        if (self.Port!= None):
            if self.State==1:
                self.reset()
                self.Port.close()
            else:
                print "Can't disconnect, reader not connected"
                raise self.ErrorNotConnected("Can't disconnect")
        
        self.clear_attr()
        self.State = 0

    def close_trace(self):
        """ Close tracefile when done."""
        if self.State==1:
            self.tf.close()
            self.State = 0 
        else:
            print "Tracefile not open..."

    # TODO - combine above 2 functions


    def record_trace(self):
        """Init an output trace file and record all serial IO to it for later decoding"""

        tfname = str(int(time.time())) + ".obd2_reader.trace"
        self.tf_out = open(tfname, 'a')
        self.RecordTrace = 1
        print "Recoding trace to:", tfname


    def OBD2_cmd(self, cmd):
        """Send an OBD2 PID to the vehicle, get the result, and format it into a standard record"""
        obd2_record = []

        self.SEND_cmd(cmd)
        record = self.RTRV_record()

        # check that the ELM headers match the original cmd
        if record[0][0] != cmd:
            print "PANIC! - cmd is different"
            print "cmd:", cmd, "record[0][0]:", record[0][0]

        # Format result into a standard OBD2 record
        obd2_record = self.triage_record( record )

        if obd2_record == []:
           obd2_record = { 'command'   : cmd ,
                           'responses' : { '7E8' : [] }, 
                           'timestamp' : 0  }

        # set timestamp 
        #scantime = time.time()
        obd2_record['timestamp'] = str(int(time.time()))

        return obd2_record


    def SEND_cmd(self, cmd):
        """Send any command to the vehicle"""

        # check for pending command results to be retrieved
        if self.recwaiting != 0: 
            #print "ARGH! can't send cmd before result of last command is retrieved!!!"
            raise ErrorRtrvBeforeSend("ARGH! can't send cmd before result of last command is retrieved!!!")

        # send command
        if self.State != 1:
            print "Can't send OBD2 command, device not connected"
            raise self.ErrorNotConnected("Can't send OBD2 command")
        elif self.Type == "SERIAL":
            if self.Device == "ELM327":
                #self.ELM327_SEND_cmd(cmd)
                self.SERIAL_SEND_cmd(cmd)
                # mark that there is now a record waiting to be retrieved
                self.recwaiting = 1
            else:
                raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")
        elif self.Type == "FILE":
            # Cant Send commands to a trace
            pass
        else:
            # unknown self.Type 
            pass

        return


    def RTRV_record(self):
        """Get the record of the last command and response from the vehicle"""

        # check if there are pending command results to be retrieved
        if self.recwaiting == 0: 
            return []

        record = []
        
        # retrieve the result
        if self.State != 1:
            print "Can't send OBD2 command, device not connected"
            raise self.ErrorNotConnected("Can't send OBD2 command")
        elif self.Type == "SERIAL":
            if self.Device == "ELM327":
                record = self.SERIAL_RTRV_record()
                self.recwaiting = 0
            else:
                raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")
        elif self.Type == "FILE":
            # trace has more records until EOF is hit
            record = self.FILE_RTRV_record()
        else:
            # unknown self.Type 
            pass
        # this record to be returned may be empty if the last command was an AT command or there was line noise in the tracefile
        # callers should be able to deal with and empty record
        return record



    def triage_record(self, record):
        """ Decide what to do with a data record."""
        # Filter out any garbage commands/responses
        # Record any changes to the reader state
        # Pass OBD2 records on for formatting
    
        # We need to figure out whether this record is :
        #   - line noise / garbage "?"
        #   - the result of an "AT" command 
        #   - the result of an OBD2 command 
   
        # skip over garbage 
        if record == []           \
          or record[0] == []     \
          or record[0][0] == ''  \
          or record[0][0] == '?' :
            #print "Garbage record.  Skipping."
            return []

        # handle ELM327 errors
        #  "?" - unrecognized command
        #  "NO DATA" - reader timed out waiting for response from vehicle
        #  "BUFFER FULL" - need to read data from reader faster, ie. increase baud rate on serial connection
        #  many more...
        if len(record) > 1 :
          if record[1][0] == '?' \
          or record[1][0] == 'NO':
            #print "Garbage record.  Skipping."
            return []

        # record the changes made by AT commands
        cmd = str.upper(record[0][0])
        if cmd[0:2] == 'AT':
            self.interpret_at_cmd(record)
            return []
 
        # remove "SEARCHING..." from response
        # example:
        #  >0100
        #  SEARCHING...
        #  41 00 BE 3E A8 11 
        if len(record) > 1 :
            if record[1][0] == 'SEARCHING...':
                record.pop(1)

        # BUFFER FULL - ugh, need to speed up the serial connection
        rl = len(record)
        rec = 0
        while rec < rl:
            if record[rec][0] == 'BUFFER' and record[rec][1] == 'FULL':
                record.pop(rec)
                print " ERROR - BUFFER FULL - Increase speed of serial connection"
                #return []
            rec += 1
        # "BUS BUSY", "CAN ERROR", ???

        # if we get a 7F, that means there was an error
        #  10  - general reject
        #  11  - service not supported
        #  12  - subfunction not supported OR invalid format
        #  21  - busy repeat
        #  22  - conditions or sequence not correct 
        #  78  - response pending
        if record[1][0] == '7F':
            mode = record[1][1]
            err  = record[1][2]
            if err == 10:
                print "General Error -- Mode:", mode
            elif err == 11:
                print "Service Not Supported Error -- Mode:", mode
            elif err == 12:
                print "Subfunction Not Supported or Invalid Format Error -- Mode:", mode
            elif err == 21:
                print "BUSY, Repeat -- Mode:", mode
            elif err == 22:
                print "Conditions or Sequence Not Correct -- Mode:", mode
            elif err == 78:
                print "Unknown Error -- Mode:", mode, " -- Error code:", err
            return []


        # format an OBD 2 command for further processing at a higher layer
        try:
            obd2_record = self.format_obd2_record(record)
        except self.ErrorIncompleteRecord:
            print "Garbage record.  Skipping."
            return []
    
        return obd2_record
    

    def interpret_at_cmd(self, record):
        """Record the results of an AT command"""

        # AT commands change the state of the reader device
        # we need to keep track of the changes
        # this is ELM327 specific

        cmd = str.upper(record[0][0])

        if self.debug > 0 :
            pprint.pprint(record)

        if cmd in self.attr_cmds.keys():
            attr = self.attr_cmds[cmd]
            self.attr[ attr ] = ' '.join(record[1])
  
            # interpret ATDPN to set CAN vs. OLD
            if cmd == 'ATDPN' :
                resp = record[1][0]
                # if it is automatically set, there is a leading A, as in "A6".  
                #   FYI - 'A' is a valid protocol number so we can't just remove a leading A
                pnum = int( resp[-1], 16 )
                if self.debug > 0 :
                    print "PNUM:", pnum,
                if pnum >= 6:
                    self.Style = 'can'
                else:
                    self.Style = 'old'
                if self.debug > 0 :
                    print "Style:", self.Style

    
        elif cmd == 'ATZ':
            # this is confusing, 
            # I was thinking about having vars for "headers" AND "headers wanted" 
            # the headers var would track the actual headers state, while the headers wanted var 
            #    would let us remember that we should turn headers back on after a reset
            # not there yet...
            #self.Headers = 0
            if self.debug > 0 :
                print "AT: Reset reader"
    
        elif cmd == 'ATH0' and record[1][0] == 'OK':
            self.Headers = 0
            if self.debug > 0 :
                print "AT: Headers OFF"
    
        elif cmd == 'ATH1' and record[1][0] == 'OK':
            self.Headers = 1
            if self.debug > 0 :
                print "AT: Headers ON"

    
        return


    # fixme - some sections incomplete
    def format_obd2_record(self, record):
        """Format the results of an OBD2 command into a standard format for processing"""
    
        # If it is an OBD2 command, we need to sort out the ecu IDs and reformat multiline messages
        #   - an ISO 15765-4 (CAN) reply with or without headers
        #   - an old style reply, with or without headers 
        #     (old style = ISO 9141-2 "ISO", ISO 14230-4 "KWP", SAE J1850 "PWM & VPW")
    
        # the timestamp of when the command was sent
        #ts = '1333808134' # a ctime measurement
        # no timestamps from raw tracefiles
        ts = '0'
        # the command sent
        cmd = str.upper(record[0][0])
        # the results from each responding ECU
        ecuids = {}
    
    
        # This is what we will return
        obd2_record = {      \
           'timestamp': ts,  \
           'command': cmd,   \
           'responses': {}    }
        # responses is a dict keyed on ECU id
        # the values are arrays of data bytes
    
    
        # 5 possibilities:  can/headers, can/no headers/multiline, can/no headers/singleline, old/headers, old/no headers
        if self.debug > 1 :
            print "Style:", self.Style, " - Headers:", self.Headers, " - single/multiline  ??"
    
        if self.Style == 'can':
            if self.Headers == 1:
                # CAN headers format:  ECUID, PCIbyte, more bytes...
                # if PCI byte starts with 0, then it is the bytecount of the single frame
                # if PCI byte starts with 1, then it is the first frame of 2 or more, then next byte is the bytecount
                # if PCI byte starts with 2, then it is a continuation frame, second digit of PCI byte is a sequence number
                #    frames will never arrive more than 16 frames out of sequence so the single sequence hexdigit is sufficient
                # if message is 16 frames or less, just sort on the seq #
                # if message is longer than 16 frames, ugh... more complicated sort needed
        
                lines = sorted(record[1:])
                # this is effective for up to 16 lines per ECU ID, past that the sort will be silly
                if self.debug > 1 :
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
          
    
    
            # CAN / no headers 
            elif self.Headers == 0:
                if self.debug > 1 :
                    pprint.pprint(record)
                # Since there are no headers, we will assume everything was from '7E8'
                ecu = '7E8'
                ecuids[ecu] = {}
                ecuids[ecu]['count'] = 0
                ecuids[ecu]['data'] = []
        
                # multiline CAN (no headers)
                #   byte count on the first line, then each following line has a line num at the front
                if len(record) > 2 and len(record[1]) == 1 and len(record[1][0]) == 3:
                    ecuids[ecu]['count'] = int(record[1][0], 16)
                    #print "count:", ecuids[ecu]['count']
          
                    # strip the line numbers & any padding at the end
                    #pprint.pprint(record[2:])
                    for l in record[2:] :
                        if len(l) == 1:
                            # this can't handle out-of-order data, but will deal with multi-ecus
                            ecu += 'X'
                            ecuids[ecu] = {}
                            ecuids[ecu]['data'] = []
                            ecuids[ecu]['count'] = l[0]
                            continue
        
                        for d in l[1:] :
                            if len(ecuids[ecu]['data']) < ecuids[ecu]['count'] :
                                ecuids[ecu]['data'].append(d)
        
                # singleline CAN (no headers)
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
                      ecu += 'X'
        
    
    
    
        # TODO
        elif self.Style == 'old':
            #print "OLD Style -- ISO/PWM/VPW .."
      
            if self.Headers == 1:
                #print "Headers ON"
                # trace of this to test is from 2006 acura tsx
                # >0906
                # 48 6B 09 49 06 01 04 A6 FB 5A 0B 
                # header:
                # 48 - priority, 6B - receiver, 09 - sender
                #pprint.pprint(record)

                lines = sorted(record[1:])
                # TODO - pick out different sender ecus
  
                ecu = lines[0][2]
                print "ECU:", ecu
                ecuids[ecu] = {}
                ecuids[ecu]['count'] = 0
                ecuids[ecu]['data'] = []

                if len(lines) > 1 :
                    print "OLD style, with Headers, Multiline"
                    # 0: pri, 1: rcvr, 2: sndr, 3: mode, 4: pid, 5: linenum, 6->(n-1): data, lastbyte: checksum
                    # add mode & pid once, skip linenums, concat data
                    ecuids[ecu]['data'] = lines[0][3:5]
                    for l in lines:
                        ecuids[ecu]['data'].extend(l[6:-1])
                    #print "data:",
                    #pprint.pprint(ecuids[ecu]['data'])
                elif len(lines) == 1 :
                    print "OLD style, with Headers, Singleline"
                    # some pids (mode 09) will have a message count in byte 5
                    #  needs to be filtered later
                    # 0: pri, 1: rcvr, 2: sndr, 3: mode, 4: pid, 5-(n-1): data, lastbyte: checksum
                    # singleline
                    ecuids[ecu]['count'] = lines[0][5]
                    ecuids[ecu]['data'].extend(lines[0][3:-1])
                else:
                    # ERROR !
                    #print "ERROR, data record too short:"
                    #pprint.pprint(record)
                    raise self.ErrorIncompleteRecord("ERROR - Incomplete Response Record")



            elif self.Headers == 0:
                print "Headers OFF"
                #print "cmd:", cmd
                #pprint.pprint(record)
    
                # singleline vs multiline (with line #'s)
                lines = sorted(record[1:])
    
                # Since there are no headers, we will assume everything was from '09'
                ecu = '09'
                ecuids[ecu] = {}
                ecuids[ecu]['count'] = 0
                ecuids[ecu]['data'] = []
               
                #print "DEBUG ---- LINES:"
                #pprint.pprint(lines)
    
                if len(lines) > 1 :
                    # multiline 
                    # 0: mode, 1: pid, 2: linenum, 3-n: data
                    # add mode & pid once, skip linenums, concat data
                    ecuids[ecu]['data'].extend(lines[0][0:2])
                    for l in lines:
                        ecuids[ecu]['data'].extend(l[3:])
                elif len(lines) == 1 :
                    # singleline
                    ecuids[ecu]['data'] = lines[0]
                else:
                    # ERROR !
                    #print "ERROR, data record too short:"
                    #pprint.pprint(record)
                    raise self.ErrorIncompleteRecord("ERROR - Incomplete Response Record")


        for e in ecuids.iterkeys():
            obd2_record['responses'][e] = ecuids[e]['data']
            #print "ECU:", e, ", Data:",
            #pprint.pprint(ecuids[e]['data'])
        
    
        return obd2_record




    #
    #  Private functions  (don't call these except from within this context)
    #

    # fixme - consider SERIAL vs. FILE
    def clear_attr(self):
        """ Clears data attributes"""
        # data attributes that should get filled in when reader is working
        self.attr = {}
        #for i in self.suppt_attr.keys():
        for k in self.attr_cmds.keys():
            self.attr[ self.attr_cmds[k] ] = "Unknown"

    # fixme - consider SERIAL vs. FILE
    def rtrv_attr(self):
        """ Retrieves data attributes"""
        #
        if self.debug > 1:
            print "Retrieving reader attributes..."
        #
        if self.State != 1:
            print "Can't retrieve reader attributes, reader not connected"
            raise self.ErrorNotConnected("Can't retrieve reader attributes")
        else:
            if self.Device == "ELM327":
                self.ELM327_rtrv_attr()
            else:
                raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")

    # fixme - consider SERIAL vs. FILE
    def reset(self):
        """ Resets device"""
        #
        if self.debug > 1:
            print "Sending reset command..."
        #
        if self.State != 1:
            print "Can't reset reader, reader not connected"
            raise self.ErrorNotConnected("Can't reset reader")
        else:
            if self.Device == "ELM327":
                self.ELM327_reset()
            else:
                raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")

    def reset_protocol(self):
        """ Resets device communication protocol"""
        #
        if self.debug > 1:
            print "Resetting communication protocol..."
        #
        if self.State != 1:
            print "Can't reset protocol, reader not connected"
            raise self.ErrorNotConnected("Can't reset reader")
        else:
            if self.Device == "ELM327":
                self.ELM327_reset_protocol()
            else:
                raise self.ErrorReaderNotRecognized("Unknown OBD2 Reader device")

    #
    # Plain serial functions (private)
    #

    # fixme - consider SERIAL vs. FILE



    #
    #  ELM327 specific functions (private)
    #

    def ELM327_rtrv_attr(self):
        """ Retrieves data attributes"""
        #for i in self.suppt_attr.keys():
        for k in self.attr_cmds.keys():
            self.SEND_cmd( k )
            time.sleep(0.1)
            self.interpret_at_cmd( self.RTRV_record() )


    def ELM327_reset(self):
        """ Resets device"""
        # FYI - interpret_at_cmd can't handle an empty list

        self.SEND_cmd("atz")    # reset ELM327 firmware
        self.interpret_at_cmd( self.RTRV_record() )

        if self.Headers == 1:
            self.SEND_cmd("ath1")  # headers on
            self.interpret_at_cmd( self.RTRV_record() )


    def ELM327_reset_protocol(self):
        """ Resets device"""
        # FYI - interpret_at_cmd can't handle an empty list

        self.SEND_cmd("atsp0")    # reset protocol
        #self.triage_record( self.RTRV_record() )
        self.RTRV_record()

        self.SEND_cmd("0100")    # load something to determine the right protocol
        self.RTRV_record()

        # just for good measure
        self.SERIAL_FLUSH_buffers()



    #
    #  SERIAL specific functions (private)
    #
    
    def SERIAL_FLUSH_buffers(self):
        """Internal use only: not a public interface"""
        #
        if self.debug > 1:
            print "Trying to flush the recv buffer... (~2 sec wait)"
        #
        # wait 2 secs for something to appear in the buffer
        time.sleep(2)
        # flush both sides
        self.Port.flushOutput()
        self.Port.flushInput()

    def SERIAL_SEND_cmd(self, cmd):
        """Private method for sending any CMD to a serial-connected reader device."""
        # Must be connected & operational
        if self.State == 0:
            # a slightly more informative result might help
            return 

        # SEND
        if self.Port.writable():
            #print "\nwriting " + cmd + " to port..."
            for c in str(cmd):
                self.Port.write(c)
            self.Port.write("\r\n")

        return

    def SERIAL_RTRV_record(self):
        """Private method for retrieving the last command and its result from a serial-connected reader device."""
        # Assumes records are separated by a '>' prompt.
        # Must be connected & operational
        if self.State == 0:
            # a slightly more informative result might help
            return []
        # max seconds to wait for data
        max_wait = 3
        # seconds to wait before trying again
        try_wait = 0.1
        tries = max_wait / try_wait
        # how much we have waited so far
        waited = 0
        # RECV
        raw_record = []
        #  raw_record is a list of non-empty strings, 
        #  each string is a line of info from the reader
        word = ''
        linebuf = []
        while len(raw_record) < 1 :
            # we need to have something to reply.. 
            #print "chars waiting:", self.Port.inWaiting()
            #sys.stdout.flush()
            while  self.Port.inWaiting() > 0:
                while 1:
                    # read 1 char at a time 
                    #   until we get to the '>' prompt
                    # 
                    c = self.Port.read(1)
                    # 
                    if self.RecordTrace == 1:
                        self.tf_out.write(c)
                    # 
                    # we are done once we see the prompt
                    if c == '>':
                        if self.debug > 2 :
                            print "Raw Record: ",
                            pprint.pprint(raw_record)
                        return raw_record
                    # \r = CR , \n = LF 
                    #  (serial device uses CR + optionally LF, unix text only uses LF)
                    # new array entry but only if there is something to add
                    elif c == '\r' or c == '\n':
                        if word != '':
                            linebuf.append(word)
                            word = ''
                        if linebuf != []:
                            raw_record.append(linebuf)
                            linebuf = []
                    # split line into words
                    elif c == ' ':
                        if word != '':
                            linebuf.append(word)
                            word = ''
                    # all other chars
                    else : 
                        word = word + c
    
            # wait a bit for the serial line to respond
            if self.debug > 1 :
                print "NO DATA TO READ!!"
            if waited < max_wait :
                waited += try_wait
                time.sleep(try_wait)
            else:
                self.recwaiting = 0
                return []



    #
    #  FILE specific functions (private)
    #
    
    def FILE_RTRV_record(self):
        """ get one data record from trace. return as an array """
        eor = 0
        raw_record = []
        #record = []
        #  record is a list of non-empty strings, 
        #  each string is a line of info from the reader
        word = ''
        linebuf = []
        while len(raw_record) < 1 and self.eof == 0 and eor == 0 :
            # we need to have something to reply.. 
            while 1:
                # read 1 char at a time 
                #   until we get to the '>' prompt
                #
                c = self.tf.read(1)
                #
                #print c,
                #
                if len(c) != 1:
                    self.eof = 1
                    if self.debug > 2 :
                        print "FILE Raw Record: ",
                        pprint.pprint(raw_record)
                    return raw_record
                elif c == '>':
                    eor = 1
                    if self.debug > 2 :
                        print "FILE2 Raw Record: ",
                        pprint.pprint(raw_record)
                    return raw_record
                # \r = CR , \n = LF 
                #  (serial device uses CR + optionally LF, unix text only uses LF)
                # - new array entry but only if there is something to add 
                elif c == '\r' or c == '\n':
                    if word != '':
                        linebuf.append(word)
                        word = ''
                    if linebuf != []:
                        raw_record.append(linebuf)
                        linebuf = []
                # split line into words
                elif c == ' ':
                    if word != '':
                        linebuf.append(word)
                        word = ''
                # all other chars
                else : 
                    word = word + c
  
        time.sleep(0.001)





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

    class ErrorRtrvBeforeSend(Exception):
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return repr(self.value)

    class ErrorIncompleteRecord(Exception):
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

