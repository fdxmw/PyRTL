"""
Defines PyRTL memories.
These blocks of memories can be read (potentially async) and written (sync)

MemBlocks supports any number of the following operations:

* read: `d = mem[address]`
* write: `mem[address] <<= d`
* write with an enable: `mem[address] <<= MemBlock.EnabledWrite(d, enable=we)`

Based on the number of reads and writes a memory will be inferred
with the correct number of ports to support that
"""

import collections

from .pyrtlexceptions import PyrtlError
from .core import working_block, LogicNet, _NameIndexer, Block
from .wire import WireVector, Const, next_tempvar_name
from .corecircuits import as_wires
from .helperfuncs import infer_val_and_bitwidth
# ------------------------------------------------------------------------
#
#         ___        __   __          __        __   __
#   |\/| |__   |\/| /  \ |__) \ /    |__) |    /  \ /  ` |__/
#   |  | |___  |  | \__/ |  \  |     |__) |___ \__/ \__, |  \
#


_memIndex = _NameIndexer()

_MemAssignment = collections.namedtuple('_MemAssignment', 'rhs, is_conditional')
"""_MemAssignment is the type returned from assignment by |= or <<="""


def _reset_memory_indexer():
    global _memIndex
    _memIndex = _NameIndexer()


class _MemIndexed(WireVector):
    """ Object used internally to route memory assigns correctly.

    The normal PyRTL user should never need to be aware that this class exists,
    hence the underscore in the name.  It presents a very similar interface to
    WireVectors (all of the normal wirevector operations should still work),
    but if you try to *set* the value with <<= or |= then it will generate a
    _MemAssignment object rather than the normal wire assignment.
    """

    def __init__(self, mem, index):
        self.mem = mem
        self.index = index
        self.wire = None

    def __ilshift__(self, other):
        return _MemAssignment(rhs=other, is_conditional=False)

    def __ior__(self, other):
        return _MemAssignment(rhs=other, is_conditional=True)

    def _two_var_op(self, other, op):
        return as_wires(self)._two_var_op(other, op)

    def __invert__(self):
        return as_wires(self).__invert__()

    def __getitem__(self, item):
        return as_wires(self).__getitem__(item)

    def __len__(self):
        return self.mem.bitwidth

    def sign_extended(self, bitwidth):
        return as_wires(self).sign_extended(bitwidth)

    def zero_extended(self, bitwidth):
        return as_wires(self).zero_extended(bitwidth)

    @property
    def name(self):
        return as_wires(self).name

    @name.setter
    def name(self, n):
        as_wires(self).name = n


class MemBlock(object):
    """MemBlock is the object for specifying block memories. It can be indexed like an
    array for both reading and writing. Writes under a conditional are automatically
    converted to enabled writes. Consider the following examples where ``addr``,
    ``data``, and ``we`` are all WireVectors::

        data = memory[addr]  # create a read port
        memory[addr] <<= data  # create a write port
        mem[address] <<= MemBlock.EnabledWrite(data, enable=we)

    When the address of a memory is assigned to using an
    :class:`~.MemBlock.EnabledWrite` object, items will only be written to the memory
    when the ``enable`` WireVector is set to high (1).

    """
    # FIXME: write ports assume that only one port is under control of the conditional
    EnabledWrite = collections.namedtuple('EnabledWrite', 'data, enable')
    """Generates logic to conditionally enable a write port.

    ``data`` (the first field in the tuple) is the data to write, and ``enable`` (the
    second field) is a one bit signal specifying whether the write should happen (i.e.
    active high).

    """

    def __init__(self, bitwidth: int, addrwidth: int, name: str = '',
                 max_read_ports: int = 2, max_write_ports: int = 1,
                 asynchronous: bool = False, block: Block = None):
        """Create a PyRTL read-write memory.

        :param bitwidth: The bitwidth of each element in the memory.
        :param addrwidth: The number of bits used to address an element in the memory.
            The memory can store ``2 ** addrwidth`` elements.
        :param name: Name of the memory. Defaults to an autogenerated name.
        :param max_read_ports: limits the number of read ports each block can create;
            passing ``None`` indicates there is no limit.
        :param max_write_ports: limits the number of write ports each block can create;
            passing ``None`` indicates there is no limit.
        :param asynchronous: If ``False``, ensure that all memory inputs are registers,
            inputs, or constants. See the note about asynchronous memories below.
        :param block: The block to add the MemBlock to, defaults to the working block.

        ---------------------
        Asynchronous Memories
        ---------------------
        It is best practice to have memory operations start on a rising clock edge if
        you want them to synthesize into efficient hardware. MemBlocks will enforce this
        by checking that all their inputs are ready at each rising clock edge. This
        implies that all MemBlock inputs - the address to read/write, the data to write,
        and the write-enable bit - must be registers, inputs, or constants, unless you
        explicitly declare the memory as ``asynchronous=True``.

        Asynchronous memories can be convenient and tempting, but they are rarely a good
        idea. They can't be mapped to block RAMs in FPGAs and will be converted to
        registers by most design tools. They are not a realistic option for memories
        with more than a few hundred elements.

        --------------------
        Read and Write Ports
        --------------------
        Each read or write to the memory will create a new `port` (either a read port or
        write port respectively). By default memories are limited to 2 read ports and 1
        write port, to keep designs efficient by default, but those values can be
        changed. Note that memories with many ports may not map to physical memories
        such as block RAMs or existing memory hardware macros.

        --------------
        Default Values
        --------------
        In PyRTL simulations, all MemBlocks are zero-initialized by default. Initial
        data can be specified for each MemBlock in :meth:`.Simulation.__init__`'s
        ``memory_value_map``.

        ---------------------------
        Simultaneous Read and Write
        ---------------------------
        In PyRTL simulations, if the same address is read and written in the same cycle,
        the read will return the `last` value stored in the MemBlock, not the newly
        written value. Example::

            mem = pyrtl.MemBlock(addrwidth=1, bitwidth=1)
            mem[0] <<= 1
            read_data = pyrtl.Output(name="read_data", bitwidth=1)
            read_data <<= mem[0]

            # In the first cycle, read_data will be the default MemBlock data value (0),
            # not the newly written value (1).
            sim = pyrtl.Simulation()
            sim.step()
            print("Cycle 0 read_data", sim.inspect("read_data"))

            # In the second cycle, read_data will be the newly written value (1).
            sim.step()
            print("Cycle 1 read_data", sim.inspect("read_data"))

        -----------------------------
        Mapping MemBlocks to Hardware
        -----------------------------
        Synchronous MemBlocks can generally be mapped to FPGA block RAMs and similar
        hardware, but there are many pitfalls:

        #. ``asynchronous=False`` is generally necessary, but may not be sufficient, for
           mapping a design to FPGA block RAMs. Block RAMs may have additional timing
           constraints, like requiring register outputs for each block RAM.
           ``asynchronous=False`` only requires register inputs.
        #. Block RAMs may offer more or less read and write ports than MemBlock's
           defaults.
        #. Block RAMs may not zero-initialize by default.
        #. Block RAMs may implement simultaneous reads and writes in different ways.

        """
        self.max_read_ports = max_read_ports
        self.num_read_ports = 0
        self.block = working_block(block)
        name = next_tempvar_name(name)

        if bitwidth <= 0:
            raise PyrtlError('bitwidth must be >= 1')
        if addrwidth <= 0:
            raise PyrtlError('addrwidth must be >= 1')

        self.bitwidth = bitwidth
        self.name = name
        self.addrwidth = addrwidth
        self.readport_nets = []
        self.id = _memIndex.next_index()
        self.asynchronous = asynchronous
        self.block._add_memblock(self)

        self.max_write_ports = max_write_ports
        self.num_write_ports = 0
        self.writeport_nets = []

    @property
    def read_ports(self):
        raise PyrtlError('read_ports now called num_read_ports for clarity')

    def __getitem__(self, item) -> WireVector:
        """Create a read port to load items from the MemBlock."""
        item = as_wires(item, bitwidth=self.addrwidth, truncating=False)
        if len(item) > self.addrwidth:
            raise PyrtlError('memory index bitwidth > addrwidth')
        return _MemIndexed(mem=self, index=item)

    def __setitem__(self, item, assignment):
        """Create a write port to store items to the MemBlock."""
        if isinstance(assignment, _MemAssignment):
            self._assignment(item, assignment.rhs, is_conditional=assignment.is_conditional)
        else:
            raise PyrtlError('error, assigment to memories should use "<<=" not "=" operator')

    def _readaccess(self, addr):
        # FIXME: add conditional read ports
        return self._build_read_port(addr)

    def _build_read_port(self, addr):
        if self.max_read_ports is not None:
            self.num_read_ports += 1
            if self.num_read_ports > self.max_read_ports:
                raise PyrtlError('maximum number of read ports (%d) exceeded' % self.max_read_ports)
        data = WireVector(bitwidth=self.bitwidth)
        readport_net = LogicNet(
            op='m',
            op_param=(self.id, self),
            args=(addr,),
            dests=(data,))
        working_block().add_net(readport_net)
        self.readport_nets.append(readport_net)
        return data

    def _assignment(self, item, val, is_conditional):
        from .conditional import _build

        # Even though as_wires is already called on item already in the __getitem__ method,
        # we need to call it again here because __setitem__ passes the original item
        # to _assignment.
        addr = as_wires(item, bitwidth=self.addrwidth, truncating=False)

        if isinstance(val, MemBlock.EnabledWrite):
            data, enable = val.data, val.enable
        else:
            data, enable = val, Const(1, bitwidth=1)
        data = as_wires(data, bitwidth=self.bitwidth, truncating=False)
        enable = as_wires(enable, bitwidth=1, truncating=False)

        if len(data) != self.bitwidth:
            raise PyrtlError('error, write data larger than memory bitwidth')
        if len(enable) != 1:
            raise PyrtlError('error, enable signal not exactly 1 bit')

        if is_conditional:
            _build(self, (addr, data, enable))
        else:
            self._build(addr, data, enable)

    def _build(self, addr, data, enable):
        """ Builds a write port. """
        if self.max_write_ports is not None:
            self.num_write_ports += 1
            if self.num_write_ports > self.max_write_ports:
                raise PyrtlError('maximum number of write ports (%d) exceeded' %
                                 self.max_write_ports)
        writeport_net = LogicNet(
            op='@',
            op_param=(self.id, self),
            args=(addr, data, enable),
            dests=tuple())
        working_block().add_net(writeport_net)
        self.writeport_nets.append(writeport_net)

    def _make_copy(self, block=None):
        block = working_block(block)
        return MemBlock(bitwidth=self.bitwidth,
                        addrwidth=self.addrwidth,
                        name=self.name,
                        max_read_ports=self.max_read_ports,
                        max_write_ports=self.max_write_ports,
                        asynchronous=self.asynchronous,
                        block=block)


class RomBlock(MemBlock):
    """PyRTL Read Only Memory.

    RomBlocks are the read only memory block for PyRTL. They support the same read
    interface as :class:`MemBlock`, but they cannot be written to (i.e. there are no
    write ports). The ROM's contents are specified when the ROM is constructed.

    """
    def __init__(self, bitwidth: int, addrwidth: int, romdata, name: str = '',
                 max_read_ports: int = 2, build_new_roms: bool = False,
                 asynchronous: bool = False, pad_with_zeros: bool = False,
                 block: Block = None):
        """Create a PyRTL Read Only Memory.

        :param bitwidth: The bitwidth of each element in the ROM.
        :param addrwidth: The number of bits used to address an element in the ROM.
            The ROM can store ``2 ** addrwidth`` elements.
        :param romdata: Specifies the data stored in the ROM. This can either be a
            function or an array (iterable) that maps from address to data. Example::

                # Create a 4-element ROM, where:
                #   rom[0] == 4
                #   rom[1] == 5
                #   rom[2] == 6
                #   rom[3] == 7
                rom = RomBlock(bitwidth=3, addrwidth=2, romdata=[4, 5, 6, 7])
        :param name: The identifier for the memory.
        :param max_read_ports: limits the number of read ports each block can create;
            passing ``None`` indicates there is no limit.
        :param build_new_roms: indicates whether :meth:`RomBlock.__getitem__` should
            create copies of the RomBlock to avoid exceeding ``max_read_ports``.
        :param asynchronous: If ``False``, ensure that all RomBlock inputs are
            registers, inputs, or constants. See the notes about asynchronous memories
            in :meth:`MemBlock.__init__`.
        :param pad_with_zeros: If ``True``, fill any missing ``romdata`` with zeros so
            all accesses to the ROM are well defined. Otherwise, the simulation will
            throw an error when accessing unintialized data. If you are generating
            Verilog, you will need to specify a value for every address (in which case
            setting this to ``True`` will help), however for testing and simulation it
            useful to know if you are accessing an unspecified value (which is why it is
            ``False`` by default).
        :param block: The block to add to, defaults to the working block.

        """

        super(RomBlock, self).__init__(bitwidth=bitwidth, addrwidth=addrwidth, name=name,
                                       max_read_ports=max_read_ports, max_write_ports=0,
                                       asynchronous=asynchronous, block=block)
        self.data = romdata
        self.build_new_roms = build_new_roms
        self.current_copy = self
        self.pad_with_zeros = pad_with_zeros

    def __getitem__(self, item) -> WireVector:
        """Create a read port to load items from the RomBlock.

        If ``build_new_roms`` was specified, create a new copy of the RomBlock if the
        number of read ports exceeds ``max_read_ports``.

        """
        import numbers
        if isinstance(item, numbers.Number):
            raise PyrtlError("There is no point in indexing into a RomBlock with an int. "
                             "Instead, get the value from the source data for this Rom")
            # If you really know what you are doing, use a Const WireVector instead.
        return super(RomBlock, self).__getitem__(item)

    def __setitem__(self, item, assignment):
        raise PyrtlError('no writing to a read-only memory')

    def _get_read_data(self, address: int):
        """_get_read_data is called by the simulator to fetch RomBlock data.

        :param address: address is a dynamic run-time value (an integer), *not* a
            WireVector.

        """
        import types
        try:
            if address < 0 or address > 2**self.addrwidth - 1:
                raise PyrtlError("Invalid address, " + str(address) + " specified")
        except TypeError:
            raise PyrtlError("Address: {} with invalid type specified".format(address))
        if isinstance(self.data, types.FunctionType):
            try:
                value = self.data(address)
            except Exception:
                raise PyrtlError("Invalid data function for RomBlock")
        else:
            try:
                value = self.data[address]
            except KeyError:
                if self.pad_with_zeros:
                    value = 0
                else:
                    raise PyrtlError(
                        f"RomBlock key {address} is invalid, "
                        "consider using pad_with_zeros=True for defaults"
                    )
            except IndexError:
                if self.pad_with_zeros:
                    value = 0
                else:
                    raise PyrtlError(
                        f"RomBlock index {address} is invalid, "
                        "consider using pad_with_zeros=True for defaults"
                    )
            except Exception:
                raise PyrtlError("invalid type for RomBlock data object")

        try:
            value = infer_val_and_bitwidth(value, bitwidth=self.bitwidth).value
        except TypeError:
            raise PyrtlError("Value: {} from rom {} has an invalid type"
                             .format(value, self))
        return value

    def _build_read_port(self, addr):
        if self.build_new_roms and \
                (self.current_copy.num_read_ports >= self.current_copy.max_read_ports):
            self.current_copy = self._make_copy()
        return super(RomBlock, self.current_copy)._build_read_port(addr)

    def _make_copy(self, block=None,):
        block = working_block(block)
        return RomBlock(bitwidth=self.bitwidth, addrwidth=self.addrwidth,
                        romdata=self.data, name=self.name, max_read_ports=self.max_read_ports,
                        asynchronous=self.asynchronous, pad_with_zeros=self.pad_with_zeros,
                        block=block)
