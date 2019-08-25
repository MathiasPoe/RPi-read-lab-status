import collections
import pickle as pk
from Adafruit_MAX31856 import MAX31856 as MAX31856

MACHINE='LT'

HELIUM_CHECK = '/pressure-logs/measure-helium-LT'
HELIUM_LOG = '/pressure-logs/helium-LT-%Y.log'
PRESSURE_LOGS = '/pressure-logs/%Y/pressure-LT-%Y-%m-%d.log'

COM_PORT_MAXIGAUGE = '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A505YB2G-if00-port0'
COM_PORT_MVC_GAUGE_PREP = None
COM_PORT_MVC_GAUGE_STM = None
COM_PORT_ION_PREP = None
COM_PORT_ION_CRYO = None
COM_PORT_ION_STM = None

HELIUM=True

FPS_SHOW=False

GRADIENT = 30  # calc gradient from last n seconds
GRADIENT_RUNEVERY = 5  # save past values every n seconds
GRADIENT_SHOW = 60  # show gradient per n seconds

# temperature chip
SPI0_DEV = 0
SPI0_CS0 = 0
SPI0_CS0_temp_type = MAX31856.MAX31856_K_TYPE
SPI0_CS1 = 1
SPI0_CS1_temp_type = MAX31856.MAX31856_K_TYPE

SPI1_DEV = None
SPI1_CS0 = None
SPI0_CS0_temp_type = MAX31856.MAX31856_K_TYPE
SPI1_CS1 = None
SPI0_CS1_temp_type = MAX31856.MAX31856_K_TYPE

data = collections.OrderedDict()
# unit: unit in which the values are measure (mbar, K, C, A)
# color: color which is used in the GUI
# sensor type: sensor with which values are recorded (maxigauges, ADC_diods, ADC_resistor, SPI0, SPI1, mvc_stm, mvc_prep, ser_ion_stm, ser_ion_cryo, ser_ion_prep)
# sensor: sensor number (channel)
# value: current value (initial value -4000 - Not found)
# limit_max: if value > limit_max -> # WARNING:
# limit_max_warning: warning, which appears if value > limit_max
# format: format of value displayed in GUI (check https://www.programiz.com/python-programming/methods/string/format )
# format_gradient: format of gradient displayed in GUI
# log_to_file: shuld value be logged? Yes -> True, No -> False
# gui_size: size of value in GUI (1 or 2)
# gui_order: set order for appearance in GUI
# used_sensor: sensor assigned to value (None at beginning)
data['PSTM'] = {'unit': 'mbar',
                     'color': '#837C00',
                     'sensor_type': 'maxigauges',
                     'sensor': 1,
                     'status': 5,
                     'value': -4000,
                     'limit_max': 1e-7,
                     'limit_max_warning': 'Cryo chamber pressure is high',
                     'format': '.2e',
                     'format_gradient': '.0e',
                     'log_to_file': True,
                     'gui_size': 2,
                     'gui_order': 0,
                     'used_sensor':None}
data['PROU'] = {'unit': 'mbar',
                     'color': '#606060',
                     'sensor_type': 'maxigauges',
                     'sensor': 2,
                     'status': 5,
                     'value': -4000,
                     'limit_max': 2e1,
                     'limit_max_warning': 'Rough pump pressure is high',
                     'format': '.2e',
                     'log_to_file': True,
                     'gui_size': 1,
                     'gui_order': 6,
                     'used_sensor':None}
data['PPRP'] = {'unit': 'mbar',
                     'color': '#E6DD23',
                     'sensor_type': 'maxigauges',
                     'sensor': 3,
                     'status': 5,
                     'value': -4000,
                     'limit_max': 1e-4,
                     'limit_max_warning': 'Prep chamber pressure is high',
                     'format': '.2e',
                     'format_gradient': '.0e',
                     'log_to_file': True,
                     'gui_size': 2,
                     'gui_order': 1,
                     'used_sensor':None}
data['TSTM'] = {'unit': 'K',
                     'color': '#AC0D2F',
                     'sensor_type': 'ADC_diods',
                     'sensor': 0,
                     'status': 5,
                     'limit_max': 40,
                     'limit_max_warning': 'STM temperature is high',
                     'value': -4000,
                     'format': '.3f',
                     'format_gradient': '.2f',
                     'log_to_file': True,
                     'gui_size': 2,
                     'gui_order': 2,
                     'used_sensor':None}
data['TCRY'] = {'unit': 'K',
                     'color': '#606060',
                     'sensor_type': 'ADC_diods',
                     'sensor': 2,
                     'status': 5,
                     'value': -4000,
                     'limit_max': 10,
                     'limit_max_warning': 'Cryo temperature is high',
                     'format': '.3f',
                     'format_gradient': '.2f',
                     'log_to_file': True,
                     'gui_size': 1,
                     'gui_order': 8,
                     'used_sensor':None}
data['TSAM'] = {'unit': 'C',
                     'color': '#ABDA21',
                     'sensor_type': 'SPI0',
                     'sensor': 'CS0',
                     'status': 5,
                     'value': -4000,
                     'format': '.2f',
                     'format_gradient': '.1f',
                     'log_to_file': True,
                     'gui_size': 2,
                     'gui_order': 4,
                     'used_sensor':None}
data['TMAN'] = {'unit': 'C',
                     'color': '#606060',
                     'sensor_type': 'ADC_resistor',
                     'sensor': 1,
                     'status': 5,
                     'value': -4000,
                     'limit_max': 80,
                     'limit_max_warning': 'Manipulator temperature is high',
                     'format': '.2f',
                     'format_gradient': '.1f',
                     'log_to_file': True,
                     'gui_size': 2,
                     'gui_order': 5,
                     'used_sensor':None}
data['TLAB'] = {'unit': 'C',
                     'color': '#606060',
                     'sensor_type': 'SPI0',
                     'sensor': 'CS0',
                     'status': 5,
                     'value': -4000,
                     'format': '.2f',
                     'log_to_file': True,
                     'gui_size': 1,
                     'gui_order': 7,
                     'used_sensor':None}


# variuos
kel_cel = -273.15
date_fmt = '%Y-%m-%d_%H:%M:%S'
date_fmt_day = '%Y-%m-%d'
date_fmt_display = '%b %d, %H:%M:%S'
date_fmt_display_he = '%b %d, %H:%M'
date_fmt_display_he_short = '%H:%M'

# wireless outlet
A_ON = '010101100001000001001010111111111'
A_OFF = '010110100001000001001010111111111'
delay_shorten = 0.00005  # delays wil be made shorter to account for command execution time
short_delay = 0.00058 - delay_shorten
long_delay = 0.00116 - delay_shorten
extended_delay = 0.00716
TRANSMIT_PIN = 26  # adc

# temperature chip
SPI_DEV=0
SPI_PORT=0

#adc
ADC_ADDR_DIODS = 0x48
ADC_ADDR_VARIOUS = 0x49

# decoding
conv_to_decode = {0: 0, 1: 1e-12, 2: -1000, 3: -2000, 4: -3000, 5: -4000, 6: -5000}
decoding_dict = {1e-12: 'Underrange', -1000: 'Overrange', -2000: 'Error', -3000: 'Off', -4000: 'Not found', -5000: 'ID error'}

# temperature calibrations
# voltage to temperature calibration for diode measuerement
temp_calib_diode = pk.load(open("tempdiode.pickle", "rb"))
# voltage to temperature calibration for type-k thermocouple
temp_calib_type_K = pk.load(open("temptypek.pickle", "rb"))
# resistance to temperature calibration for pt100 sensor
temp_calib_resistor = pk.load(open("tempresistor.pickle", "rb"))

# GUI
FONT_FAMILY = 'Liberation Mono'
COLOR_BACKGROUND_WINDOW = '#030919'
COLOR_BACKGROUND = '#030919'
COLOR_TIME = "#4A63A1"
COLOR_HELIUM = "#606060"
COLOR_status_gui_inactive = '#303030'
COLOR_status_gui_active = '#a0a0a0'
COLOR_status_gui_warning = '#f06060'
COLOR_button_helium_bg = '#303030'
COLOR_button_helium_fg = '#f06020'

COLOR_gradient_brightness_factor = 0.4
COLOR_gradient_unit_brightness_factor = 0.3
FONT_SCALING = 2.0

height_ratio_time = 4
height_ratio_normal = 6
height_ratio_small = 3
height_ratio_helium = 4

font_ratio_time = 0.75
font_ratio_small = 0.5
font_ratio_gradient = 0.40
font_ratio_gradient_unit = 0.35
font_ratio_helium = 0.75
font_size_gui = 15

measure_animations = [
    [u"\u25DC", u"\u25DD", u"\u25DE", u"\u25DF"],
    ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"],
    ["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"],
    ["⠋","⠙","⠚","⠞","⠖","⠦","⠴","⠲","⠳","⠓"],
    ["⠄","⠆","⠇","⠋","⠙","⠸","⠰","⠠","⠰","⠸","⠙","⠋","⠇","⠆"],
    ["⠋","⠙","⠚","⠒","⠂","⠂","⠒","⠲","⠴","⠦","⠖","⠒","⠐","⠐","⠒","⠓","⠋"],
    ["⠁","⠉","⠙","⠚","⠒","⠂","⠂","⠒","⠲","⠴","⠤","⠄","⠄","⠤","⠴","⠲","⠒","⠂","⠂","⠒","⠚","⠙","⠉","⠁"],
    ["⠁","⠁","⠉","⠙","⠚","⠒","⠂","⠂","⠒","⠲","⠴","⠤","⠄","⠄","⠤","⠠","⠠","⠤","⠦","⠖","⠒","⠐","⠐","⠒","⠓","⠋","⠉","⠈","⠈"],
    ["⢹","⢺","⢼","⣸","⣇","⡧","⡗","⡏"],
    ["⢄","⢂","⢁","⡁","⡈","⡐","⡠"],
    ["⠁","⠂","⠄","⡀","⢀","⠠","⠐","⠈"],
    ["_","_","_","-","`","`","'","´","-","_","_","_"],
    ["☱","☲","☴"],
    #["🙈","🙈","🙉","🙊"],
    #["😄","😝"],
    #["🕛","🕐","🕑","🕒","🕓","🕔","🕕","🕖","🕗","🕘","🕙","🕚"],
    #["🌍","🌎","🌏"],
	#["🌑","🌒","🌓","🌔","🌕","🌖","🌗","🌘"],
    #["🚶","🏃"],
    ["◐","◓","◑","◒"],
    ["▖","▘","▝","▗"],
]
measure_animations_speed = [
    80,
    80,
    80,
    80,
    80,
    80,
    80,
    80,
    80,
    80,
    100,
    70,
    100,
    #300,
    #200,
    #100,
    #180,
    #80,
    #140,
    50,
    120,
]
