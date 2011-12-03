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
     def __init__(self, device):
         """Initializes port by resetting device and getting supported PIDs. """
         #
         self.Device   = device     # ELM327, other?  used to determine which reader commands to send (not OBD2 cmds)
         self.Port     = None       # connect later
         #
         self.State      = 0        # 1 is connected, 0 is disconnected/failed
         self.attr       = {}       # the list of device attributes and their values
         self.suppt_attr = {}       # the list of supported device attributes 
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

     def clear_attr(self):
         """ Clears data attributes"""
         # data attributes that should get filled in when reader is working
         self.attr = {}
         for i in self.suppt_attr.keys():
           self.attr[i] = "Unknown"

     def rtrv_attr(self):
         """ Retrieves data attributes"""
         if self.State == 1:
           if self.Device == "ELM327":
               self.ELM327_rtrv_attr()
           else:
               pass
         else:
           print "Can't retrieve reader attributes, reader not connected"

     def reset(self):
         """ Resets device"""
         if self.State == 1:
           if self.Device == "ELM327":
               self.ELM327_reset()
           else:
               pass
         else:
           print "Can't reset reader, reader not connected"

     def connect(self):
         """ Opens serial connection to reader device"""
         if (self.Port!= None) and self.State==0:
           try:
               self.Port.open()
               self.State = 1
               self.flush_recv_buf()
               self.reset()
               self.rtrv_attr()
           except serial.SerialException:
               self.State = 0
               return None
         else:
           return None    

     def disconnect(self):
         """ Resets reader device and closes serial connection"""
         if (self.Port!= None) and self.State==1:
            self.reset()
            self.Port.close()
         
         self.clear_attr()
         self.State = 0

     def flush_recv_buf(self):
         """Internal use only: not a public interface"""
         time.sleep(0.2)
         while self.Port.inWaiting() > 0:
             tmp = self.Port.read(1)
             time.sleep(0.1)

     def OBD2_cmd(self, cmd):
         """Public method for sending an OBD2 PID and getting the result"""
         if self.State == 1:
           if self.Device == "ELM327":
               return self.ELM327_OBD2_cmd(cmd)
           else:
               return []
         else:
           print "Can't send OBD2 command, reader not connected"


     #
     #  ELM327 specific functions
     #

     def ELM327_rtrv_attr(self):
         """ Retrieves data attributes"""
         for i in self.suppt_attr.keys():
           self.attr[i] = self.ELM327_cmd( self.suppt_attr[i] )

     def ELM327_reset(self):
         """ Resets device"""
         self.ELM327_cmd("atz")    # reset ELM327 firmware
         #self.ELM327_cmd("ate0")   # echo off
         #self.ELM327_cmd("atl0")   # linefeeds off

     def ELM327_cmd(self, cmd):
         """Private method for sending any CMD to an ELM327 style reader and getting the result"""
         #  SENDs a command and then RECVs the reply until it sees a ">"  ELM prompt
         
         # SEND
         if self.Port.writable():
             #print "\nwriting " + cmd + " to port..."
             for c in str(cmd):
                 self.Port.write(c)
             self.Port.write("\r\n")

         # RECV
         reply = []
         #  reply is a list of non-empty strings, 
         #  each string is a line of info from the reader
         buffer = ''
         while len(reply) < 1 or self.Port.inWaiting() > 0:
           # we need to have something to reply.. 
           while 1:
               # read 1 char at a time 
               #   until we get to the '>' prompt
               c = self.Port.read(1)
               if c == '>':
                   break
               elif c != '\r' and c != '\n':
                   buffer = buffer + c
               elif c != '\n':
                   if buffer != '':
                       reply.append(buffer)
                       buffer = ''
           time.sleep(0.1)

         # debug
         #pprint.pprint(reply)
         return reply


     def ELM327_OBD2_cmd(self, cmd):
         """Private method for sending an OBD2 PID to a ELM327 style reader."""
         # should really throw an exception if something is wrong, HOW?
         # might want to check that the cmd is valid OBD2 PID

         if self.State == 0:
             return []

         cmd = str(cmd)
         raw_result = self.ELM327_cmd(cmd)
  
         # raw_result is now a list
         #  [0] = the cmd sent
         #  [1] = first line of the response
         #  [2] = second line of the response
         #  ...
 
         # check that the ELM headers match the original cmd
         if raw_result[0] != cmd:
            print "PANIC! - cmd is different"

         # return lists of hexbytes
         result = []
         for line in raw_result[1:]:
             #print "DEBUG: LINE --", line, "--"
             # if line has a trailing space, it adds an empty item in the hexbyte array
             if line != 'NO DATA':
               temp = line.rstrip().split(' ')
               if len(temp) > 0:
                   result.append(temp)

         return result

      



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

