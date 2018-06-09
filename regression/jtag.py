#!/usr/bin/env python
#a Copyright
#  
#  This file 'riscv_minimal.py' copyright Gavin J Stark 2017
#  
#  This program is free software; you can redistribute it and/or modify it under
#  the terms of the GNU General Public License as published by the Free Software
#  Foundation, version 2.0.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even implied warranty of MERCHANTABILITY
#  or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
#  for more details.

#a Imports
import pycdl
import sys, os, unittest, tempfile
import simple_tb
import dump

#a Useful functions
def int_of_bits(bits):
    l = len(bits)
    m = 1<<(l-1)
    v = 0
    for b in bits:
        v = (v>>1) | (m*b)
        pass
    return v

def bits_of_n(nbits, n):
    bits = []
    for i in range(nbits):
        bits.append(n&1)
        n >>= 1
        pass
    return bits

#a Globals
riscv_regression_dir      = "../riscv_tests_built/isa/"
riscv_atcf_regression_dir = "../riscv-atcf-tests/build/dump/"

#a Test classes
#c c_jtag_apb_time_test_base
class c_jtag_apb_time_test_base(simple_tb.base_th):
    #f jtag_reset
    def jtag_reset(self):
        """
        Reset the jtag - this requires 5 clocks with TMS high.

        This leaves the JTAG state machine in reset
        """
        self.jtag__tms.drive(1)
        self.jtag__tdi.drive(0)
        self.bfm_wait(5)
        pass

    #f jtag_tms
    def jtag_tms(self, tms_values):
        """
        Scan in a number of TMS values, to move the state machine on
        """
        for tms in tms_values:
            self.jtag__tms.drive(tms)
            self.bfm_wait(1)
            pass
        pass

    #f jtag_shift
    def jtag_shift(self, tdi_values):
        """
        Shift in data from tdi_values, and transition out of shift mode
        Record the shifted out data and return it.
        Leave the JTAG state machine in Exit1.

        This assumes the state machine is in a shift mode to start
        with.  It runs the JTAG with TMS low for all except the last
        tdi_values bit.  Then it runs with TMS high so that the last
        bit is shifted in, and the state machine moves to exit1.

        """
        bits = []
        self.jtag__tms.drive(0)
        for tdi in tdi_values[:-1]:
            self.jtag__tdi.drive(tdi)
            self.bfm_wait(1)
            bits.append(self.tdo.value())
            pass
        self.jtag__tms.drive(1)
        self.jtag__tdi.drive(tdi_values[-1])
        self.bfm_wait(1)
        bits.append(self.tdo.value())
        return bits

    #f jtag_read_idcodes
    def jtag_read_idcodes(self):
        """
        Read the JTAG idcodes on the scan chain. Return a list of 32-bit integer IDCODEs.

        This resets the JTAG state machine, and then enters shift-dr.
        In reset the JTAG TAP controllers should set the IR for IDCODE reading.
        IDCODEs are guaranteed to be 32 bits, with a bottom bit set.

        Hence one can scan out 32-bit values from the chain while the first bit out is set.

        Leaves the state machine in shift-dr
        """
        self.jtag_reset()
        self.jtag_tms([0,1,0,0]) # Put in to shift-dr
        idcodes = []
        while True:
            bits = []
            self.bfm_wait(1)
            bits.append(self.tdo.value())
            if bits[0]==0: break
            for i in range(31):
                self.bfm_wait(1)
                bits.append(self.tdo.value())
                pass
            idcode = int_of_bits(bits)
            idcodes.append(idcode)
            pass
        return idcodes

    #f jtag_write_irs
    def jtag_write_irs(self,ir_bits):
        """
        Requires the JTAG state machine to be in reset or idle

        Move to shift-ir, and shift in the bits, then revert back to idle (not through reset!)
        """
        self.jtag_tms([0,1,1,0,0]) # Put in Shift-IR
        self.jtag_shift(ir_bits) # Leaves it in Exit1-IR
        self.jtag_tms([1,0]) # Dump it back in to idle
        pass

    #f jtag_write_drs
    def jtag_write_drs(self,dr_bits):
        """
        Scan data into the data register, and return data scanned out.
        Requires the JTAG state machine to be in reset or idle.

        Move to shift-dr, and shift in the bits, then revert back to idle (not through reset!)
        """
        self.jtag_tms([0,1,0,0]) # Put in Shift-DR
        data = self.jtag_shift(dr_bits) # Leaves it in Exit1-DR
        self.jtag_tms([1,0]) # Dump it back in to idle
        return data

    #f apb_write
    def apb_write(self, address, data, write_ir=False):
        """
        Requires the JTAG state machine to be in reset or idle.

        Writes the IR to be 'access' if required, then does the appropriate write access.
        """
        if write_ir:
            self.jtag_write_irs(ir_bits = bits_of_n(5,0x11)) # Send in 0x11 (apb_access)
            pass
        data = self.jtag_write_drs(dr_bits = bits_of_n(50,((address&0xffff)<<34)|((data&0xffffffff)<<2)|(2)))
        return data

    #f apb_read_slow
    def apb_read_slow(self, address, write_ir=False):
        """
        Requires the JTAG state machine to be in reset or idle.

        Writes the IR to be 'access' if required, then does the appropriate read access; it then waits and does another operation to get the data back
        """
        if write_ir:
            self.jtag_write_irs(ir_bits = bits_of_n(5,0x11)) # Send in 0x11 (apb_access)
            pass
        data = self.jtag_write_drs(dr_bits = bits_of_n(50,((address&0xffff)<<34)|(0<<2)|(1)))
        self.bfm_wait(100)
        data = self.jtag_write_drs(dr_bits = bits_of_n(50,0))
        return int_of_bits(data)

    #f apb_read_pipelined
    def apb_read_pipelined(self, address):
        """
        Requires the JTAG state machine to be in reset or idle.

        Peforms the appropriate read access and returns the last data
        """
        data = self.jtag_write_drs(dr_bits = bits_of_n(50,((address&0xffff)<<34)|(0<<2)|(1)))
        return int_of_bits(data)

    #f run
    def run(self):
        self.sim_msg = self.sim_message()
        self.bfm_wait(10)
        simple_tb.base_th.run_start(self)

        self.finishtest(0,"")
        pass

#c c_jtag_apb_time_test_idcode
class c_jtag_apb_time_test_idcode(c_jtag_apb_time_test_base):
    #f run
    def run(self):
        self.sim_msg = self.sim_message()
        self.bfm_wait(10)
        simple_tb.base_th.run_start(self)

        idcodes = self.jtag_read_idcodes()
        if len(idcodes)==1:
            if idcodes[0] != 0xabcde6e3:
                self.failtest(0,"Expected idcode of 0xabcde6e3 but got %08x"%idcodes[0])
                pass
            pass
        else:
            self.failtest(0,"Expected a single idcode")
            pass

        self.finishtest(0,"")
        pass
    pass

#c c_jtag_apb_time_test_time_slow
class c_jtag_apb_time_test_time_slow(c_jtag_apb_time_test_base):
    #f run
    def run(self):
        self.sim_msg = self.sim_message()
        self.bfm_wait(10)
        simple_tb.base_th.run_start(self)

        idcodes = self.jtag_reset()
        self.jtag_write_irs(ir_bits = bits_of_n(5,0x10)) # Send in 0x10 (apb_control)
        self.jtag_write_drs(dr_bits = bits_of_n(32,0))   # write apb_control of 0

        timer_readings = []
        for i in range(5):
            timer_readings.append(self.apb_read_slow(0x1200, write_ir=True))
            print "APB timer read returned address/data/status of %016x"%(timer_readings[-1]<<2)
            if (timer_readings[-1]&3)!=0:
                self.failtest(i,"Expected APB op to have succeeded (got %016x)"%(timer_readings[-1]<<2))
                pass
            pass
        timer_diffs = []
        total_diff = 0
        for i in range(len(timer_readings)-1):
            timer_diffs.append( (timer_readings[i+1] - timer_readings[i])>>2 )
            total_diff += timer_diffs[-1]
            pass

        avg_diff = total_diff / (0. + len(timer_diffs))

        for t in timer_diffs:
            if abs(t-avg_diff)>2:
                self.failtest(0,"Expected timer diff between reads (%d) to be not far from average of %d"%(t,avg_diff))
            pass
        pass

        self.finishtest(0,"")
        pass
    pass

#c c_jtag_apb_time_test_time_fast
class c_jtag_apb_time_test_time_fast(c_jtag_apb_time_test_base):
    #f run
    def run(self):
        self.sim_msg = self.sim_message()
        self.bfm_wait(10)
        simple_tb.base_th.run_start(self)

        idcodes = self.jtag_reset()
        self.jtag_write_irs(ir_bits = bits_of_n(5,0x10)) # Send in 0x10 (apb_control)
        self.jtag_write_drs(dr_bits = bits_of_n(32,0))   # write apb_control of 0
        self.jtag_write_irs(ir_bits = bits_of_n(5,0x11)) # Send in 0x11 (apb_access)

        timer_readings = []
        for i in range(10):
            timer_readings.append(self.apb_read_pipelined(0x1200))
            print "APB timer read returned address/data/status of %016x"%(timer_readings[-1]<<2)
            if (timer_readings[-1]&3)!=0:
                self.failtest(i,"Expected APB op to have succeeded (got %016x)"%(timer_readings[-1]<<2))
                pass
            pass

        timer_readings = timer_readings[2:]
        timer_diffs = []
        total_diff = 0
        for i in range(len(timer_readings)-1):
            timer_diffs.append( (timer_readings[i+1] - timer_readings[i])>>2 )
            total_diff += timer_diffs[-1]
            pass

        avg_diff = total_diff / (0. + len(timer_diffs))

        for t in timer_diffs:
            if abs(t-avg_diff)>2:
                self.failtest(0,"Expected timer diff between reads (%d) to be not far from average of %d"%(t,avg_diff))
            pass
        pass

        print timer_diffs

        self.finishtest(0,"")
        pass
    pass

#c c_jtag_apb_time_test_time_fast2
class c_jtag_apb_time_test_time_fast2(c_jtag_apb_time_test_base):
    #f run
    def run(self):
        self.sim_msg = self.sim_message()
        self.bfm_wait(10)
        simple_tb.base_th.run_start(self)

        idcodes = self.jtag_reset()
        self.jtag_write_irs(ir_bits = bits_of_n(5,0x10)) # Send in 0x10 (apb_control)
        self.jtag_write_drs(dr_bits = bits_of_n(32,0))   # write apb_control of 0
        self.jtag_write_irs(ir_bits = bits_of_n(5,0x11)) # Send in 0x11 (apb_access)

        timer_readings = []
        for i in range(10):
            timer_readings.append(self.apb_read_pipelined(0x1200))
            self.bfm_wait(20) # Delay so that the next read captures the result of this request (provide update to capture delay that exceeds APB transaction + sync time)
            print "APB timer read returned address/data/status of %016x"%(timer_readings[-1]<<2)
            if (timer_readings[-1]&3)!=0:
                self.failtest(i,"Expected APB op to have succeeded (got %016x)"%(timer_readings[-1]<<2))
                pass
            pass

        timer_readings = timer_readings[1:]
        timer_diffs = []
        total_diff = 0
        for i in range(len(timer_readings)-1):
            timer_diffs.append( (timer_readings[i+1] - timer_readings[i])>>2 )
            total_diff += timer_diffs[-1]
            pass

        avg_diff = total_diff / (0. + len(timer_diffs))

        for t in timer_diffs:
            if abs(t-avg_diff)>2:
                self.failtest(0,"Expected timer diff between reads (%d) to be not far from average of %d"%(t,avg_diff))
            pass
        pass

        print timer_diffs

        self.finishtest(0,"")
        pass
    pass

#c c_jtag_apb_time_test_old
class c_jtag_apb_time_test_old(c_jtag_apb_time_test_base):
    def __init__(self, **kwargs):
        c_jtag_apb_time_test_base.__init__(self, **kwargs)
        pass
    #f run
    def run(self):
        self.sim_msg = self.sim_message()
        self.bfm_wait(10)
        simple_tb.base_th.run_start(self)

        idcodes = self.jtag_reset()
        self.jtag_write_irs(ir_bits = bits_of_n(5,0x10)) # Send in 0x10 (apb_control)
        self.jtag_write_drs(dr_bits = bits_of_n(32,0))   # write apb_control of 0
        
        print "%016x"%(self.apb_read_slow(0x1200, write_ir=True)<<2)
        print "%016x"%(self.apb_read_slow(0x1200, write_ir=True)<<2)
        print "%016x"%(self.apb_read_slow(0x1200, write_ir=True)<<2)
        print "%016x"%(self.apb_read_slow(0x1200, write_ir=True)<<2) # return this data (X)
        print "%016x"%(self.apb_read_pipelined(0x1200)<<2) # Start read (will give Y), return last read data (X)
        print "%016x"%(self.apb_read_pipelined(0x1200)<<2) # Start another read, last access has not finished when this starts so returns last-but-one-data (X)
        print "%016x"%(self.apb_read_pipelined(0x1200)<<2) # Start another read, last access has not finished when this starts so returns last-but-one-data (Y)
        print "%016x"%(self.apb_read_pipelined(0x1200)<<2)
        print "%016x"%(self.apb_read_pipelined(0x1200)<<2)

        #self.bfm_wait(self.run_time-10)
        #self.ios.b.drive(1)

        self.finishtest(0,"")
        pass
    pass

#a Hardware classes
#c jtag_apb_timer_hw
class jtag_apb_timer_hw(simple_tb.cdl_test_hw):
    """
    
    """
    loggers = {#"itrace": {"verbose":0, "filename":"itrace.log", "modules":("dut.trace "),},
               }
    th_forces = { "th.clock":"clk",
                  "th.inputs":("tdo"),
                  "th.outputs":("jtag__ntrst jtag__tms jtag__tdi" ),
                  }
    module_name = "tb_jtag_apb_timer"
    clocks = {"jtag_tck":(0,3,3),
              "apb_clock":(0,2,2),
              }
    #f __init__
    def __init__(self, test):
        self.th_forces = self.th_forces.copy()
        simple_tb.cdl_test_hw.__init__(self,test)
        pass
    pass

#a Simulation test classes
#c jtag_apb_timer
class jtag_apb_timer(simple_tb.base_test):
    pass


#c Add tests to riscv_minimal and riscv_minimal_single_memory
test_dir = ""
tests = { "idcode"     : (c_jtag_apb_time_test_idcode,2*1000),
          "timer_slow" : (c_jtag_apb_time_test_time_slow,8*1000),
          "timer_fast" : (c_jtag_apb_time_test_time_fast,8*1000),
          "timer_fast2" : (c_jtag_apb_time_test_time_fast2,6*1000),
           }
for tc in tests:
    (tf,num_cycles) = tests[tc]
    def test_fn(c, tf=tf, num_cycles=num_cycles):
        test = tf()
        hw = jtag_apb_timer_hw(test)
        c.do_test_run(hw, num_cycles=num_cycles)
        pass
    setattr(jtag_apb_timer, "test_"+tc, test_fn)
    pass
pass
