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
import pprint

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
GET_PERM_DTCs      = "03"
CLEAR_PERM_DTCs    = "04"
# DTCs from curent drive cycle:
GET_CYCLE_DTCs     = "07"
# DTCs that have been cleared
GET_CLEARED_DTCs   = "0A"


# Parameters are the same for modes $01 and $02
supported_PIDs  = ["0100", "0101", "0104", "0105", "010C", "010D", "0111",
                   "0200",
                   "0500", 
                   "0600", 
                   "0900"]
#"0200", "0202", "0204", "0205", "020C", "020D", "0211",
#  FYI  -  0100, 0101, 0104, 0105, 010C, 010D, 0111  are mandatory
#       when DTC is set, freeze frame must be set with 
#                0202, 0204, 0205, 020C, 020D, 0211 
# 
# 0104/0204 - Calculated engine load value (%)
# 0105/0205 - Engine coolant temperature (deg C)
# 010C/020C - Engine speed (rpm) 
# 010D/020D - Vehicle speed (km/h)
# 0111/0211 - Throttle position (%)

# Feature PIDs:
# modes 01, 02, 05, 06, 08, 09
# params 00, 20, 40, 60, A0, C0, E0
#  
#feature_PIDs    = ["0100", "0113", "011D", "0120", "0140", "0160", "0180", "01A0", "01C0", "01E0",
feature_PIDs    = ["0100", "0120", "0140", "0160", "0180", "01A0", "01C0", "01E0",
                   "0200", "0220", "0240", "0260", "0280", "02A0", "02C0", "02E0",
                   "0500", "0520", "0540", "0560", "0580", "05A0", "05C0", "05E0",
                   "0600", "0620", "0640", "0660", "0680", "06A0", "06C0", "06E0",
                   "0900", "0920", "0940", "0960", "0980", "09A0", "09C0", "09E0" ]

#                   "0800", "0820", "0840", "0860", "0880", "08A0", "08C0", "08E0",
#  mode 08 involves controlling the ECU, not yet...

# in mode 06, PIDs are called TIDs, Test IDs or MIDs for Monitor IDs.

# Basic, permanant info about vehicle
info_PIDs = ["011C", "0151", "0902", "0904"]

#
# Emmissions Inspection and Diagnostics
#

status_PIDs = ["0101", "0121", "0130", "0131", "0141", "014D", "014E"]

# 01 01 - Monitor status since DTCs cleared & MIL status & DTC count
#
# If all monitors are "complete" and there are no DTCs and no MIL, 
#    then we pass inspection.

# Misc. PIDs related to emmissions monitors & DTCs
misc_diag_PIDs = [ "0130", "0131", "014E", "0121", "014D"]
# remove above later...
#
# 01 30 - # of warm-ups since codes cleared
# 01 31 - Distance traveled since codes cleared (km)
# 01 4E - Time since trouble codes cleared (minutes)
# 01 21 - Distance traveled with MIL on (km)
# 01 4D - Time run with MIL on (minutes)


# 01 41 - Monitor status this drive cycle

# 02 02 - DTC that set freeze frame
#


# helper for storing info & status pid data
pidmap = {
   "011C" : 'OBD_std',
   "0151" : 'fuel_type',
   "0902" : 'VIN',
   "0904" : 'Calibration',
   "0121" : 'kmMILon',
   "0130" : 'warmups',
   "0131" : 'kmdriven',
   "014D" : 'minMILon',
   "014E" : 'minutes' 
}


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
         # check that result is actually ascii
         #if d >= '20' and d <= '7E':
         hd = eval( "0x" + d )
         if hd >= 0x20 and hd <= 0x7E :
             TXT += binascii.unhexlify(d)
         else:
             TXT += '_'
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
    bitstrs = []
    for b in data:
        bitstrs.append(hex_to_bitstring(b))
    return bitstrs




#
# starting point for decoding any obd2 reply
#

def decode_obd2_record(obd2_record):
    """ Decode sensor reading . """

    #print "OBD2 record to decode:"
    #pprint.pprint(obd2_record)
    # ctime
    #TS   = obd2_record['timestamp']
    # simple string
    #CMD  = obd2_record['command']
    # dict, keyed on ecuid, value is 1D array of databytes, no padding
    #RESP = obd2_record['responses']

    decoded_record = {}
    decoded_record['timestamp'] = obd2_record['timestamp']
    decoded_record['command']   = obd2_record['command']

    decoded_record['values']    = {}

    # values returned should be a list of 3-tuples (desc, value, unit) or something equivalent
    #  or an empty list if there is nothing to decode
    #values = []

    for ECU in obd2_record['responses'].iterkeys():

        DATABYTES = obd2_record['responses'][ECU]
        if len(DATABYTES) < 1 :
            decoded_record['values'][ECU] = []
            break

        # M: mode 
        # P: pid (not incl. mode)
        # D: data to decode, without MODE, PID, count or padding 

        # determine MODE
        M = DATABYTES[0] 
        M = str(hex(int(M,16) - 0x40))[2:]
        M = str.upper(M).rjust(2,'0')

        # determine PID
        P = ''
        D = ''

        # modes 03, 04, 07, 0A have no PIDs, 
        if M == '03' or M == '04' or M == '07' or M == '0A':
            D = DATABYTES[1:]

        # modes 01, 02, 06, 09 have PIDs with 2 chars (1 hexbyte)
        elif M == '01' or M == '02' or M == '06' or M == '09':
            P = str.upper(DATABYTES[1]).rjust(2,'0')
            D = DATABYTES[2:]

        # mode 05, has PIDs with 4 chars (2 hexbytes), 
        elif M == '05':
            P = str.upper(DATABYTES[1]).rjust(2,'0') + str.upper(DATABYTES[2]).rjust(2,'0')
            D = DATABYTES[3:]

        # don't know about other modes
        else:
            # PANIC!!! ARGH!!!
            pass


        # debug
        #print "M P D :", M, P, D
        if len(D) > 0:
            decoded_record['values'][ECU] = []

            ecvals = decode_data_by_mode(M, P, D)

            # debug
            #pprint.pprint(ecvals)

            for v in ecvals:
                decoded_record['values'][ECU].append(v)
            

    return decoded_record



def decode_data_by_mode(mode, pid, data):
    """ Determine which decoder to use, based on mode . """
    # expecting:
    #   - the result data to be valid
    #   - the mode and pid to be extracted
    #   - in some situations, a count of values to decode  (TODO???)
    #   - any multiline data to be reformatted into a single array of hexbytes "data"

    M = mode
    P = pid
    D = data

    # values returned should be a list of 3-tuples (desc, value, unit) or something equivalent
    #  or an empty list if there is nothing to decode
    values = []

    PID = M + P
    #print "PiID: -", PID, "-"

    ## feature PIDs are the same for all modes
    ## no, mode9 has a message count
    #if PID in feature_PIDs:
    #    return decode_feature_pid(PID, D)

    if M == '01' :
        return decode_mode1_pid(PID, D)

    elif M == '02' :
        # mode 2 uses the same definitions as mode 1 
        if P == '02' :
            return decode_DTCs(data)
        else :
            PID = '01' + P
            return decode_mode1_pid(PID, D)

    elif M == '03' :
        return decode_DTCs(data)

    elif M == '04' :
        # when mode 04 is sent, the DTCs are cleared.  There is no response, except "44" or and error. 
        pass

    elif M == '05' :
        return decode_mode5_pid(PID, data)

    elif M == '06' :
        return decode_mode6_pid(PID, data)

    elif M == '07' :
        return decode_DTCs(data)

    elif M == '08' :
        pass

    elif M == '09' :
        return decode_mode9_pid(PID, D)

    elif M == '0A' :
        return decode_DTCs(data)

    else :
        # unknown mode
        return values


def decode_feature_pid(PID, data): 
    """ Decode the supported features indicated."""
    # feature pids indicate which of the next 32 pids are supported
    # pids 0113 and 011D indicate which of the O2 sensors are supported
    #  they are useful with mode $05 and maybe mode $06

    # a simple list of supported pids to return
    feat_pids = []

    M = PID[0:2]
    # integer math seems to work better
    P0 = int(PID[2:], 16)

    L = len(data)
    #print "Fpid length:", L
    bits = L*8

    feat_bits = ""
    if L == 4 :
        for db in data :
            # reverse the bit order and append
            feat_bits += hex_to_bitstring(db)[::-1]
    else:
        for db in data :
            # O2 sensor bitmap isn't reversed ?
            feat_bits += hex_to_bitstring(db)
    
    for i in range(bits):
        if feat_bits[i] == '1':
            # do math as integers, then convert back to hex
            P = str.upper(hex(P0+i+1))[2:].rjust(2, "0")
            newpid = M + P
            #print "M:", M, " P0:", P0, " i:", i, " P:", P, "Newpid:", newpid 
            feat_pids.append(newpid)

            # not sure we want/need to do this
            ## add mode 02 pids based on mode 01 pids
            #if M == '01' and P != '01' and P != '02':
            #    newpid = '02' + P
            #    feat_pids.append(newpid)

    #print "Feature PIDs:"
    #pprint.pprint(feat_pids)
    return feat_pids


def decode_mode1_pid(PID, data):
    """ Decode Mode1 sensor reading using PIDs dict . """

    values = []

    if PID not in PIDs :
        #print "Unknown PID, data: ", PID, data
        values.append( ["Unknown PID: " + PID, decode_hex(data), ""] )
        return []

    elif PID in feature_PIDs:
        return decode_feature_pid(PID, data)

    elif PID == '0101' or PID == '0141':
        return decode_monitors(PID, data)

    elif PID == '0103':
        A = hex_to_bitstring(data[0])
        B = hex_to_bitstring(data[1])
        # debug
        #print "A:", A, "B:", B
        fcode1 = -1
        fcode2 = -1
        i = 0 
        while i < 5:
            if A[i] == '1':
                fcode1 = i
            if B[i] == '1':
                fcode2 = i
            i += 1
        if fcode1 != -1:
          values.append( ["Fuel system 1 status", fcode1, fuel_system_statuses[fcode1]] )
        if fcode2 != -1:
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

    # sort of handled above 
    elif PID == '0113' or PID == '011D':
        [A] = hexbytes_to_bitarrays( data )
        values.append( ["O2 Sensor bitmap", A, "Next 8 PIDs"] )
        return values

    elif PID == '011C':
        A = data[0]
        print "DEBUG: byte A:", A
        if A in OBD_standards :
            values.append( ["OBD standard", A, OBD_standards[A]] )
        else :
            values.append( ["OBD standard", A, "Unknown"] )
        return values

    elif PID == '0151':
        A = data[0]
        values.append( ["Fuel type", A, fuel_types[A]] )
        return values

    # insert new elif sections here

    else :
        return decode_generic_pid(PID, data)


def decode_mode5_pid(PID, data):
    """ Decode Mode5 . """
    # NOTE: this is only for OLD style (not CAN)

    values = []

    if PID not in PIDs :
        #print "Unknown PID, data: ", PID, data
        values.append( ["Unknown PID: " + PID, decode_hex(data), ""] )
        return []

    elif PID in feature_PIDs:
        return decode_feature_pid(PID, data)

    else :
        print " DONT KNOW how to interpret mode 05"
        print "  PID:", PID
        # same as hex
        #print "  Raw:", data
        print "  Hex:", decode_hex(data)
        print " Ints:", decode_ints(data)
        # text needs to be filtered
        #print " Text:", decode_text(data)
        return []


def decode_mode6_pid(PID, data):
    """ Decode Mode6 . """

    values = []

    # pids/tids/mids are not necessarily in the CSV file
    #if PID not in PIDs :
    #    print "Unknown PID, data: ", PID, data
    #    values.append( ["Unknown PID: " + PID, decode_hex(data), ""] )
    #    return []
    #
    #elif PID in feature_PIDs:
    if PID in feature_PIDs:
        #return []
        if len(data) == 5 :
            # pop filler byte on old style messages
            data.pop(0)
        print "feat PID, data: ", PID, data
        return decode_feature_pid(PID, data)

    else :
        #PID = '06' + str.upper(P).rjust(2,'0')
        print " DONT KNOW how to interpret mode 06"
        print "  PID:", PID
        # same as hex
        #print "  Raw:", data
        print "  Hex:", decode_hex(data)
        print " Ints:", decode_ints(data)
        # text needs to be filtered
        #print " Text:", decode_text(data)
        return []


def decode_mode9_pid(PID, data):
    """ Decode Mode9 sensor reading using PIDs dict . """

    values = []

    print "mode9 PID, data: ", PID, data

    if PID not in PIDs :
        #print "Unknown PID, data: ", PID, data
        values.append( ["Unknown PID: " + PID, decode_hex(data), ""] )
        return []

    elif PID in feature_PIDs:
        if len(data) == 5:
            # pop message count
            data.pop(0)
        return decode_feature_pid(PID, data)

    # message counts for next pids
    elif PID == '0901' or PID == '0903' or PID == '0905' or PID == '0907' or PID == '0909':
        values.append( [ PIDs[PID][1][0][0], decode_ints( data ), "" ] )
        return values

    # VIN
    elif PID == '0902':
        #   0902 should have 17 bytes
        #    VIN: XXXXXXXXXXXXXXXXX
        if len(data) == 18:
            # pop message count
            data.pop(0)
        # old style pads '0902' with 3 '00' bytes at front
        if data[0] == '00' and data[1] == '00' and data[2] == '00':
            data.pop(0)
            data.pop(0)
            data.pop(0)
        values.append( [ PIDs[PID][1][0][0], decode_text( data ), "" ] )
        return values

    # Calibration ID
    elif PID == '0904':
        #  0904 should have 16 bytes
        #  CALID: XXXXXXXXXXXXXXXX
        if len(data) == 17 or len(data) == 33:
            # pop message count
            data.pop(0)
        values.append( [ PIDs[PID][1][0][0], decode_text( data ), "" ] )
        return values

    elif PID == '0906':
        # 4 hex bytes
        #  CVN: XX XX XX XX
        if len(data) == 5:
            # pop message count
            data.pop(0)
        values.append( [ PIDs[PID][1][0][0], decode_hex( data ), "" ] )
        return values

    elif PID == '0908':
        # IPT: 16 values, each is a 2byte integer
        #print "IPT decode...."

        if len(data) == 33:
            # pop message count
            data.pop(0)

        ipt_names = [
        "OBDCOND",
        "IGNCNTR",
        "CATCOMP1",
        "CATCOND1",
        "CATCOMP2",
        "CATCOND2",
        "O2SCOMP1",
        "O2SCOND1",
        "O2SCOMP2",
        "O2SCOND2",
        "EGRCOMP",
        "EGRCOND",
        "AIRCOMP",
        "AIRCOND",
        "EVAPCOMP",
        "EVAPCOND",
        ]

        while len(data) > 0:
            A = 256 * int( data.pop(0), 16 )
            B = int( data.pop(0), 16 )
            #print "A+B", A, B, A+B
            values.append( [ "IPT: " + ipt_names.pop(0), A+B , "" ] )

        return values

    # insert new elif sections here
    # 090A ...

    else:
        return []


def decode_generic_pid(PID, data):
    """ Decode generic sensor reading using PIDs dict . """

    values = []

    # skip unknown pids
    if PID not in PIDs:
        return []

    databytes   = int(PIDs[PID][0])

    if len(data) < databytes :
        #print "expecting:", databytes, "bytes, received:", len(result[0])-2, "bytes"
        values.append( [ "ERROR", 1,  "expected more databytes" ] )
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


def decode_monitors( PID, data ) :
    """ Decode onboard emmissions monitors """
    # this is the primary OBD info considered by the Official Emmissions Inspection process
    # 0101 looks at the overall status of the monitors, 
    # 0141 looks at the their status only for the current drive cycle
    values = []
    [A, B, C, D] = hexbytes_to_bitarrays( data )
 
    badtxt = "INCOMPLETE"

    # PID 0101 has MIL & DTC count, 0141 does not
    if PID == '0101':
        badtxt = "NOT READY FOR INSPECTION"
        # debug
        #print "Monitor status OVERALL"
        MIL = "Off"
        if A[7] == '1':
            MIL = "ON"
        values.append( ["MIL", MIL, ""] )
        DTC_CNT = int(data[0], 16) & int(0x7F)
        values.append( ["DTC count", DTC_CNT, ""] )
    else:
        # debug
        #print "Monitor status THIS DRIVE CYCLE"
        pass

    ign = int(B[3])
    values.append( [ "Ignition Type", ign, ignition_type[ign] ] )

    # TODO: these should just skip unsupported sensors, duh.
    #   and doneness should be the 2nd field in the 3 tuple
    for i in [0, 1, 2]:
        done = badtxt
        if B[i] == '1':
            if B[i+4] == '0':
                done = "OK"
            values.append( ['Continuous Monitor', continuous_monitors[i], done] )

    # C lists supported monitors (1 = SUPPORTED)
    # D lists their readiness (0 = READY)
    if ign == 0 :
        for i in [0, 1, 2, 3, 4, 5, 6, 7]:
            done = badtxt
            if C[i] == '1':
                if D[i] == '0':
                    done = "OK"
                # debug
                #print 'Monitor', non_continuous_monitors[0][i], done
                values.append( ['Non-continuous Monitor', non_continuous_monitors[0][i], done] )

    if ign == 1 :
        for i in [0, 1, 3, 5, 6, 7]:
            done = badtxt
            if C[i] == '1':
                if D[i] == '0':
                    done = "OK"
                values.append( ['Non-continuous Monitor', non_continuous_monitors[1][i], done] )


    # debug
    #pprint.pprint(values)
    return values


def decode_DTCs( data ) :
    """ Decode Diagnostic Trouble Codes """
    values = []

    charcode = [ "P", "C", "B", "U" ]

    if len(data) % 2 == 1:
        numDTCs = data.pop(0)
    
    while len(data) > 1:
        A = data.pop(0)
        B = data.pop(0)
 
        # 00 00 is padding
        if A != '00' and B != '00':
            A0 = int(A[0], 16)
            DTC = str(charcode[ A0 / 4 ]) + str(A0 % 4) + A[1] + B
            values.append( [ "DTC", DTC, DTCs[DTC] ] )

    return values




# TODO - rename this OBD2_vehicle, maybe split into a separate file 
class OBD2:
    """ OBD2 abstracts communication with OBD-II vehicle."""
    def __init__(self,reader):
        """Initializes port by resetting device and getting supported PIDs. """
        # OBD2 reader device, see "class obd2_reader"
        self.reader = reader

        # PIDs supported by any ECU in this instance, preloaded with a few to start
        self.suppPIDs = supported_PIDs

        # Dict of Basic info about the vehicle, VIN, fuel type, OBD standard, etc.
        # info is PER ECU, main engine controller is not necessarily 
        #   the only ECU that will respond
        self.info    = {
            '7E8' :  {
                        'OBD_std'      : '00',
                        'fuel_type'    : '00',
                        'VIN'          : "Unknown",
                        'Calibration'  : "Unknown",
                        'Year'         : "Unknown",
                        'Make'         : "Unknown",
                        'Model'        : "Unknown"
                      }
        }

        # status is PER ECU, main engine controller is not necessarily 
        #   the only ECU that will respond to 0101
        self.obd2status  = {
            '7E8' :  {
                        # scantime is of the 0101 pid
                        'scantime'     : "Unknown",
                        'MIL'          : "Unknown",
                        'kmMILon'      : "Unknown",
                        'minMILon'     : "Unknown",
                        'inspmons'     : [],
                        'cyclemons'    : [],
                        'DTCcount'     : "Unknown",
                        'DTCs'         : [],
                        # below are all ...since DTCs last cleared
                        'warmups'      : "Unknown",
                        'kmdriven'     : "Unknown",
                        'minutes'      : "Unknown"
                     }
        }
 
        # BIG data structure to store all scan info
        # self.sensor_readings --> ECU --> PID--> scantime--> list of values
        self.sensor_readings = { }

        # TODO: something about freeze frame...


    def scan_features(self):
        """ Scan vehicle for supported features. """
        # scans known feature PIDs, adds PIDs reported as supported to self.suppPIDs
        for fpid in feature_PIDs:
            if fpid in self.suppPIDs:
                supp_pids = decode_obd2_record( self.reader.OBD2_cmd(fpid) )
                self.store_info( supp_pids )


    def scan_basic_info(self):
        """ Scan vehicle for general information. """
        # no output, just adds to self.info

        for pid in info_PIDs:
            if pid in self.suppPIDs:
                rec = decode_obd2_record( self.reader.OBD2_cmd(pid) )
                #print "Decoded: ",
                #pprint.pprint(rec)
                self.store_info(rec)

        # self.info['Year']   # from VIN
        # self.info['Make']   # from VIN
        # self.info['Model']  # from VIN



    #
    #  OBD2 Status - Emmissions monitors & diagnostic info
    #

    ## 3 continuous and 8 non-continuous OBD monitors, plus current fuel system and 2nd air status
    ##   dynamic info, needs time to warm up
    #monitor_PIDs   = ["0101", "0103", "0112", "0141"]

    ## static diagnostic info: MIL, DTC count, DTCs, # of warmups since DTC, time run with MIL on, 
    ##   time run since codes cleared, dist travelled with MIL, ...
    #DTC_PIDs   =     ["0101", "0102", "0121", "0130", "0131", "0141", "014D", "014E"]

    def scan_obd2_status(self):
        """ Scan vehicle for general information. """
        # no output, just adds to self.obd2_status
   
        for pid in status_PIDs:
            if pid in self.suppPIDs:
                rec = decode_obd2_record( self.reader.OBD2_cmd(pid) )
                #print "Decoded: ",
                #pprint.pprint(rec)
                self.store_info(rec)


    def store_info(self, rec):
        """Take a decoded record and store the relevant info in the OBD2 vehicle object."""
     
        pid = rec['command']
        ts = rec['timestamp']

        for ecu in rec['values'].iterkeys():
            if ecu not in self.info:
                #print "New ECU"
                self.info[ecu] = {}

            if pid in feature_PIDs:
                #if rec['values'][ecu] == []:
                #    self.suppPIDs.remove(pid)
                for fpid in rec['values'][ecu]:
                    if fpid not in self.suppPIDs :
                        self.suppPIDs.append(fpid)
                self.suppPIDs.sort()

            if ecu not in self.obd2status:
                #print "New ECU"
                self.obd2status[ecu] = {}
                self.obd2status[ecu]['inspmons'] = []
                self.obd2status[ecu]['cyclemons'] = []

            if pid in info_PIDs:
                if 0 in rec['values'][ecu] and len(rec['values'][ecu][0]) == 3:
                    self.info[ecu][ pidmap[pid] ] = rec['values'][ecu][0][1]

            elif pid in status_PIDs:
                # 01 01 - lots of info...
                if pid == "0101" :
                    self.obd2status[ecu]['scantime'] = rec['timestamp']
                    vals = rec['values'][ecu]
                    for v in vals:
                        if v[0] == 'MIL':
                            self.obd2status[ecu]['MIL'] = v[1]
                        elif v[0] == 'DTC count':
                            self.obd2status[ecu]['DTCcount'] = v[1]
                        elif v[0] == 'Continuous Monitor':
                            self.obd2status[ecu]['inspmons'].append(v)
                        elif v[0] == 'Non-continuous Monitor':
                            self.obd2status[ecu]['inspmons'].append(v)
                # 01 41 - lots of info...
                elif pid == "0141" :
                    self.obd2status[ecu]['scantime'] = rec['timestamp']
                    vals = rec['values'][ecu]
                    for v in vals:
                        if v[0] == 'Continuous Monitor':
                            self.obd2status[ecu]['cyclemons'].append(v)
                        elif v[0] == 'Non-continuous Monitor':
                            self.obd2status[ecu]['cyclemons'].append(v)
                # normalish
                else :
                    if len(rec['values'][ecu][0]) == 3:
                        self.obd2status[ecu][ pidmap[pid] ] = rec['values'][ecu][0][1]
       
            elif pid == '03':
                # TODO - add list of DTCs to self.obd2status[ecu]['DTCs']
                pass
       
            elif pid == '04':
                # no data, just skip
                pass
       
            # save all data for later display by tui/gui
            # self.sensor_readings --> ECU --> PID--> scantime--> list of values
            if not ecu in self.sensor_readings:
                self.sensor_readings[ecu] = {}
            if not pid in self.sensor_readings[ecu]:
                self.sensor_readings[ecu][pid] = {}
            if not ts in self.sensor_readings[ecu][pid]:
                self.sensor_readings[ecu][pid][ts] = []
                self.sensor_readings[ecu][pid][ts].extend( rec['values'][ecu] )
            else:
                while ts in self.sensor_readings[ecu][pid] :
                    ts += "0"
                self.sensor_readings[ecu][pid][ts] = []
                self.sensor_readings[ecu][pid][ts].extend( rec['values'][ecu] )
                



    def curr_sensors(self):
        """ Scan vehicle for current sensor readings . """
        # one pass through the supported PIDs in mode 0x01

        # populate list of pids to check
        sensor_pids = []
        for spid in self.suppPIDs:
            if spid[1] == '1' and spid not in feature_PIDs and spid not in info_PIDs and spid not in status_PIDs :
                sensor_pids.append(spid)

        return sensor_pids


    def scan_pid(self, pid):
        """ Scan vehicle for sensor readings using the given pids. """
        # one pass through the supported PIDs in mode 0x01
        # check the readings of each sensor

        dec_rec = decode_obd2_record( self.reader.OBD2_cmd(pid) )
        self.store_info( dec_rec )

        #self.show_last_reading( pid )



    def scan_pid_list(self, pidlist):
        """ Scan vehicle for sensor readings using the given pids. """
        # one pass through the supported PIDs in mode 0x01
        # check the readings of each sensor

        for pid in pidlist:

            self.scan_pid( pid )

            #scantime = time.time()

            #dec_rec = decode_obd2_record( self.reader.OBD2_cmd(pid) )
            #self.store_info( dec_rec )

            # probably don't want this...
            self.show_last_reading( pid )




    def show_last_reading(self, pid):
        """ Display the most recent reading for a given sensor. """
        
        # column widths
        c1 = 40
        c2 = 8

        for ecu in self.sensor_readings :
            mts = max( self.sensor_readings[ecu][pid] ) 
            print ecu, "-", pid, "-", mts, ":",
            vals = 0
            if len(self.sensor_readings[ecu][pid][mts]) == 0:
                print ""
            for val in self.sensor_readings[ecu][pid][mts] :
                if vals > 0:
                    print "                        ",
                vals += 1
                if len(val) == 3:
                    # debug / log
                    print val[0].rjust( c1 ), ": ", str(val[1]).rjust( c2 ), val[2]
    

    # # simulator does not have freeze frame sensors
    # def scan_freeze_frame(self):
    #     """ Scan vehicle for freeze-frame sensor readings . """
    #     # one pass through the supported PIDs in mode 0x02, Freeze frame from when last DTC triggered
    #     for spid in self.suppPIDs:
    #         if spid[1] == '2' and spid not in feature_PIDs :
    #             #print "diag PID:", ipid, "supported"
    #             # debug
    #             #print "Checking FF sensor PID:", spid, "--",
    #             result = self.reader.OBD2_cmd(spid)
    #             # debug
    #             print result


    #
    # Some sample functions to show the info stored in the object
    #

    def show_basic_info(self):
        """ Show general information. """
        # just interprets self.info for CLI, GUI would directly read self.info
        print "VIN".rjust(16),           ": ", self.info['7E8']['VIN']
        print "Year".rjust(16),          ": ", self.info['7E8']['Year']
        print "Manufacturer".rjust(16),  ": ", self.info['7E8']['Make']
        print "Model".rjust(16),         ": ", self.info['7E8']['Model']
        print "Complies with".rjust(16), ": ", OBD_standards[self.info['7E8']['OBD_std']]
        print "Fuel type".rjust(16),     ": ", fuel_types[self.info['7E8']['fuel_type']]
        print "Calibration".rjust(16),   ": ", self.info['7E8']['Calibration']


    def show_obd2_status(self):
        """ Show status of obd2 monitors and related information. """
        # just interprets self.obd2_status for CLI, GUI would directly read self.info
        pass





# ----



