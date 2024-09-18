from litex.build.lattice import LatticeECP5Platform
from litex.gen import LiteXModule
from migen import *
from litex.build.generic_platform import Misc, Subsignal, Pins, IOStandard
from litespi.opcodes import SpiNorFlashOpCodes as Codes
from litespi.modules import W25Q64
from litex.soc.cores.clock import ECP5PLL
from litex.soc.integration.soc import SoCRegion
from ..hyperram import HyperRAM

from ..crg_ecp5 import CRG
from ..serial_led import SerialLedController

_io = [
    # Clk / Rst
    ("clk25", 0, Pins("128"), IOStandard("LVCMOS33")),
    ("clk125", 0, Pins("103"), IOStandard("LVCMOS33")),
    ("clk_rgmii", 0, Pins("105"), IOStandard("LVCMOS33")),

    # Leds
    ("rgb_led", 0,
        Subsignal("r", Pins("3")),
        Subsignal("g", Pins("142")),
        Subsignal("b", Pins("31")),
        IOStandard("LVCMOS33"),
    ),

    ("spiflash4x", 0,
        Subsignal("cs_n", Pins("49")),
        Subsignal("clk", Pins("54")),
        Subsignal("dq", Pins("47", "46", "45", "41")),
        IOStandard("LVCMOS33")
    ),

    ("serial", 0,
        Subsignal("tx", Pins("11")),
        Subsignal("rx", Pins("13")),
        IOStandard("LVCMOS33")
    ),

    ("ulpi", 0,
        Subsignal("rst_n",  Pins("82")),
        Subsignal("dir",  Pins("80")),
        Subsignal("clk",  Pins("84")),
        Subsignal("nxt",  Pins("79")),
        Subsignal("stp",  Pins("81")),
        Subsignal("data", Pins("78 77 76 74 73 72 71 69")),
        IOStandard("LVCMOS33")
    ),
    # RGMII Ethernetx
    ("eth_clocks", 0,
        Subsignal("tx", Pins("117")),
        Subsignal("rx", Pins("110")),
        IOStandard("LVCMOS33")
    ),
    ("eth", 0,
        Subsignal("rst_n",   Pins("124")),
        Subsignal("mdio",    Pins("107")),
        Subsignal("mdc",     Pins("108")),
        Subsignal("rx_ctl",  Pins("111")),
        Subsignal("rx_data", Pins("112 113 114 115"), Misc("PULLMODE=UP")), # RGMII mode - Advertise all capabilities.
        Subsignal("tx_ctl",  Pins("116")),
        Subsignal("tx_data", Pins("121 120 119 118")),
        IOStandard("LVCMOS33")
    ),

    # HyperRAM
    ("hyperram", 0,
        Subsignal("dq", Pins("93 99 90 92 91 94 97 98"), IOStandard("LVCMOS33")),
        Subsignal("rwds", Pins("95"), IOStandard("LVCMOS33")),
        Subsignal("cs_n", Pins("88"), IOStandard("LVCMOS33")),
        Subsignal("rst_n", Pins("89"), IOStandard("LVCMOS33")),
        Subsignal("clk", Pins("104"), IOStandard("LVCMOS33")),
        Subsignal("clk_n", Pins("102"), IOStandard("LVCMOS33")),
    ),

]

_connectors = [
    ("pmod1",
        {
            "1p": "26",
            "1n": "27",
            "2p": "24",
            "2n": "25",
            "3p": "28",
            "3n": "30",
            "4p": "22",
            "4n": "23",
         }
    ),
    ("pmod2",
        {
            "1p": "5",
            "1n": "7",
            "2p": "4",
            "2n": "6",
            "3p": "10",
            "3n": "12",
            "4p": "1",
            "4n": "2",
        }
    ),
]

class Platform(LatticeECP5Platform):
    default_clk_name   = "clk25"
    default_clk_period = 1e9/25e6

    def __init__(self, device="LFE5U-25F", revision="2.0", toolchain="trellis", **kwargs):
        assert device in ["LFE5U-12F", "LFE5U-25F", "LFE5U-45F", "LFE5U-85F"]
        assert revision in ["1.7", "2.0"]
        LatticeECP5Platform.__init__(self, device + "-7TG144C", _io, _connectors, toolchain=toolchain, **kwargs)

        self.add_extension([
            ('debug', 0,
                Subsignal('jtck', Pins('pmod2:1n')),
                Subsignal('jtck_dir', Pins('pmod2:2p')),
                Subsignal('jtms', Pins('pmod2:4n')),
                Subsignal('jtms_dir', Pins('pmod2:2n')),
                Subsignal('jtdo', Pins('pmod2:4p')),
                Subsignal('jtdi', Pins('pmod2:3n')),
                Subsignal('jtdi_dir', Pins('pmod2:1p')),

                Subsignal('nrst', Pins('pmod1:1n')),
                Subsignal('nrst_dir', Pins('pmod2:3p')),
            ),
            ('trace', 0,
                Subsignal('clk', Pins('pmod1:4n')),
                Subsignal('data', Pins('pmod1:2n pmod1:4p pmod1:3n pmod1:2p')),
            ),
        ])

    def get_crg(self, sys_clk_freq):
        crg = CRG(self, sys_clk_freq)
        # crg.add_usb()
        # crg.add_ulpi(self)
        return crg

    def get_flash_module(self):
        return W25Q64(Codes.READ_1_1_1)

    def add_leds(self, soc):
        soc.led_status = self.request('rgb_led', 0)

    def add_platform_specific(self, soc):
        # HyperRAM
        cdr = ClockDomainsRenamer({
            'hr':      'sys',
            'hr2x':    'sys2x',
            'hr_90':   'sys_90',
            'hr2x_90': 'sys2x_90',
        })

        pads = self.request('hyperram')

        soc.submodules.hyperram = cdr(HyperRAM(pads))
        soc.add_csr('hyperram')
        soc.bus.add_slave('hyperram', soc.hyperram.bus, SoCRegion(origin = soc.mem_map.get('hyperram', 0x20000000), size = 0x7FFFFF))

        soc.comb += pads.rst_n.eq(1)

    def do_finalize(self, fragment):
        LatticeECP5Platform.do_finalize(self, fragment)

        self.add_period_constraint(self.lookup_request("clk_ulpi", 0, loose=True), 1e9/60e6)
        self.add_period_constraint(self.lookup_request("trace:clk", 0, loose=True), 1e9/125e6)
        self.add_period_constraint(self.lookup_request("clk25", loose=True), 1e9/25e6)


    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--device', choices = ['LFE5U-25F', 'LFE5U-45F'], default = 'LFE5U-25F', help = 'ECP5 device (default: LFE5U-25F)')

    @classmethod
    def get_profile(cls, profile):
        return {
            'default': {
                'uart_name': 'serial',
                'uart_baudrate': 1e6,
                'with_debug': True,
                'with_trace': True,
                'with_target_power': False,
            },
        }[profile]
