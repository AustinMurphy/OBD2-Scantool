#!/usr/bin/env python
###########################################################################
# odb2.py
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
# this class represents "the vehicle" 
#
#  it interprets and presents the standard OBD2 messages & codes
#  it does not implement the communications layers


# for debugging/development
#import pprint

# lots of string manipulation
import string

# for logging
import time

# for reading CSV files of PIDs and DTCs
import csv

# for hex to ascii conversion
import binascii


#
# See README.OBD2 for OBD2 reference info
#




# definitions of Mode/Parameter IDs
PIDs = {}
#   PIDs[PID] = [bytesreturned, listofsensors]
#      sensor = [desc, min, max, unit, formula]

# definitions of Diagnostic Trouble Codes (reference only, possibly using multiple sources)
DTCs = {}
#   DTCs[code] = Description




# DTCs since last time DTCs were cleared
GET_UNCLEARED_DTCs = "03"
CLEAR_DTCs         = "04"
# DTCs from curent drive cycle:
GET_CYCLE_DTCs     = "07"
# DTCs that have been cleared
GET_CLEARED_DTCs   = "0A"


supported_PIDs  = ["0100", "0101", "0104", "0105", "010C", "010D", "0111",
                   "0200", "0202", "0204", "0205", "020C", "020D", "0211",
                   "0600", 
                   "0900"]
#  FYI  -  0100, 0101, 0104, 0105, 010C, 010D, 0111  are mandatory
#       when DTC is set, freeze frame must be set with 
#                0202, 0204, 0205, 020C, 020D, 0211 
# 
# 0104/0204 - Calculated engine load value (%)
# 0105/0205 - Engine coolant temperature (°C)
# 010C/020C - Engine speed (rpm) 
# 010D/020D - Vehicle speed (km/h)
# 0111/0211 - Throttle position (%)

feature_PIDs    = ["0100", "0120", "0140", "0160", "0180", "01A0", "01C0", "01E0",
                   "0200", "0220", "0240", "0260", "0280", "02A0", "02C0", "02E0",
                   "0600", "0620", "0640", "0660", "0680", "06A0", "06C0", "06E0",
                   "0900" ]
diagnostic_PIDs = ["0101", "0102", "0130", "0131", "014E", "0121", "014D", "0141"]

# 01 01 - Monitor status since DTCs cleared & MIL status & DTC count
#
# If all monitors are "complete" and there are no DTCs and no MIL, 
#    then we pass inspection.
#
# 01 30 - # of warm-ups since codes cleared
# 01 31 - Distance traveled since codes cleared (km)
# 01 4E - Time since trouble codes cleared (minutes)
#
# 01 21 - Distance traveled with MIL on (km)
# 01 4D - Time run with MIL on (minutes)
#
# 01 41 - Monitor status this drive cycle



OBD_standards = {
    "00" : "Unknown",
    "01" : "OBD-II as defined by the CARB",
    "02" : "OBD as defined by the EPA",
    "03" : "OBD and OBD-II",
    "04" : "OBD-I",
    "05" : "Not meant to comply with any OBD standard",
    "06" : "EOBD (Europe)",
    "07" : "EOBD and OBD-II",
    "08" : "EOBD and OBD",
    "09" : "EOBD, OBD and OBD II",
    "0A" : "JOBD (Japan)",
    "0B" : "JOBD and OBD II",
    "0C" : "JOBD and EOBD",
    "0D" : "JOBD, EOBD, and OBD II"
}


fuel_types = {
    "00" : "Unknown",
    "01" : "Gasoline",
    "02" : "Methanol",
    "03" : "Ethanol",
    "04" : "Diesel",
    "05" : "LPG",
    "06" : "CNG",
    "07" : "Propane",
    "08" : "Electric",
    "09" : "Bifuel running Gasoline",
    "0A" : "Bifuel running Methanol",
    "0B" : "Bifuel running Ethanol",
    "0C" : "Bifuel running LPG",
    "0D" : "Bifuel running CNG",
    "0E" : "Bifuel running Prop",
    "0F" : "Bifuel running Electricity",
    "10" : "Bifuel mixed gas/electric",
    "11" : "Hybrid gasoline",
    "12" : "Hybrid Ethanol",
    "13" : "Hybrid Diesel",
    "14" : "Hybrid Electric",
    "15" : "Hybrid Mixed fuel",
    "16" : "Hybrid Regenerative"
}

# indexed numerically: 0-4
fuel_system_statuses = [
    "Open loop due to insufficient engine temperature",
    "Closed loop, using oxygen sensor feedback to determine fuel mix",
    "Open loop due to engine load OR fuel cut due to deacceleration ",
    "Open loop due to system failure",
    "Closed loop, using at least one oxygen sensor but there is a fault in the feedback system"
]

# indexed numerically: 0-2
secondary_air_statuses = [
    "Upstream of catalytic converter",
    "Downstream of catalytic converter",
    "From the outside atmosphere or off"
]


# indexed numerically: 0-1
ignition_type = [
    "Spark",
    "Compression"
]

# indexed numerically: 0-2
continuous_monitors = [
    "Misfire",
    "Fuel system",
    "Components"
]

# indexed numerically: 0-7, 2 & 4 are placeholders for compression ignition monitors
non_continuous_monitors = [
    [
    "Catalyst",
    "Heated Catalyst",
    "Evaporative System",
    "Secondary Air System",
    "A/C Refrigerant",
    "Oxygen Sensor",
    "Oxygen Sensor Heater",
    "EGR System"
    ], 
    [
    "NMHC Cat",
    "NOx/SCR Monitor",
    "",
    "Boost Pressure",
    "",
    "Exhaust Gas Sensor",
    "PM filter monitoring",
    "EGR and/or VVT System"
    ]
]


# DTC info loader
def load_dtcs_from_csv(dtcsfile):
    """ Load DTC definitions from CSV file . """
    # load DTC definitions from CSV file into DTCs dict
    #
    #  DTC,"Description"
    #
    with open(dtcsfile, 'rb') as f:
        reader = csv.reader(f)
        # skip the field description line
        flddesc = reader.next()
        for row in reader:
            DTCs[row[0]] = row[1]


# PID info loader
def load_pids_from_csv(pidsfile):
    """ Load PID definitions from CSV file . """
    # load PID definitions from CSV file into PIDs dict
    #
    #  "Mode (hex)","PID (hex)","Data bytes returned",Desc,Min,Max,Units,Formula[,Desc,Min,Max,Units,Formula]*
    #
    with open(pidsfile, 'rb') as f:
        reader = csv.reader(f)
        # skip the field description line
        flddesc = reader.next()

        for row in reader:
            num_vals = len(row)
            # Mode, PID (within the mode), bytes returned
            M = row[0]
            P = row[1]
            B = row[2]

            # reformat PID to match other usages
            # TODO:  (mode 0x05 PIDs are actually 4 characters long... hmmm )
            PID = str.upper(M).rjust(2,'0') + str.upper(P).rjust(2,'0')
           
            sensors = []
            #  most PIDs have just one sensor, O2 sensors have 2, 
            #  the CSV file is formatted to have 5 fields per sensor, the first 3 fields are not repeated
            num_sensors = (num_vals-3)/5
            i = 0
            while i < num_sensors:
                # sensor is a 5-tuple (desc, min, max, units, formula)
                j = (5*i)+3
                sensors.append(row[j:j+5])
                i += 1

            PIDs[PID] = [B, sensors]


#
# decoding helpers
#

def hex_to_bitstring(str):
    """ Convert hex digits to a string of bits"""
    # 4 bits per hex digit
    bitstring = ""
    for i in str:
        # silly type safety, we don't want to eval random stuff
        if type(i) == type(''):
            v = eval("0x%s" % i)
            for j in (8, 4, 2, 1):
                if v & j :
                    bitstring += '1'
                else:
                    bitstring += '0'
    # reverse the string to make it array addressable
    return bitstring[::-1]


def decode_text( data ) :
    """ Decode ASCII text encoded in hex"""
    TXT = ''
    for d in data:
         TXT += binascii.unhexlify(d)

    return TXT


def decode_ints( data ) :
    """ Decode integers encoded in hex"""
    INTs = ''
    for d in data:
         INTs += str(int(d, 16)).rjust(3,' ')
         INTs += ' '

    return INTs


def decode_hex( data ) :
    """ Decode hex chars encoded in hex"""
    # just turn the array into a string, same spacing as the INTs string above
    HEXs = ''
    for d in data:
         HEXs += d.rjust(3,' ')
         HEXs += ' '

    return HEXs


# used by monitor decode and O2 sensor bitmap decode
def hexbytes_to_bitarrays( data ) :
    """ Convert list of hex bytes to a list of bitstrings """
    values = []
    #data = result[0][2:]
    for b in data:
        values.append(hex_to_bitstring(b))
    return values
    # this does not match the [ desc, value, unit ] style of "values",  but it works..


#
#  full decoders  that return list of 3-tuple values 
#

def decode_DTCs( data ) :
    """ Decode Diagnostic Trouble Codes """
    values = []

    charcode = [ "P", "C", "B", "U" ]
    
    while len(data) > 0:
        A = data.pop(0)
        B = data.pop(0)
 
        # 00 00 is padding
        if A != '00' and B != '00':
            A0 = int(A[0], 16)
            DTC = str(charcode[ A0 / 4 ]) + str(A0 % 4) + A[1] + B
            values.append( [ "DTC", DTC, DTCs[DTC] ] )

    return values



def decode_monitors( P, data ) :
    """ Decode onboard emmissions monitors """
    # this is the primary OBD info considered by the Official Emmissions Inspection process
    # 0101 looks at the overall status of the monitors, 
    # 0141 looks at the their status only for the current drive cycle
    values = []
    [A, B, C, D] = hexbytes_to_bitarrays( data )

    # PID 0101 has MIL & DTC count, 0141 does not
    if P == '01':
        MIL = "Off"
        if A[7] == '1':
            MIL = "ON"
        values.append( ["MIL", MIL, ""] )
        DTC_CNT = int(data[0], 16) & int(0x7F)
        values.append( ["DTC count", DTC_CNT, ""] )

    ign = int(B[3])
    values.append( [ "Ignition Type", ign, ignition_type[ign] ] )

    # TODO: these should just skip unsupported sensors, duh.
    #   and doneness should be the 2nd field in the 3 tuple
    for i in [0, 1, 2]:
        state = "UNSUPPORTED"
        done = "INCOMPLETE"
        if B[i] == '1':
            state = "SUPPORTED"
            if B[i+4] == '0':
                done = "READY"
            values.append( [continuous_monitors[i], state, done] )

    if ign == 0 :
        for i in [0, 1, 2, 3, 4, 5, 6, 7]:
            state = "UNSUPPORTED"
            done = "INCOMPLETE"
            if C[i] == '1':
                state = "SUPPORTED"
                if D[i] == '0':
                    done = "READY"
                values.append( [non_continuous_monitors[0][i], state, done] )

    if ign == 1 :
        for i in [0, 1, 3, 5, 6, 7]:
            state = "UNSUPPORTED"
            done = "INCOMPLETE"
            if C[i] == '1':
                state = "SUPPORTED"
                if D[i] == '0':
                    done = "READY"
                values.append( [non_continuous_monitors[1][i], state, done] )


    return values



#
# starting point for decoding any obd2 reply
#

def decode_obd2_reply(result):
    """ Decode sensor reading . """
    # typical result is the list of hexbytes:  4+MODE, PID, A, B, C, D, ...
    # Other possiblities include mulitple lines of above, 
    #   or CAN style, with bytecount on first line followed by 1: data, 2: data, ...

    # values returned should be a list of 3-tuples (desc, value, unit) or something equivalent
    #  or an empty list if there is nothing to decode
    values = []

    # result format style: 
    #   sl (singleline), 
    #   mlold (multiline OLD style), 
    #   mlcan (multiline CAN style)
    FMT = ''
    # mode 
    M = ''
    # pid (not incl. mode)
    P = ''
    # C - count of datapoints reported, only reported if response is CAN style. 0 means unknown
    C = ''
    # data to decode, without MODE, PID, count or padding if response is CAN style
    D = []   

    #
    # filter out bogus replys
    # determine message format
    # determine MODE
    # determine PID
    #
    # modes 3, 4, 7, A(?) have no PIDs, 
    # modes 1, 2, 9 have PIDs with 2 chars (1 hexbyte)
    # mode 5, has PIDs with 4 chars (2 hexbytes), 
    # don't know about other modes
    #

    if len(result) == 0:
        #debug
        #print "nothing to decode!"
        return values

    elif len(result) == 1:
        #debug
        #print "result = 1 line"
        if len(result[0]) == 0:
            #print "nothing to decode!"
            return values
        elif result[0][0] == '?':
            #print "nothing to decode!"
            return values
        elif result[0][0] == 'NO' and result[0][1] == 'DATA':
            #print "nothing to decode!"
            return values
        else :
            # single line response
            #   typical for most sensors
            FMT = 'sl'
            M = result[0][0]
            M = str(hex(int(M,16) - 0x40))[2:]
            M = str.upper(M).rjust(2,'0')

            MSG = result[0][1:]
            if M == '03' or M == '04' or M == '07' or M == '0A':
                P = ''
                if len(MSG) % 2 == 1 :              
                    # ISO 15765-4, CAN style ( M, C, C pairs of bytes)
                    C = int(MSG[0], 16)
                    D = MSG[1:]
                else :
                    # OLD style ( M, 3 pairs of bytes)
                    D = MSG

            elif M == '01' or M == '02' or M == '09':
                P = str.upper(MSG[0]).rjust(2,'0')
                #C = int(MSG[1], 16)
                D = MSG[1:]

    elif len(result) > 1 :
        #print "result > 1 line"
        if len(result[0]) == 1:
            # multiline CAN style reply, ISO 15765-2 
            #   typical for PID 0902 (VIN) 
            FMT = 'mlcan'
            
            # number of databytes in message
            B = int(result[0][0], 16)

            MSG = []

            # strip the line numbers & any padding at the end
            i = 0
            for l in result[1:] :
                for d in l[1:] :
                   if i < B :
                       MSG.append(d)
                   i += 1;

            # mode
            M = MSG[0]
            M = str(hex(int(M,16) - 0x40))[2:]
            M = str.upper(M).rjust(2,'0')

            if M == '03' or M == '04' or M == '07' or M == '0A':
                P = ''
                C = int(MSG[1], 16)
                D = MSG[2:]

            elif M == '01' or M == '02' or M == '09':
                P = str.upper(MSG[1]).rjust(2,'0')
                C = int(MSG[2], 16)
                D = MSG[3:]

            elif M == '06':
                P = str.upper(MSG[1]).rjust(2,'0')
                D = MSG[2:]

        else:
            # multiline old style reply 
            #  possible for 0902 (VIN) on pre-CAN vehicles
            FMT = 'mlold'
            # mode
            M = result[0][0]
            M = str(hex(int(M,16) - 0x40))[2:]
            M = str.upper(M).rjust(2,'0')

            # pid 
            P = result[0][1]
            if M == '03' or M == '04' or M == '07' or M == '0A':
                P = ''
                for l in result :
                    for d in l[1:] :
                       D += d

            elif M == '01' or M == '02' or M == '06' or M == '09':
                P = str.upper(result[0][1]).rjust(2,'0')
                for l in result :
                    for d in l[2:] :
                       D += d
  
    # debug
    #print "FMT M P C D :", FMT, M, P, C, D
    if len(D) > 0:
        return decode_data_by_mode(M, P, C, D)
    else:
        # mode 04 (clear codes) has no data to report
        return values





def decode_data_by_mode(mode, pid, count, data):
    """ Decode sensor reading using PIDs dict . """
    # expecting:
    #   - the result data to be valid
    #   - the mode and pid to be extracted
    #   - in some situations, a count of values to decode 
    #   - any multiline data to be reformatted into a single array of hexbytes "data"

    M = mode
    P = pid
    C = count

    # values returned should be a list of 3-tuples (desc, value, unit) or something equivalent
    #  or an empty list if there is nothing to decode
    values = []


    if M == '01' :
        PID = '01' + str.upper(P).rjust(2,'0')

    elif M == '02' :
        # mode 2 uses the same definitions as mode 1 (I hope...)
        PID = '01' + str.upper(P).rjust(2,'0')
        if P == '02' :
            return decode_DTCs(data)

    elif M == '03' :
        return decode_DTCs(data)

    elif M == '04' :
        pass

    elif M == '05' :
        PID = '05' + str.upper(P).rjust(4,'0')

    elif M == '06' :
        PID = '06' + str.upper(P).rjust(2,'0')
        print " DONT KNOW how to interpret mode 06"
        print "  PID:", PID
        print "  Hex:", decode_hex(data)
        print " Ints:", decode_ints(data)
        print " Text:", decode_text(data)
        return []

    elif M == '07' :
        return decode_DTCs(data)

    elif M == '08' :
        pass

    elif M == '09' :
        PID = '09' + str.upper(P).rjust(2,'0')

    elif M == '0A' :
        return decode_DTCs(data)

    else :
        # unknown mode
        return values

    

    if PID not in PIDs :
        print "Unknown PID, data: ", PID, data
        values.append( ["Unknown", PID, ""] )
        return values

    elif PID in feature_PIDs : 
        # don't try to decode a feature PID
        return values

    elif PID == '0101' or PID == '0141':
        return decode_monitors(P, data)

    elif PID == '0103':
        A = hex_to_bitstring(data[0])
        B = hex_to_bitstring(data[1])
        i = 0 
        while i < 5:
            if A[i] == '1':
                fcode1 = i
            if B[i] == '1':
                fcode2 = i
            i += 1
        values.append( ["Fuel system 1 status", fcode1, fuel_system_statuses[fcode1]] )
        values.append( ["Fuel system 2 status", fcode2, fuel_system_statuses[fcode2]] )
        return values

    elif PID == '0112':
        A = hex_to_bitstring(data[0])
        i = 0 
        while i < 3:
            if A[i] == '1':
                sacode = i
            i += 1
        values.append( ["Secondary air status", sacode, secondary_air_statuses[sacode]] )
        return values

    elif PID == '0113' or PID == '011D':
        [A] = hexbytes_to_bitarrays( data )
        values.append( ["O2 Sensor bitmap", A, "Next 8 PIDs"] )
        return values

    elif PID == '011C':
        A = data[0]
        values.append( ["OBD standard", A, OBD_standards[A]] )
        return values

    elif PID == '0151':
        A = data[0]
        values.append( ["Fuel type", A, fuel_types[A]] )
        return values

    #elif PID == '0902' or PID == '0904':
    elif M == '09':
        values.append( [ PIDs[PID][1][0][0], decode_text( data ), "" ] )
        return values

    # insert new elif sections here

    else :
        databytes   = int(PIDs[PID][0])
 
        if len(data) < databytes :
            #print "expecting:", databytes, "bytes, received:", len(result[0])-2, "bytes"
            values.append( [ PID, "ERROR", "expected more databytes" ] )
            return values

        # assign A, B, C, D, ...
        if databytes >= 1 :
            A = int(data[0], 16)
        if databytes >= 2 :
            B = int(data[1], 16)
        if databytes >= 3 :
            C = int(data[2], 16)
        if databytes >= 4 :
            D = int(data[3], 16)
        if databytes >= 5 :
            E = int(data[4], 16)
        if databytes >= 6 :
            F = int(data[5], 16)
        if databytes >= 7 :
            G = int(data[6], 16)

        # some PIDs have info for multiple sensors
        for sensor in PIDs[PID][1] :
            desc    = sensor[0]
            minval  = float(sensor[1])
            maxval  = float(sensor[2])
            unit    = sensor[3]
            formula = sensor[4]
             
            # skip decode if formula does not exist
            if len(formula) == 0:
                values.append( [desc, "ERROR", "FORMULA UNKNOWN"] )
                return values

            # TODO: more checking to be sure that we are not eval'ing something wierd

            # compute and test value
            value = eval(formula)

            if value < minval:
                values.append( [desc, "ERROR", "undermin"] )
            elif value > maxval:
                values.append( [desc, "ERROR", "overmax"] )
            else:
                values.append( [desc, value, unit] )

    return values






class OBD2:
    """ OBD2 abstracts communication with OBD-II vehicle."""
    def __init__(self,reader):
        """Initializes port by resetting device and gettings supported PIDs. """
        # OBD2 reader device, see "class obd2_reader"
        self.reader = reader

        # PIDs supported in this instance, preloaded with a few to start
        self.suppPIDs = supported_PIDs

        # Dict of Basic info about the vehicle, VIN, fuel type, OBD standard, etc.
        self.info    = {
            'OBD_std'      : '00',
            'fuel_type'    : '00',
            'VIN'          : "Unknown",
            'Calibration'  : "Unknown",
            'Year'         : "Unknown",
            'Make'         : "Unknown",
            'Model'        : "Unknown"
        }

        # Maintenance Indicator Lamp (aka. check engine light)
        self.MIL      = "Unknown"
        # list of DTCs
        self.DTCcount = "Unknown"
        self.currDTCs = ()
        # monitor info
        self.monitors  = {}
        # Dict of info related to DTCs, # warmups & distance & time since codes cleared, distance & time run with MIL
        self.DTCinfo  = {}


    def scan_features(self):
        """ Scan vehicle for supported features. """
        # scans known feature PIDs, adds PIDs reported as supported to self.suppPIDs
        for fpid in feature_PIDs:
            if fpid in self.suppPIDs:
                feature_bits = self.interpret_features(fpid)
                # debug
                print feature_bits, ""
        self.suppPIDs.sort()


    # move this to global (have it return list of supported PIDs like this: [ PID, desc, '' ] )
    def interpret_features(self, fpid):
        """ Interpret feature query and add supported PIDs to supported PID list. """
        # 
        pbytes = len(fpid) / 2
        
        # debug
        print "Checking feature PID:", fpid, "--",
        result = self.reader.OBD2_cmd(fpid)
        # debug
        print result
        
        feat_bits = ""
        if len(result) > 0 and len(result[0]) > pbytes:
            for hexbyte in  result[0][pbytes:] :
                # unreverse the bitstring
                feat_bits += hex_to_bitstring(hexbyte)[::-1]
            # debug
            #print "len:", len(feat_bits)
            for i in range(32):
                if feat_bits[i] == '1':
                    fhex = "0x" + fpid
                    newpid = str.upper(hex(int(fhex,16) + i + 1)[2:]).rjust(4,'0')
                    # debug
                    #print newpid, "is supported"
                    self.suppPIDs.append(newpid)
        else:
            self.suppPIDs.remove(fpid)

        return feat_bits


    def scan_info(self):
        """ Scan vehicle for general information. """
        # no output, just adds to self.info
   
        # 011C - OBD standard 
        l = decode_obd2_reply(self.reader.OBD2_cmd("011C"))
        if len(l) > 0 :
            self.info['OBD_std'] = l[0][1]
            
        # 0151 - Fuel Type
        l = decode_obd2_reply(self.reader.OBD2_cmd("0151"))
        if len(l) > 0 :
            self.info['fuel_type'] = l[0][1]

        # 0902  - Vehicle Identification Number
        l = decode_obd2_reply(self.reader.OBD2_cmd("0902"))
        if len(l) > 0 :
            self.info['VIN'] = l[0][1]

        # 0904 - Calibration ID
        l = decode_obd2_reply(self.reader.OBD2_cmd("0904"))
        if len(l) > 0 :
            self.info['Calibration'] = l[0][1]

        # self.info['Year']   # from VIN
        # self.info['Make']   # from VIN
        # self.info['Model']  # from VIN


    def show_info(self):
        """ Show general information. """
        # just interprets self.info for CLI, GUI would directly read self.info
        print "Complies with: ", OBD_standards[self.info['OBD_std']]
        print "    Fuel type: ", fuel_types[self.info['fuel_type']]
        print "          VIN: ", self.info['VIN']
        print "  Calibration: ", self.info['Calibration']
        print "         Year: ", self.info['Year']
        print " Manufacturer: ", self.info['Make']
        print "        Model: ", self.info['Model']


    ## 3 continuous and 8 non-continuous OBD monitors, plus current fuel system and 2nd air status
    ##   dynamic info, needs time to warm up
    #monitor_PIDs   = ["0101", "0103", "0112", "0141"]
    # 

    ## static diagnostic info: MIL, DTC count, DTCs, # of warmups since DTC, time run with MIL on, 
    ##   time run since codes cleared, dist travelled with MIL, ...
    #DTC_PIDs   =     ["0101", "0102", "0121", "0130", "0131", "0141", "014D", "014E"]


    def scan_diag_info(self):
        """ Scan vehicle for current sensor readings . """
        # 
        for dpid in diagnostic_PIDs :
            if dpid in self.suppPIDs :
                # debug / log
                scantime = time.time()
                print scantime, "--",
                # debug / log
                print "read PID:", dpid, "--",
                result = self.reader.OBD2_cmd(dpid)
                # debug / log
                print "result:", result, "--",

                values = decode_obd2_reply(result)
                for val in values:
                    # debug / log
                    print val[0], ":", val[1], val[2]
                if len(values) == 0:
                    print ""


    def scan_curr_sensors(self):
        """ Scan vehicle for current sensor readings . """
        # one pass through the supported PIDs in mode 0x01
        for spid in self.suppPIDs:
            #print "supported PID:", spid
            #if spid[1] == '1' and spid not in feature_PIDs and spid not in diagnostic_PIDs:
            if spid not in feature_PIDs and spid not in diagnostic_PIDs:
                # debug / log
                scantime = time.time()
                print scantime, "--",
                # debug / log
                print "read PID:", spid, "--",
                result = self.reader.OBD2_cmd(spid)
                # debug / log
                print "result:", result, "--",

                values = decode_obd2_reply(result)
                for val in values:
                    # debug / log
                    print val[0], ":", val[1], val[2]
                if len(values) == 0:
                    print ""


    # simulator does not have freeze frame sensors
    def scan_frozen_sensors(self):
        """ Scan vehicle for freeze-frame sensor readings . """
        # one pass through the supported PIDs in mode 0x02, Freeze frame from when last DTC triggered
        for spid in self.suppPIDs:
            if spid[1] == '2' and spid not in feature_PIDs :
                #print "diag PID:", ipid, "supported"
                # debug
                #print "Checking FF sensor PID:", spid, "--",
                result = self.reader.OBD2_cmd(spid)
                # debug
                print result




# ----



