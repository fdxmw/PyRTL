import io
import unittest

import pyrtl
from pyrtl.corecircuits import _basic_add

# the code below disables testing of CompiledSim on systems where there does
# not appear to be the right version of gcc.  This is a not an ideal way to check
# and more work is required to more elegantly check compiledsim across multiple
# architectures.
import subprocess
try:
    version = subprocess.check_output(['gcc', '--version'])
except OSError:
    raise unittest.SkipTest('CompiledSimulation testing requires gcc')


class TraceWithBasicOpsBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()
        self.bitwidth = 3
        self.r = pyrtl.Register(bitwidth=self.bitwidth, name='r')
        self.o = pyrtl.Output(bitwidth=self.bitwidth, name='o')
        self.o <<= self.r

    def check_trace(self, correct_string):
        wtt = pyrtl.working_block().wirevector_subset(pyrtl.Output)
        sim_trace = pyrtl.SimulationTrace(wires_to_track=wtt)
        sim = self.sim(tracer=sim_trace)
        for i in range(8):
            sim.step()
        output = io.StringIO()
        sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), correct_string)

    def test_not_simulation(self):
        self.r.next <<= ~ self.r
        self.check_trace('o 07070707\n')

    def test_and_simulation(self):
        self.r.next <<= (~ self.r) & pyrtl.Const(6, bitwidth=self.bitwidth)
        self.check_trace('o 06060606\n')

    def test_nand_simulation(self):
        self.r.next <<= self.r.nand(pyrtl.Const(6, bitwidth=self.bitwidth))
        self.check_trace('o 07171717\n')

    def test_or_simulation(self):
        result = self.r | pyrtl.Const(4, bitwidth=self.bitwidth)
        self.r.next <<= result
        self.assertEqual(len(result), self.bitwidth)
        self.check_trace('o 04444444\n')

    def test_xor_simulation(self):
        self.r.next <<= self.r ^ pyrtl.Const(4, bitwidth=self.bitwidth)
        self.check_trace('o 04040404\n')

    def test_plus_simulation(self):
        self.r.next <<= self.r + pyrtl.Const(2, bitwidth=self.bitwidth)
        self.check_trace('o 02460246\n')

    def test_minus_simulation(self):
        self.r.next <<= self.r - pyrtl.Const(1, bitwidth=self.bitwidth)
        self.check_trace('o 07654321\n')

    def test_minus_sim_overflow(self):
        pyrtl.reset_working_block()
        i = pyrtl.Input(8, 'i')
        o = pyrtl.Output(name='o')
        o <<= i - 1

        tracer = pyrtl.SimulationTrace()
        sim = self.sim(tracer=tracer)
        sim.step({i: 1})
        sim.step({i: 0})
        self.assertEqual(tracer.trace['o'], [0, 0x1ff])

    def test_multiply_simulation(self):
        self.r.next <<= self.r * pyrtl.Const(2, bitwidth=self.bitwidth) + \
            pyrtl.Const(1, bitwidth=self.bitwidth)
        self.check_trace('o 01377777\n')

    def test_const_nobitwidth_simulation(self):
        self.r.next <<= self.r - pyrtl.Const(1)
        self.check_trace('o 07654321\n')

    def test_const_rawint_simulation(self):
        self.r.next <<= self.r - 1
        self.check_trace('o 07654321\n')

    def test_const_verilogsmall_simulation(self):
        self.r.next <<= self.r - "1'b1"
        self.check_trace('o 07654321\n')

    def test_const_verilogbig_simulation(self):
        self.r.next <<= self.r - "3'b1"
        self.check_trace('o 07654321\n')

    def test_const_veriloghuge_simulation(self):
        self.r.next <<= self.r - "64'b1"
        self.check_trace('o 07654321\n')

    def test_const_veriloghuge2_simulation(self):
        self.r.next <<= self.r + "64'b1"
        self.check_trace('o 01234567\n')

    def test_const_associativity_string_simulation(self):
        self.r.next <<= "64'b1" + self.r
        self.check_trace('o 01234567\n')

    def test_const_associativity_int_simulation(self):
        self.r.next <<= 1 + self.r
        self.check_trace('o 01234567\n')

    def test_bitslice_and_concat_simulation(self):
        left = self.r[0:-1]
        right = pyrtl.Const(1, bitwidth=1)
        self.r.next <<= pyrtl.concat(left, right)
        self.check_trace('o 01377777\n')

    def test_bitslice2_and_concat_simulation(self):
        left = self.r[:-1]
        right = pyrtl.Const(1, bitwidth=1)
        self.r.next <<= pyrtl.concat(left, right)
        self.check_trace('o 01377777\n')

    def test_reg_to_reg_simulation(self):
        self.r2 = pyrtl.Register(bitwidth=self.bitwidth, name='r2')
        self.r.next <<= self.r2
        self.r2.next <<= self.r + pyrtl.Const(2, bitwidth=self.bitwidth)
        self.o2 = pyrtl.Output(bitwidth=self.bitwidth, name='o2')
        self.o2 <<= self.r2
        self.check_trace(' o 00224466\no2 02244660\n')

    def test_less_than_cmp_simulation(self):
        left = self.r[0:-1]
        right = pyrtl.Const(1, bitwidth=1)
        self.r.next <<= left < right
        self.check_trace('o 01010101\n')

    def test_equals_simulation(self):
        left = self.r[0:-1]
        right = pyrtl.Const(0, bitwidth=1)
        self.r.next <<= left == right
        self.check_trace('o 01010101\n')


class PrintTraceBase(unittest.TestCase):
    # note: doesn't include tests for compact=True because all the tests test that
    def setUp(self):
        pyrtl.reset_working_block()
        self.in1 = pyrtl.Input(8, "in1")
        self.in2 = pyrtl.Input(8, "in2")
        self.out = pyrtl.Output(16, "out")

    def test_print_trace_single_dig_notcompact(self):
        self.out <<= pyrtl.probe(self.in1, "in1_probe") + self.in2
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        for i in range(5):
            sim.step({
                self.in1: i,
                self.in2: 5 - i
            })
        correct_outp = ("      --- Values in base 10 ---\n"
                        "in1       0 1 2 3 4\n"
                        "in1_probe 0 1 2 3 4\n"
                        "in2       5 4 3 2 1\n"
                        "out       5 5 5 5 5\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_outp)

    def test_print_trace_base2(self):
        self.out <<= pyrtl.probe(self.in1, "in1_probe") + self.in2
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        for i in range(5):
            sim.step({
                self.in1: 4 * i,
                self.in2: 4 * (5 - i)
            })
        correct_outp = ("      --- Values in base 2 ---\n"
                        "in1           0   100  1000  1100 10000\n"
                        "in1_probe     0   100  1000  1100 10000\n"
                        "in2       10100 10000  1100  1000   100\n"
                        "out       10100 10100 10100 10100 10100\n")
        output = io.StringIO()
        sim_trace.print_trace(output, base=2)
        self.assertEqual(output.getvalue(), correct_outp)

    def test_print_trace_base8(self):
        self.out <<= pyrtl.probe(self.in1, "in1_probe") + self.in2
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        for i in range(5):
            sim.step({
                self.in1: 6 * i,
                self.in2: 6 * (5 - i)
            })
        correct_outp = ("      --- Values in base 8 ---\n"
                        "in1        0  6 14 22 30\n"
                        "in1_probe  0  6 14 22 30\n"
                        "in2       36 30 22 14  6\n"
                        "out       36 36 36 36 36\n")
        output = io.StringIO()
        sim_trace.print_trace(output, base=8)
        self.assertEqual(output.getvalue(), correct_outp)

    def test_print_trace_base16(self):
        self.out <<= pyrtl.probe(self.in1, "in1_probe") * self.in2
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        for i in range(5):
            sim.step({
                self.in1: 9 * i,
                self.in2: 9 * (5 - i)
            })
        correct_outp = ("      --- Values in base 16 ---\n"
                        "in1         0   9  12  1b  24\n"
                        "in1_probe   0   9  12  1b  24\n"
                        "in2        2d  24  1b  12   9\n"
                        "out         0 144 1e6 1e6 144\n")
        output = io.StringIO()
        sim_trace.print_trace(output, base=16)
        self.assertEqual(output.getvalue(), correct_outp)


class SimWithSpecialWiresBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()

    def test_reg_directly_before_reg(self):
        pass

    def test_weird_wire_names(self):
        """
        Some simulations need to be careful when handling special names
        (eg Fastsim June 2016)
        """
        i = pyrtl.Input(8, '"182&!!!\n')
        o = pyrtl.Output(8, '*^*)#*$\'*')
        o2 = pyrtl.Output(8, 'test@+')
        w = pyrtl.WireVector(8, '[][[-=--09888')
        r = pyrtl.Register(8, '&@#)^#@^&(asdfkhafkjh')

        w <<= i
        r.next <<= i
        o <<= w
        o2 <<= r

        trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=trace)

        sim.step({i: 28})
        self.assertEqual(trace.trace[o.name], [28])
        sim.step({i: 233})
        self.assertEqual(trace.trace[o2.name], [0, 28])

    def test_fastsim_wire_names(self):
        """ Testing ability to use wire names instead of wires in input"""
        in1 = pyrtl.Input(8, "in1")
        in2 = pyrtl.Input(8, "in2")
        in3 = pyrtl.Input(8, "in3")
        truth = pyrtl.Const(1, 1)
        out1 = pyrtl.Output(16, "out2")
        out2 = pyrtl.Output(16, "out3")
        out1 <<= in1 + in2
        out2 <<= in3 | truth
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        for i in range(10):
            sim.step({
                'in1': 2 * i,
                'in2': 3 * i,
                'in3': 40 - 2 * i
            })
        correct_outp = (" --- Values in base 10 ---\n"
                        "in1   0  2  4  6  8 10 12 14 16 18\n"
                        "in2   0  3  6  9 12 15 18 21 24 27\n"
                        "in3  40 38 36 34 32 30 28 26 24 22\n"
                        "out2  0  5 10 15 20 25 30 35 40 45\n"
                        "out3 41 39 37 35 33 31 29 27 25 23\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_outp)


class SimInputValidationBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()

    def test_input_out_of_bitwidth(self):
        counter = pyrtl.Register(bitwidth=3, name='counter')
        i = pyrtl.Input(bitwidth=2, name='i')
        counter.next <<= counter + i

        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        for cycle in range(4):
            sim.step({i: cycle})
        with self.assertRaises(pyrtl.PyrtlError):
            sim.step({i: 5})


class SimStepMultipleBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()
        in1 = pyrtl.Input(4, "in1")
        in2 = pyrtl.Input(4, "in2")
        out1 = pyrtl.Output(4, "out1")
        out1 <<= (in1 ^ in2) + pyrtl.Const(1)
        out2 = pyrtl.Output(4, "out2")
        out2 <<= in1 | in2
        self.inputs = {
            'in1': [0, 1, 3, 15, 14],
            'in2': '66666',  # When a string, assumes each input is a single digit integer
        }

    def test_step_multiple_nsteps_no_inputs(self):
        pyrtl.reset_working_block()
        a = pyrtl.Register(8)
        b = pyrtl.Output(8, 'b')
        a.next <<= a + 1
        b <<= a

        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        sim.step_multiple(nsteps=5)

        correct_output = ("--- Values in base 10 ---\n"
                          "b 0 1 2 3 4\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_output)

    def test_step_multiple_nsteps_gt_ninputs(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        with self.assertRaises(pyrtl.PyrtlError) as error:
            sim.step_multiple(self.inputs, nsteps=6)
        self.assertEqual(str(error.exception),
                         'nsteps is specified but is greater than the '
                         'number of values supplied for each input')

    def test_step_multiple_no_inputs(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        with self.assertRaises(pyrtl.PyrtlError) as error:
            sim.step_multiple()
        self.assertEqual(str(error.exception),
                         'need to supply either input values '
                         'or a number of steps to simulate')

    def test_step_multiple_bad_nsteps1(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        with self.assertRaises(pyrtl.PyrtlError) as error:
            sim.step_multiple({'in1': [], 'in2': []})
        self.assertEqual(str(error.exception),
                         'must simulate at least one step')

    def test_step_multiple_bad_nsteps2(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        with self.assertRaises(pyrtl.PyrtlError) as error:
            sim.step_multiple(self.inputs, nsteps=-1)
        self.assertEqual(str(error.exception),
                         'must simulate at least one step')

    def test_step_multiple_no_values_for_each_step_of_input(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        with self.assertRaises(pyrtl.PyrtlError) as error:
            sim.step_multiple({'in1': [0, 1, 3], 'in2': [1]})
        self.assertEqual(str(error.exception),
                         'must supply a value for each provided wire '
                         'for each step of simulation')

    def test_step_multiple_no_values_for_each_step_of_given_outputs(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        with self.assertRaises(pyrtl.PyrtlError) as error:
            sim.step_multiple(self.inputs,
                              {'out1': [7, 8, 6, 10, 9],
                               'out2': [6, 7, 7, 15]})
        self.assertEqual(str(error.exception),
                         'any expected outputs must have a supplied value '
                         'each step of simulation')

    def test_step_multiple_no_expected_check(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        sim.step_multiple(self.inputs)

        correct_output = (" --- Values in base 10 ---\n"
                          "in1   0  1  3 15 14\n"
                          "in2   6  6  6  6  6\n"
                          "out1  7  8  6 10  9\n"
                          "out2  6  7  7 15 14\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_output)

    def test_step_multiple_no_errors(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        expected = {
            'out1': [7, 8, 6, 10, 9],
            'out2': [6, 7, 7, 15, 14],
        }
        sim.step_multiple(self.inputs, expected)

        correct_output = (" --- Values in base 10 ---\n"
                          "in1   0  1  3 15 14\n"
                          "in2   6  6  6  6  6\n"
                          "out1  7  8  6 10  9\n"
                          "out2  6  7  7 15 14\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_output)

    def test_step_multiple_dont_care_expected(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        expected = {
            'out1': [7, '?', 6, 10],
            'out2': '6?7?',
        }
        sim.step_multiple(self.inputs, expected, nsteps=4)

        correct_output = (" --- Values in base 10 ---\n"
                          "in1   0  1  3 15\n"
                          "in2   6  6  6  6\n"
                          "out1  7  8  6 10\n"
                          "out2  6  7  7 15\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_output)

    def test_step_multiple_no_errors_nsteps_specified(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        expected = {
            'out1': [7, 8, 6, 10, 9],
            'out2': [6, 7, 7, 15, 14],
        }
        sim.step_multiple(self.inputs, expected, nsteps=3)

        correct_output = (" --- Values in base 10 ---\n"
                          "in1  0 1 3\n"
                          "in2  6 6 6\n"
                          "out1 7 8 6\n"
                          "out2 6 7 7\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_output)

    def test_step_multiple_many_errors_report_only_first(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        expected = {
            'out1': [7, 9, 4, 10, 9],
            'out2': [6, 2, 7, 8, 14],
        }
        output = io.StringIO()
        sim.step_multiple(self.inputs, expected, file=output, stop_after_first_error=True)

        # Test the output about unexpected values
        correct_output = ("Unexpected output (stopped after step with first error):\n"
                          " step       name expected   actual\n"
                          "    1       out1        9        8\n"
                          "    1       out2        2        7\n")
        self.assertEqual(output.getvalue(), correct_output)

        # Test that the trace stopped after the step with the first error
        correct_output = (" --- Values in base 10 ---\n"
                          "in1  0 1\n"
                          "in2  6 6\n"
                          "out1 7 8\n"
                          "out2 6 7\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_output)

    def test_step_multiple_many_errors_report_all(self):
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)

        expected = {
            'out1': [7, 9, 4, 10, 9],
            'out2': [6, 2, 7, 8, 14],
        }
        output = io.StringIO()
        sim.step_multiple(self.inputs, expected, file=output)

        # Test the output about unexpected values
        correct_output = ("Unexpected output on one or more steps:\n"
                          " step       name expected   actual\n"
                          "    1       out1        9        8\n"
                          "    1       out2        2        7\n"
                          "    2       out1        4        6\n"
                          "    3       out2        8       15\n")
        self.assertEqual(output.getvalue(), correct_output)

        # Test that the trace still produced all the steps
        correct_output = (" --- Values in base 10 ---\n"
                          "in1   0  1  3 15 14\n"
                          "in2   6  6  6  6  6\n"
                          "out1  7  8  6 10  9\n"
                          "out2  6  7  7 15 14\n")
        output = io.StringIO()
        sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_output)


class TraceWithAdderBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()
        bitwidth = 3
        self.r = pyrtl.Register(bitwidth=bitwidth, name='r')
        self.result = _basic_add(self.r, pyrtl.Const(1).zero_extended(bitwidth))
        self.r.next <<= self.result
        self.o = pyrtl.Output(bitwidth=bitwidth, name='o')
        self.o <<= self.r

    def test_adder_simulation(self):
        sim_trace = pyrtl.SimulationTrace(wires_to_track=[self.o])
        on_reset = {}  # signal states to be set when reset is asserted
        # build the actual simulation environment
        sim = self.sim(register_value_map=on_reset, default_value=0, tracer=sim_trace)

        # step through 15 cycles
        for i in range(15):
            sim.step()

        output = io.StringIO()
        sim_trace.print_trace(output, compact=True)
        file = io.StringIO()
        sim_trace.render_trace(file=file)  # want to make sure the code at least runs
        self.assertEqual(output.getvalue(), 'o 012345670123456\n')


class SimulationVCDWithAdderBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()
        bitwidth = 3
        self.r = pyrtl.Register(bitwidth=bitwidth, name='r')
        self.result = _basic_add(self.r, pyrtl.Const(1).zero_extended(bitwidth))
        self.r.next <<= self.result
        self.o = pyrtl.Output(bitwidth=bitwidth, name='o')
        self.o <<= self.r

    VCD_OUTPUT = """$timescale 1ns $end
$scope module logic $end
$var wire 3 o o $end
$upscope $end
$enddefinitions $end
$dumpvars
b0 o
$end
#0
b0 o

#10
b1 o

#20
b10 o

#30
b11 o

#40
b100 o

#50
b101 o

#60
b110 o

#70
b111 o

#80
b0 o

#90
b1 o

#100
b10 o

#110
b11 o

#120
b100 o

#130
b101 o

#140
b110 o

#150
"""

    def test_vcd_output(self):
        sim_trace = pyrtl.SimulationTrace(wires_to_track=[self.o])
        on_reset = {}  # signal states to be set when reset is asserted
        # build the actual simulation environment
        sim = self.sim(register_value_map=on_reset, default_value=0, tracer=sim_trace)

        # step through 15 cycles
        for i in range(15):
            sim.step()

        test_output = io.StringIO()
        sim_trace.print_vcd(test_output)
        self.assertEqual(self.VCD_OUTPUT, test_output.getvalue())


class SimTraceWithMuxBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()
        bitwidth = 3
        self.a = pyrtl.Input(bitwidth=bitwidth)
        self.b = pyrtl.Input(bitwidth=bitwidth)
        self.sel = pyrtl.Input(bitwidth=1)
        self.muxout = pyrtl.Output(bitwidth=bitwidth, name='muxout')
        self.muxout <<= pyrtl.mux(self.sel, self.a, self.b)

        # build the actual simulation environment
        self.sim_trace = pyrtl.SimulationTrace()
        self.sim = self.sim(tracer=self.sim_trace)

    def test_adder_simulation(self):
        input_signals = {0: {self.a: 0, self.b: 1, self.sel: 1},
                         1: {self.a: 0, self.b: 2, self.sel: 1},
                         2: {self.a: 0, self.b: 0, self.sel: 1},
                         3: {self.a: 1, self.b: 1, self.sel: 0},
                         4: {self.a: 2, self.b: 1, self.sel: 0},
                         5: {self.a: 0, self.b: 1, self.sel: 0}}
        for i in range(6):
            self.sim.step(input_signals[i])

        output = io.StringIO()
        self.sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), 'muxout 120120\n')


class MemBlockBase(unittest.TestCase):

    def setUp(self):
        pyrtl.reset_working_block()
        self.bitwidth = 3
        self.addrwidth = 3
        self.output1 = pyrtl.Output(self.bitwidth, "o1")
        self.output2 = pyrtl.Output(self.bitwidth, "o2")
        self.read_addr1 = pyrtl.Input(self.addrwidth)
        self.read_addr2 = pyrtl.Input(self.addrwidth)
        self.write_addr = pyrtl.Input(self.addrwidth)
        self.write_data = pyrtl.Input(self.bitwidth)
        self.mem1 = pyrtl.MemBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth, name='mem1')
        self.mem2 = pyrtl.MemBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth, name='mem2')
        self.output1 <<= self.mem1[self.read_addr1]
        self.output2 <<= self.mem1[self.read_addr2]
        self.mem1[self.write_addr] <<= self.write_data

        # build the actual simulation environment
        self.sim_trace = pyrtl.SimulationTrace()

    def test_simple_memblock(self):
        sim = self.sim(tracer=self.sim_trace)

        input_signals = [[0, 1, 4, 5],
                         [4, 1, 0, 5],
                         [0, 4, 1, 6],
                         [1, 1, 0, 0],
                         [6, 0, 6, 7]]
        for signals in input_signals:
            sim.step({self.read_addr1: signals[0], self.read_addr2: signals[1],
                      self.write_addr: signals[2], self.write_data: signals[3]})

        output = io.StringIO()
        self.sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), 'o1 05560\no2 00560\n')

    def test_simple2_memblock(self):
        sim = self.sim(tracer=self.sim_trace)
        input_signals = [
            {self.read_addr1: 0, self.read_addr2: 1, self.write_addr: 0, self.write_data: 0x7},
            {self.read_addr1: 1, self.read_addr2: 2, self.write_addr: 1, self.write_data: 0x6},
            {self.read_addr1: 0, self.read_addr2: 0, self.write_addr: 2, self.write_data: 0x5},
            {self.read_addr1: 0, self.read_addr2: 1, self.write_addr: 0, self.write_data: 0x4},
            {self.read_addr1: 1, self.read_addr2: 0, self.write_addr: 1, self.write_data: 0x3},
            {self.read_addr1: 2, self.read_addr2: 2, self.write_addr: 2, self.write_data: 0x2},
            {self.read_addr1: 1, self.read_addr2: 2, self.write_addr: 0, self.write_data: 0x1},
            {self.read_addr1: 0, self.read_addr2: 1, self.write_addr: 1, self.write_data: 0x0},
            {self.read_addr1: 1, self.read_addr2: 0, self.write_addr: 2, self.write_data: 0x7},
            {self.read_addr1: 2, self.read_addr2: 1, self.write_addr: 0, self.write_data: 0x6}]

        for signal in input_signals:
            sim.step(signal)

        output = io.StringIO()
        self.sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), 'o1 0077653107\no2 0076452310\n')

    def test_synth_simple_memblock(self):
        pyrtl.synthesize()
        pyrtl.optimize()
        self.sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=self.sim_trace)
        input_signals = [[0, 1, 4, 5],
                         [4, 1, 0, 5],
                         [0, 4, 1, 6],
                         [1, 1, 0, 0],
                         [6, 0, 6, 7]]
        for signals in input_signals:
            sim.step({self.read_addr1: signals[0], self.read_addr2: signals[1],
                      self.write_addr: signals[2], self.write_data: signals[3]})

        output = io.StringIO()
        self.sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), 'o1 05560\no2 00560\n')

    def test_mem_val_map(self):
        read_addr3 = pyrtl.Input(self.addrwidth)
        self.output3 = pyrtl.Output(self.bitwidth, "o3")
        self.output3 <<= self.mem2[read_addr3]
        mem_val_map = {self.mem1: {0: 0, 1: 1, 2: 2, 3: 3},
                       self.mem2: {0: 4, 1: 5, 2: 6, 3: 7}}
        self.sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=self.sim_trace, memory_value_map=mem_val_map)
        # put new entries in
        for i in range(2):
            sim.step({
                self.read_addr1: 4 + i,  # d.c.
                self.read_addr2: 4 + i,  # d.c.
                read_addr3: 2,
                self.write_addr: 4 + i,  # put a 4 and a 5 in the 4th and 5th addr of mem1
                self.write_data: 4 + i
            })
        # modify existing entries
        for i in range(2):
            sim.step({
                self.read_addr1: 1 + i,  # d.c.
                self.read_addr2: 1 + i,  # d.c.
                read_addr3: 2,
                self.write_addr: 1 + i,  # put a 2 and a 3 in the 1st and 2nd addr of mem1
                self.write_data: 2 + i
            })
        # check consistency of memory_value_map assignment, insertion, and modification
        self.assertEqual(sim.inspect_mem(self.mem1), {0: 0, 1: 2, 2: 3, 3: 3, 4: 4, 5: 5})

    def test_mem_val_map_defaults(self):
        read_addr3 = pyrtl.Input(self.addrwidth)
        self.output3 = pyrtl.Output(self.bitwidth, "o3")
        self.output3 <<= self.mem2[read_addr3]
        mem_val_map = {self.mem1: {0: 0, 1: 1},
                       self.mem2: {0: 4, 1: 5}}
        self.sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=self.sim_trace, memory_value_map=mem_val_map)
        for i in range(2, 8):
            sim.step({
                self.read_addr1: i,
                self.read_addr2: 8 - i + 1,
                read_addr3: i,
                self.write_addr: 0,
                self.write_data: 0
            })
        output = io.StringIO()
        self.sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), 'o1 000000\n'
                                            'o2 000000\n'
                                            'o3 000000\n')

    def test_mem_val_map_empty_mapping(self):
        read_addr3 = pyrtl.Input(self.addrwidth)
        self.output3 = pyrtl.Output(self.bitwidth, "o3")
        self.output3 <<= self.mem2[read_addr3]
        mem_val_map = {self.mem1: {0: 0, 1: 1},
                       self.mem2: {}}
        self.sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=self.sim_trace, memory_value_map=mem_val_map)
        for i in range(2, 8):
            sim.step({
                self.read_addr1: i,
                self.read_addr2: 8 - i + 1,
                read_addr3: i,
                self.write_addr: 0,
                self.write_data: 0
            })
        output = io.StringIO()
        self.sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), 'o1 000000\n'
                                            'o2 000000\n'
                                            'o3 000000\n')


class MemBlockLargeBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()
        self.bitwidth = 68
        self.addrwidth = 32
        self.output1 = pyrtl.Output(self.bitwidth, "o1")
        self.output2 = pyrtl.Output(self.bitwidth, "o2")
        self.read_addr1 = pyrtl.Input(self.addrwidth)
        self.read_addr2 = pyrtl.Input(self.addrwidth)
        self.write_addr = pyrtl.Input(self.addrwidth)
        self.write_data = pyrtl.Input(self.bitwidth)
        self.mem = pyrtl.MemBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth, name='mem')
        self.output1 <<= self.mem[self.read_addr1]
        self.output2 <<= self.mem[self.read_addr2]
        self.mem[self.write_addr] <<= self.write_data

        # build the actual simulation environment
        self.sim_trace = pyrtl.SimulationTrace()

    def test_mem_blocks_very_large(self):
        ''' Tests support of very large memories (i.e. address width > 30 bits),
            and that limbs are handled appropriately for bitwidths > 64 '''
        sim = self.sim(tracer=self.sim_trace)

        write_data = 0x20000000040000012  # 68 bits
        input_signals = [[0, 1, 0xffffffff, write_data],
                         [0xffffffff, 1, 0, write_data],
                         [0, 0xffffffff, 0xf0000001, 6],
                         [0xf0000001, 0xf0000001, 0, 0],
                         [6, 0, 6, 7]]
        for signals in input_signals:
            sim.step({self.read_addr1: signals[0], self.read_addr2: signals[1],
                      self.write_addr: signals[2], self.write_data: signals[3]})

        output = io.StringIO()
        correct_outp = ("--- Values in base 10 ---\n"
                        "o1                    0 %d %d                    6                    0\n"
                        "o2                    0                    0 %d                    6                    0\n"  # noqa
                        % (write_data, write_data, write_data))
        self.sim_trace.print_trace(output)
        self.assertEqual(output.getvalue(), correct_outp)


class RegisterDefaultsBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()
        self.i = pyrtl.Input(bitwidth=3)
        self.r1 = pyrtl.Register(name='r1', bitwidth=3)
        self.r2 = pyrtl.Register(name='r2', bitwidth=3, reset_value=7)
        self.o = pyrtl.Output(name='o', bitwidth=3)
        self.r1.next <<= self.i
        self.r2.next <<= self.r1
        self.o <<= self.r2

    def check_trace(self, correct_string, **kwargs):
        wtt = pyrtl.working_block().wirevector_subset(pyrtl.Output)
        sim_trace = pyrtl.SimulationTrace(wires_to_track=wtt)
        sim = self.sim(tracer=sim_trace, **kwargs)
        for i in range(8):
            sim.step({self.i: i})
        output = io.StringIO()
        sim_trace.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), correct_string)

    def test_reset_value(self):
        self.check_trace('o 70012345\n')

    def test_register_map_overrides_reset_value(self):
        self.check_trace('o 36012345\n', register_value_map={self.r1: 6, self.r2: 3})

    def test_partial_map(self):
        self.check_trace('o 76012345\n', register_value_map={self.r1: 6})

    def test_partial_map_overrides_default(self):
        self.check_trace('o 76012345\n', default_value=5, register_value_map={self.r1: 6})

    def test_default_used_for_non_reset_value(self):
        self.check_trace('o 75012345\n', default_value=5)


class RomBlockSimBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()

    def generate_expected_output(self, data_tuples, length):
        """dataTuple is in a series of tuples in  (name, function) format
            the function takes in a single argument, length
           length is the number of steps in the length """

        out_string = ""
        for tuple in data_tuples:
            out_string = out_string + tuple[0] + " "
            for time in range(0, length - 1):
                out_string += str(tuple[1](time))
            out_string += '\n'
        return out_string

    def compareIO(self, sim_trace_a, expected_output):
        output = io.StringIO()
        sim_trace_a.print_trace(output, compact=True)
        self.assertEqual(output.getvalue(), expected_output)

    def rom_block_test_helper(self, bitwidth):

        def rom_data_function(add):
            return int((add + 5) / 2)

        pyrtl.reset_working_block()
        self.bitwidth = bitwidth
        self.addrwidth = 4
        self.output1 = pyrtl.Output(self.bitwidth, "o1")
        self.output2 = pyrtl.Output(self.bitwidth, "o2")
        self.read_addr1 = pyrtl.Input(self.addrwidth)
        self.read_addr2 = pyrtl.Input(self.addrwidth)
        self.rom = pyrtl.RomBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth,
                                  name='rom', romdata=rom_data_function)
        self.output1 <<= self.rom[self.read_addr1]
        self.output2 <<= self.rom[self.read_addr2]
        # build the actual simulation environment
        self.sim_trace = pyrtl.SimulationTrace()
        self.sim = self.sim(tracer=self.sim_trace)

        input_signals = {}
        for i in range(0, 5):
            input_signals[i] = {self.read_addr1: i, self.read_addr2: 2 * i}
            self.sim.step(input_signals[i])

        exp_out = self.generate_expected_output((("o1", lambda x: rom_data_function(x)),
                                                 ("o2", lambda x: rom_data_function(2 * x))), 6)
        self.compareIO(self.sim_trace, exp_out)

    def test_function_rom_block_bitwidth_4(self):
        self.rom_block_test_helper(4)

    def test_function_rom_block_bitwidth_12(self):
        self.rom_block_test_helper(12)

    def test_function_rom_block_bitwidth_32(self):
        self.rom_block_test_helper(32)

    def test_function_rom_block_bitwidth_64(self):
        self.rom_block_test_helper(64)

    def rom_block_with_optimization_helper(self, bitwidth):

        def rom_data_function(add):
            return int((add + 5) / 2)

        pyrtl.reset_working_block()
        self.bitwidth = bitwidth
        self.addrwidth = 4
        self.output1 = pyrtl.Output(self.bitwidth, "o1")
        self.output2 = pyrtl.Output(self.bitwidth, "o2")

        self.read_addr1 = pyrtl.Input(self.addrwidth)
        self.read_addr2 = pyrtl.Input(self.addrwidth)
        self.rom = pyrtl.RomBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth,
                                  name='rom', romdata=rom_data_function)
        self.output1 <<= self.rom[self.read_addr1]
        self.output2 <<= self.rom[self.read_addr2]

        pyrtl.synthesize()
        pyrtl.optimize()
        # build the actual simulation environment
        self.sim_trace = pyrtl.SimulationTrace()
        self.sim = self.sim(tracer=self.sim_trace)

        input_signals = {}
        for i in range(0, 5):
            input_signals[i] = {self.read_addr1: i, self.read_addr2: 2 * i}
            input_signals[i] = {self.read_addr1: i, self.read_addr2: 2 * i}
            self.sim.step(input_signals[i])

        # exp_out = self.generate_expected_output((("o1", lambda x: rom_data_function(x) - 1),
        exp_out = self.generate_expected_output((("o1", lambda x: rom_data_function(x)),
                                                 ("o2", lambda x: rom_data_function(2 * x))), 6)
        self.compareIO(self.sim_trace, exp_out)

    def test_function_rom_block_with_optimization_bitwidth_4(self):
        self.rom_block_with_optimization_helper(4)

    def test_function_rom_block_with_optimization_bitwidth_12(self):
        self.rom_block_with_optimization_helper(12)

    def test_function_rom_block_with_optimization_bitwidth_32(self):
        self.rom_block_with_optimization_helper(32)

    def test_function_rom_block_with_optimization_bitwidth_64(self):
        self.rom_block_with_optimization_helper(64)

    def test_rom_out_of_range_error(self):
        rom_data_array = [15, 13, 11, 9, 7, 5, 3]
        rom1 = pyrtl.RomBlock(bitwidth=4, addrwidth=3, romdata=rom_data_array)
        rom_add_1 = pyrtl.Input(3, "rom_in")
        rom_out_1 = pyrtl.Output(4, "rom_out_1")
        rom_out_1 <<= rom1[rom_add_1]

        sim_trace = pyrtl.SimulationTrace()
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            self.sim(tracer=sim_trace)

    def test_rom_rom_block_in_memory_value_map_error(self):
        rom_data_array = [6]
        rom1 = pyrtl.RomBlock(bitwidth=4, addrwidth=1, romdata=rom_data_array)
        rom_addr = pyrtl.Input(1, "rom_addr")
        rom_out = pyrtl.Output(4, "rom_out")
        rom_out <<= rom1[rom_addr]
        mem_val_map = {rom1: {0: 0}}

        sim_trace = pyrtl.SimulationTrace()
        with self.assertRaises(pyrtl.PyrtlError) as error:
            self.sim(tracer=sim_trace, memory_value_map=mem_val_map)
        self.assertIn("memory_value_map", str(error.exception))

    def test_rom_val_map(self):
        def rom_data_function(add):
            return int((add + 5) / 2)
        dummy_in = pyrtl.Input(1, "dummy")
        self.bitwidth = 4
        self.addrwidth = 4
        self.rom1 = pyrtl.RomBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth,
                                   name='rom1', romdata=rom_data_function)
        self.rom2 = pyrtl.RomBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth,
                                   name='rom2', romdata=rom_data_function)
        mem_val_map = {self.rom1: {0: 0, 1: 1, 2: 2, 3: 3},
                       self.rom2: {0: 4, 1: 5, 2: 6, 3: 7}}

        self.sim_trace = pyrtl.SimulationTrace()
        with self.assertRaises(pyrtl.PyrtlError):
            sim = self.sim(tracer=self.sim_trace, memory_value_map=mem_val_map)

    def test_negative_memory_value_map(self):
        mem = pyrtl.MemBlock(addrwidth=3, bitwidth=3)
        counter = pyrtl.Register(bitwidth=mem.addrwidth)
        counter.next <<= counter + 1
        read_data = pyrtl.Output(name="read_data")
        read_data <<= mem[counter]
        memory_values = [-4, -3, -2, -1, 0, 1, 2, 3]
        memory_value_map = {index: value for index, value in enumerate(memory_values)}
        sim = self.sim(memory_value_map={mem: memory_value_map})
        for i in range(2 ** mem.addrwidth):
            sim.step()
            actual_read_data = pyrtl.val_to_signed_integer(sim.inspect("read_data"),
                                                           bitwidth=mem.bitwidth)
            self.assertEqual(actual_read_data, memory_value_map[i])

    def test_unsigned_memory_value_map(self):
        mem = pyrtl.MemBlock(addrwidth=3, bitwidth=3)
        counter = pyrtl.Register(bitwidth=mem.addrwidth)
        counter.next <<= counter + 1
        read_data = pyrtl.Output(name="read_data")
        read_data <<= mem[counter]
        memory_values = [0, 1, 2, 3, 4, 5, 6, 7]
        memory_value_map = {index: value for index, value in enumerate(memory_values)}
        sim = self.sim(memory_value_map={mem: memory_value_map})
        for i in range(2 ** mem.addrwidth):
            sim.step()
            actual_read_data = sim.inspect("read_data")
            self.assertEqual(actual_read_data, memory_value_map[i])


class InspectBase(unittest.TestCase):
    """
    Unittests for sim.inspect_mem
    """

    def setUp(self):
        pyrtl.reset_working_block()

    def test_inspect_mem(self):
        a = pyrtl.Input(8, 'a')
        b = pyrtl.Input(8, 'b')
        mem = pyrtl.MemBlock(8, 8, 'mem')
        mem[b] <<= a
        sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=sim_trace)
        self.assertEqual(sim.inspect_mem(mem), {})
        sim.step({a: 3, b: 23})
        self.assertEqual(sim.inspect_mem(mem), {23: 3})


class TraceErrorBase(unittest.TestCase):
    def setUp(self):
        pyrtl.reset_working_block()

    def test_empty_trace(self):
        with self.assertRaises(pyrtl.PyrtlError):
            self.sim_trace = pyrtl.SimulationTrace()

    def test_empty_trace_after_untraceable_removed(self):
        r = pyrtl.Register(2, 'r')
        r.next <<= r + 1
        sim = self.sim()
        sim.step_multiple(provided_inputs={}, nsteps=10)
        with self.assertRaises(pyrtl.PyrtlError) as ex:
            sim.tracer.render_trace()
        self.assertEqual(
            str(ex.exception),
            "Empty trace list. This may have occurred because "
            "untraceable wires were removed prior to simulation, "
            "if a CompiledSimulation was used."
        )

    def test_invalid_base(self):
        self.in1 = pyrtl.Input(8, "in1")
        self.out = pyrtl.Output(8, "out")
        self.out <<= self.in1
        self.sim_trace = pyrtl.SimulationTrace()
        sim = self.sim(tracer=self.sim_trace)
        for i in range(5):
            sim.step({self.in1: i})
        with self.assertRaises(pyrtl.PyrtlError):
            self.sim_trace.print_trace(base=4)


def make_unittests():
    """
    Generates separate unittests for each of the simulators
    """
    g = globals()
    unittests = {}
    base_tests = {name: v for name, v in g.items()
                  if isinstance(v, type) and issubclass(v, unittest.TestCase)}
    for name, v in base_tests.items():
        del g[name]
        if name[-4:].lower() == 'base':
            name = name[:-4]
        else:
            # Add Base to the end of your unittest name to tell this that you actually
            # made the unittest as such
            raise Exception("You should be making unittests that are compatible with"
                            "both Fastsim and Simulation")
        for sim in sims:
            unit_name = "Test" + name + sim.__name__
            unittests[unit_name] = type(unit_name, (v,), {'sim': sim})
    g.update(unittests)


sims = (pyrtl.CompiledSimulation,)
make_unittests()


if __name__ == '__main__':
    unittest.main()
