# Status display for Raspberry Pi
#
# required software: python3.5 or newer, https://pypi.org/project/adafruit-circuitpython-ads1x15/0.5.3/
#
# enalbe GPIO and SPI on your RPi

import collections
import copy
import datetime as dt
from functools import wraps
import numpy as np
import pandas as pd
import pickle as pk
import os
import threading
import time
import serial
import board
import busio
import Adafruit_GPIO
from Adafruit_MAX31856 import MAX31856 as MAX31856
import adafruit_ads1x15.single_ended

import config as CFG    # config file - individual for every machine
import GUI              # GUI for visualization and interaction on screen


class measure:
    # decoding
    conv_to_decode = CFG.conv_to_decode
    decoding_dict = CFG.decoding_dict       # converts values to labels like 'Overrange', 'Off', ...

    # temperature calibrations
    # voltage to temperature calibration for diode measuerement
    temp_calib_diode = CFG.temp_calib_diode
    # voltage to temperature calibration for type-k thermocouple
    temp_calib_type_K = CFG.temp_calib_type_K
    # resistance to temperature calibration for pt100 sensor
    temp_calib_resistor = CFG.temp_calib_resistor

    def __init__(self):
        self.day_now = dt.datetime.now().strftime(CFG.date_fmt_day)     # get date of current day

        self.init_data_dict()       # get dictionary of values, which should be measured

        # for displaying gradients
        self.gradient_data_current = 0
        self.gradient_data_num = int(np.max(CFG.GRADIENT / CFG.GRADIENT_RUNEVERY))
        self.gradient_data = [copy.deepcopy(self.data) for _ in range(self.gradient_data_num)]  # we dont want references
        now = dt.datetime.now()
        self.gradient_data_timestamp = [now] * self.gradient_data_num

        self.sensor_types=list(set([self.data[key]['sensor_type'] for key in self.data]))   # get sensor types

        # initialize sensors
        for key in self.data:
            if self.data[key]['sensor_type'] in ['ADC_diods','ADC_resistor']:
                self.init_adc(key)
            if self.data[key]['sensor_type'] == 'maxigauges':
                self.init_serial_maxigauge(key)
            if self.data[key]['sensor_type'] == 'mvc_prep':
                self.init_serial_mvc_prep(key)
            if self.data[key]['sensor_type'] == 'mvc_stm':
                self.init_serial_mvc_stm(key)
            if self.data[key]['sensor_type'] == 'ser_ion_prep':
                self.init_serial_ion_prep(key)
            if self.data[key]['sensor_type'] == 'ser_ion_cryo':
                self.init_serial_ion_cryo(key)
            if self.data[key]['sensor_type'] == 'ser_ion_stm':
                self.init_serial_ion_stm(key)
            if self.data[key]['sensor_type'] == 'SPI0':
                if self.data[key]['sensor'] == 'CS0':
                    self.init_SPI0_CS0(key)
                if self.data[key]['sensor'] == 'CS1':
                    self.init_SPI0_CS1(key)
            if self.data[key]['sensor_type'] == 'SPI1':
                if self.data[key]['sensor'] == 'CS0':
                    self.init_SPI1_CS0(key)
                if self.data[key]['sensor'] == 'CS1':
                    self.init_SPI1_CS1(key)

        self.first_run = True

        # check if helium measurement is enabled
        if CFG.HELIUM != None:
            self.helium_status = {}
            self.helium_check = False
            self.helium_save = False
            self.helium_turn_sensor_off = False
            self.helium_turn_sensor_off_retries = 0

        # threads
        self.threads_running = {}
        self.lock = threading.Lock()

        self.log_writing_header = False

        # loop properties
        self.main_loop_time = 0.08
        self.main_loop_time_normal = 0.08
        self.main_loop_time_slow = 0.5

        self.time_loop = time.time()
        self.fps = ''

        self.gui = None

    def init_data_dict(self):
        # initialize data dictionary with for values which should be measured
        self.data=CFG.data

    def init_adc(self,key):
        # initialize analog-to-digital converter chip (adafruit_ads1x15)
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.adc = adafruit_ads1x15.single_ended.ADS1115(i2c, address=CFG.ADC_ADDR_VARIOUS)
            if self.data[key]['sensor_type'] not in ['ADC_diods','ADC_resistor']:
                self.data[key]['used_sensor']=self.adc
        except:
            self.adc = None
        try:
            self.adc2 = adafruit_ads1x15.single_ended.ADS1115(i2c, address=CFG.ADC_ADDR_DIODS)
            if self.data[key]['sensor_type'] in ['ADC_diods','ADC_resistor']:
                self.data[key]['used_sensor']=self.adc2
        except:
            self.adc2 = None

    def init_serial_maxigauge(self,key):
        # initialize maxigauges (pfeiffer)
        self.ser_maxi = None
        try:
            self.ser_maxi = serial.Serial(timeout=0.5,
                                     baudrate=9600,
                                     stopbits=serial.STOPBITS_ONE,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE
                                     )
            self.ser_maxi.port = CFG.COM_PORT_MAXIGAUGE
            self.ser_maxi.open()
            self.ser_maxi.reset_input_buffer()
            self.ser_maxi.reset_output_buffer()
            self.data[key]['used_sensor']=self.ser_maxi
        except:
            pass

    def init_serial_mvc_prep(self,key):
        # initialize pressure gauge (vacom) in prep chamber
        self.ser_mvc_prep = None
        try:
            self.ser_mvc_prep = serial.Serial(timeout=0.5,
                                     baudrate=19200,
                                     stopbits=serial.STOPBITS_ONE,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE
                                     )
            self.ser_mvc_prep.port = CFG.COM_PORT_MVC_GAUGE_PREP
            self.ser_mvc_prep.open()
            self.ser_mvc_prep.reset_input_buffer()
            self.ser_mvc_prep.reset_output_buffer()
            self.data[key]['used_sensor']=self.ser_mvc_prep
        except:
            pass

    def init_serial_mvc_stm(self,key):
        # initialize mvc pressure gauge (vacom) in stm/afm chamber
        self.ser_mvc_stm = None
        try:
            self.ser_mvc_stm = serial.Serial(timeout=0.5,
                                     baudrate=19200,
                                     stopbits=serial.STOPBITS_ONE,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE
                                     )
            self.ser_mvc_stm.port = CFG.COM_PORT_MVC_GAUGE_STM
            self.ser_mvc_stm.open()
            self.ser_mvc_stm.reset_input_buffer()
            self.ser_mvc_stm.reset_output_buffer()
            self.data[key]['used_sensor']=self.ser_mvc_stm
        except:
            pass

    def init_serial_ion_prep(self,key):
        # initialize ion pump (gamma vacuum) in prep chamber (AFM/XPS)
        self.ser_ion_prep = None
        try:
            self.ser_ion_prep = serial.Serial(timeout=0.5,
                                     baudrate=9600,
                                     stopbits=serial.STOPBITS_ONE,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE
                                     )
            self.ser_ion_prep.port = CFG.COM_PORT_ION_PREP
            self.ser_ion_prep.open()
            self.ser_ion_prep.reset_input_buffer()
            self.ser_ion_prep.reset_output_buffer()
            self.data[key]['used_sensor']=self.ser_ion_prep
        except:
            pass

    def init_serial_ion_cryo(self,key):
        # initialize ion pump (gamma vacuum) in cryo chamber (AFM)
        self.ser_ion_cryo = None
        try:
            self.ser_ion_cryo = serial.Serial(timeout=0.5,
                                     baudrate=9600,
                                     stopbits=serial.STOPBITS_ONE,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE
                                     )
            self.ser_ion_cryo.port = CFG.COM_PORT_ION_CRYO
            self.ser_ion_cryo.open()
            self.ser_ion_cryo.reset_input_buffer()
            self.ser_ion_cryo.reset_output_buffer()
            self.data[key]['used_sensor']=self.ser_ion_cryo
        except:
            pass

    def init_serial_ion_stm(self,key):
        # initialize ion pump (gamma vacuum) in stm chamber (XPS)
        self.ser_ion_stm = None
        try:
            self.ser_ion_stm = serial.Serial(timeout=0.5,
                                     baudrate=9600,
                                     stopbits=serial.STOPBITS_ONE,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE
                                     )
            self.ser_ion_stm.port = CFG.COM_PORT_ION_STM
            self.ser_ion_stm.open()
            self.ser_ion_stm.reset_input_buffer()
            self.ser_ion_stm.reset_output_buffer()
            self.data[key]['used_sensor']=self.ser_ion_stm
        except:
            pass

    def init_SPI0_CS0(self,key):
        # initialize temperature measuremeant via MAX31856 chip
        self.sensor_temp_sample = None
        try:
            self.sensor_temp_sample = MAX31856(hardware_spi=Adafruit_GPIO.SPI.SpiDev(
                CFG.SPI0_DEV, CFG.SPI0_CS0), tc_type=CFG.SPI0_CS0_temp_type, avgsel=0xF)  # 0x8 for 8 samples average, 0xF for 16
            self.data[key]['used_sensor']=self.sensor_temp_sample
        except:
            pass

    def init_SPI0_CS1(self,key):
        # initialize temperature measuremeant via MAX31856 chip
        self.sensor_temp_OMBE1 = None
        try:
            self.sensor_temp_OMBE1 = MAX31856(hardware_spi=Adafruit_GPIO.SPI.SpiDev(
                CFG.SPI0_DEV, CFG.SPI0_CS1), tc_type=CFG.SPI0_CS1_temp_type, avgsel=0xF)  # 0x8 for 8 samples average, 0xF for 16
            self.data[key]['used_sensor']=self.sensor_temp_OMBE1
        except:
            pass

    def init_SPI1_CS0(self,key):
        # initialize temperature measuremeant via MAX31856 chip
        self.sensor_temp_OMBE2 = None
        try:
            self.sensor_temp_OMBE2 = MAX31856(hardware_spi=Adafruit_GPIO.SPI.SpiDev(
                CFG.SPI1_DEV, CFG.SPI1_CS0), tc_type=CFG.SPI1_CS0_temp_type, avgsel=0xF)  # 0x8 for 8 samples average, 0xF for 16
            self.data[key]['used_sensor']=self.sensor_temp_OMBE2
        except:
            pass

    def init_SPI1_CS1(self,key):
        # initialize temperature measuremeant via MAX31856 chip
        self.sensor_temp_OMBE3 = None
        try:
            self.sensor_temp_OMBE3 = MAX31856(hardware_spi=Adafruit_GPIO.SPI.SpiDev(
                CFG.SPI1_DEV, CFG.SPI1_CS1), tc_type=CFG.SPI1_CS1_temp_type, avgsel=0xF)  # 0x8 for 8 samples average, 0xF for 16
            self.data[key]['used_sensor']=self.sensor_temp_OMBE3
        except:
            pass

    def _start_async(interval, check_lastrun=False):
        # decorator to start function as thread
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                self = args[0]
                if func.__name__ not in self.threads_running:
                    self.threads_running[func.__name__] = {}
                    self.threads_running[func.__name__]['lastrun'] = dt.datetime.now() - dt.timedelta(days=365 * 10)
                run_thread = False
                if 'thread' not in self.threads_running[func.__name__]:
                    run_thread = True
                elif not self.threads_running[func.__name__]['thread'].is_alive():
                    if check_lastrun:
                        if dt.datetime.now() - self.threads_running[func.__name__]['lastrun'] > dt.timedelta(seconds=interval / 2):
                            run_thread = True
                    else:
                        run_thread = True

                if run_thread:
                    # we always need to create a new thread-object because threads cant be re-run
                    self.threads_running[func.__name__]['lastrun'] = dt.datetime.now()
                    self.threads_running[func.__name__]['thread'] = threading.Timer(interval, func, args=args, kwargs=kwargs)
                    self.threads_running[func.__name__]['thread'].start()
            return wrapper
        return decorator

    def cancel_all_threads(self):
        for name, tdict in self.threads_running:
            if 'thread' in tdict:
                if tdict['thread'].is_alive():
                    tdict['thread'].cancel()

    def read_maxigauge(self, key):
        # controller returns something like 'x,x.xxxEsx <CR><LF>'
        # first digit is the error code, then comma, then pressure followed by Carrige return <CR>, Line feed <LF>
        # x,x.xxxEsx <CR><LF> x[Status],[x.xxxEsx] Measurement value (always engeneers' format)
        # 0 Measurement data okay, 1 Underrange, 2 Overrange
        # 3 Sensor error, 4 Sensor off, 5 No sensor, 6 Identification error
        if self.data[key]['used_sensor'] != None:
            self.data[key]['used_sensor'].flushInput()
            self.send_command(self.data[key]['used_sensor'],'PR%i\r\n' % self.data[key]['sensor'])  # request channel
            self.send_command(self.data[key]['used_sensor'],'\x05')  # enquire data
            #~ self.send_command('PR%i\r\n\x05' % (channel))  # request channel
            start_time = time.time()
            string_out = ''
            while string_out == '':
                if time.time()-start_time > 1:
                    return -2000, -2000
                try:
                    string_out = self.read_port(self.data[key]['used_sensor'])
                    if string_out == '':
                        time.sleep(0.01)
                        continue
                    string_split = string_out.split(',')          # splits read string into string[-1],string[0]
                    string_pres = str(string_split[1])            # pressure value converted to string
                    string_sta = int(string_split[0][-1])         # status value converted to int
                    pressure = float(string_pres)                 # float of pressure
                    status = int(string_sta)                      # status as integer value
                except ValueError:
                    pass
                except IndexError:
                    pass
                time.sleep(0.01)
            return self.conv_to_decode[status], pressure
        else:
            return -4000,-4000

    def read_mvcgauge(self, key):
        # communication described in MVC - manual
        if self.data[key]['used_sensor'] != None:
            input_command = 'rpv{}\r'.format(self.data[key]['sensor']).encode('utf-8')             # encode as utf-8
            convinput = self.to_bytes(input_command)                                               # convert to byte sequence
            self.data[key]['used_sensor'].write(convinput)                                         # send to wire
            time.sleep(0.05)
            out = ''                                                                               # string to hold the received message, empty one for new reading
            out += self.data[key]['used_sensor'].readline().decode('utf-8',errors='ignore')
            try:
                current=float(out.split(',')[1])
                if out.split(',')[0] != '0':
                    return -2000, -2000
                return 0,current
            except:
                return -3000,-3000
        else:
            return -4000,-4000

    def read_ionpump(self, key):
        # communication described in Gamma Vacuum - manual
        # important here: use crossed-rs232 cabel
        if self.data[key]['used_sensor']!= None:
            input_command = '~ 05 0A 01 00\r'.encode('utf-8')             # encode as utf-8
            convinput = self.to_bytes(input_command)                   # convert to byte sequence
            self.data[key]['used_sensor'].write(convinput)                                # send to wire
            time.sleep(0.05)
            out = ''                                            # string to hold the received message, empty one for new reading
            out += self.data[key]['used_sensor'].readline().decode('utf-8',errors='ignore')
            try:
                current=float(out.split(' ')[3])
                if out.split(' ')[1] != 'OK':
                    return -2000, -2000
                return 0,current
            except:
                return -3000,-3000
        else:
            return -4000,-4000

    def send_command(self, sensor, command):
        # send command to maxigauges
        # Takes ascii string 'command' and converts it to bytes to send it over serial connection
        input_command = command.encode('utf-8')             # encode as utf-8
        convinput = self.to_bytes(input_command)                   # convert to byte sequence
        sensor.write(convinput)                                # send to wire
        time.sleep(0.05)

    def read_port(self, sensor):
        # read port from maxigauges
        # Reads serial port, gets bytes over wire, decodes them with utf-8 and returns string with received message
        out = ''                                            # string to hold the received message, empty one for new reading
        out += sensor.readline().decode('utf-8')
        out += sensor.readline().decode('utf-8')               # we have to read twice
        return out

    def to_bytes(self, seq):
        # convert a sequence of int/str to a byte sequence and returns it
        if isinstance(seq, bytes):
            return seq
        elif isinstance(seq, bytearray):
            return bytes(seq)
        elif isinstance(seq, memoryview):
            return seq.tobytes()
        else:
            b = bytearray()
            for item in seq:
                # this one handles int and str for our emulation and ints for Python 3.x
                b.append(item)
            return bytes(b)

    def sleep_precise(self, duration, prec=0.0001):
        # better than time.sleep()
        start = time.time()
        while time.time() - start < duration - prec:
            time.sleep(prec)
        # print('sleep deviation: ', time.time()-start-duration)

    def transmit_outlet_code(self, turn_on=True):
        # transmit code to start helium measurement
        # Transmit a chosen code string using the GPIO transmitter
        NUM_ATTEMPTS = 20
        gpio = Adafruit_GPIO.get_platform_gpio()
        gpio.rpi_gpio.setmode(gpio.rpi_gpio.BCM)
        gpio.rpi_gpio.setup(CFG.TRANSMIT_PIN, Adafruit_GPIO.OUT)
        if turn_on:
            code = CFG.A_ON
        else:
            code = CFG.A_OFF
        for t in range(NUM_ATTEMPTS):
            self.lock.acquire()  # timing is critical
            for i in code:
                if i == '1':
                    gpio.output(CFG.TRANSMIT_PIN, 1)
                    self.sleep_precise(CFG.short_delay)
                    gpio.output(CFG.TRANSMIT_PIN, 0)
                    self.sleep_precise(CFG.long_delay)
                elif i == '0':
                    gpio.output(CFG.TRANSMIT_PIN, 1)
                    self.sleep_precise(CFG.long_delay)
                    gpio.output(CFG.TRANSMIT_PIN, 0)
                    self.sleep_precise(CFG.short_delay)
                else:
                    continue
            gpio.output(CFG.TRANSMIT_PIN, 0)
            self.lock.release()
            self.sleep_precise(CFG.extended_delay)
        gpio.cleanup()

    @_start_async(CFG.GRADIENT_RUNEVERY)
    def measure_gradient(self):
        for key in self.data.keys():
            self.gradient_data[self.gradient_data_current][key]['value'] = self.data[key]['value']
        self.gradient_data_timestamp[self.gradient_data_current] = dt.datetime.now()
        self.gradient_data_current += 1
        if self.gradient_data_current >= self.gradient_data_num:
            self.gradient_data_current = 0
        self.update_values_gradient()

    @_start_async(0.001)
    def measure_values_maxigauge(self):
        self.data_unreliable = collections.OrderedDict()
        for key in self.data:
            if self.data[key]['sensor_type'] == 'maxigauges':
                self.data[key]['status'], self.data[key]['value'] = self.read_maxigauge(key)

    @_start_async(0.001)
    def measure_values_ionpumps(self):
        self.data_unreliable = collections.OrderedDict()
        for key in self.data:
            if self.data[key]['sensor_type'] in ['ser_ion_cryo','ser_ion_prep','ser_ion_stm']:
                self.data[key]['status'], self.data[key]['value'] = self.read_ionpump(key)

    @_start_async(0.001)
    def measure_values_mvc_gauge_prep(self):
        if not self.ser_mvc_prep.is_open:
            self.init_serial_mvc_prep()

        self.data_unreliable = collections.OrderedDict()
        for key in self.data:
            if self.data[key]['sensor_type'] == 'mvc_prep':
                self.data[key]['status'], self.data[key]['value'] = self.read_mvcgauge(key)

    @_start_async(0.001)
    def measure_values_mvc_gauge_stm(self):
        if not self.ser_mvc_stm.is_open:
            self.init_serial_mvc_stm()

        self.data_unreliable = collections.OrderedDict()
        for key in self.data:
            if self.data[key]['sensor_type'] == 'mvc_stm':
                self.data[key]['status'], self.data[key]['value'] = self.read_mvcgauge(key)

    @_start_async(0.001)
    def measure_values_analog(self):
        self.data_unreliable = collections.OrderedDict()
        for key in self.data:
            if self.data[key]['sensor_type'] in ['ADC_diods', 'SPI0', 'SPI1', 'ADC_resistor']:
                self.data[key]['value'], self.data[key]['status'], self.data_unreliable[key] = self.read_analog(key)


    def read_analog(self, key):
        # measure values from adc chips and temperature chips
        measurement_points = 15
        extra_feature_multi = np.zeros(measurement_points)
        val_unreliable = False
        for cycle in range(measurement_points):
            # average over several values (measurement_points)
            if self.data[key]['sensor_type'] in ['ADC_diods','ADC_resistor']:
                # ADC chip
                if self.data[key]['used_sensor'] is None:
                    extra_feature_multi[cycle] = -4000
                else:
                    try:
                        extra_feature_multi[cycle] = self.data[key]['used_sensor'].read_volts(channel=self.data[key]['sensor'], gain=2)
                    except:
                        extra_feature_multi[cycle] = -4000
            elif self.data[key]['sensor_type'] in ['SPI0', 'SPI1']:
                # temperatuer chip
                if key == 'TLAB':
                    try:
                        extra_feature_multi[cycle] = self.data[key]['used_sensor'].read_internal_temp_c()
                    except:
                        extra_feature_multi[cycle] = -4000
                else:
                    try:
                        extra_feature_multi[cycle] = self.data[key]['used_sensor'].read_temp_c()
                    except:
                        extra_feature_multi[cycle] = -4000
        if min(extra_feature_multi) <= -1000:
            # remove non-physical values and declare them as unreliable
            val = min(extra_feature_multi)
            status = min(extra_feature_multi)
            val_unreliable = np.mean(extra_feature_multi)
        else:
            # if values make sense, average them and convert with respective calibration
            val = np.mean(extra_feature_multi)
            status = 0
            try:
                if self.data[key]['sensor_type'] not in ['TSAM', 'TLAB', 'TOM1', 'TOM2', 'TOM3']:
                    status = 0
                    if self.data[key]['sensor_type'] == 'ADC_diods':
                        val = self.temp_calib_diode(val)
                    elif self.data[key]['sensor_type'] == 'ADC_resistor':
                        val = self.temp_calib_resistor(val * 1000)
                    if key == 'TMAN':
                        val += CFG.kel_cel
            except ValueError:
                val = -3000
                status = -3000
            if np.std(extra_feature_multi) > 3:
                # if deviations are to large -> unreliable
                val = -2000
                status = -2000
                val_unreliable = np.mean(extra_feature_multi)
        if key in ['TSAM', 'TLAB', 'TOM1', 'TOM2', 'TOM3']:
            # range of temp-chip is between -200C and 1500C
            if val <= -198.0 or val >1500 and val not in CFG.conv_to_decode:
                val = -4000
                status = -4000
        if key in ['TAFM', 'TCRY', 'TMAN', 'TSTM']:
            if val >= 390.0:
                val = -4000
                status = -4000
        return val, status, val_unreliable

    def init_labels(self, gui):
        # initialize labels for GUI
        self.gui = gui
        colors = {key: self.data[key]['color'] for key in self.data}
        sizes = {key: self.data[key]['gui_size'] for key in self.data}
        labels_strs = [' {0: >4} {1: <6} = '.format(key, '[{}]'.format(self.data[key]['unit'])) for key in self.data]
        labels = collections.OrderedDict()
        gui_orders=[self.data[key]['gui_order'] for key in self.data]
        gui_orders_indices = np.argsort(gui_orders)
        for i in gui_orders_indices:
            labels[list(self.data.keys())[i]] = labels_strs[i]
        gui.init_labels(labels, colors, sizes)

    def update_values(self):
        # update label values in GUI
        values = {}
        for key in self.data:
            if int(self.data[key]['value']) in self.decoding_dict.keys():
                values[key] = self.decoding_dict[self.data[key]['value']]
            else:
                values[key] = '{0: {1}}'.format(float(self.data[key]['value']), self.data[key]['format'])
                if key in self.data_unreliable and self.data_unreliable[key] is not False:
                    values[key] += '*'
        for key in values:
            values[key] = '{0: >10}'.format(values[key])
        timestr = dt.datetime.now().strftime(CFG.date_fmt_display) + ' ' + self.fps
        self.gui.update_values(values, timestr)

    def update_values_gradient(self):
        # update gradient values in GUI
        values = {}
        for key in self.data:
            if self.data[key]['gui_size'] < 2:
                continue
            values[key] = '-'
            now = dt.datetime.now()
            if int(self.data[key]['value']) in self.decoding_dict.keys():
                continue
            yvalues = [gdata[key]['value'] if int(gdata[key]['value']) not in self.decoding_dict.keys() else np.nan for gdata in self.gradient_data]
            xvalues = [(gtime-now).seconds for gtime in self.gradient_data_timestamp]
            if np.nan not in yvalues:
                k = np.polyfit(xvalues, yvalues, 1)[0] * CFG.GRADIENT_SHOW
                if np.abs(k/self.data[key]['value']) > 1e-3:
                    values[key] = '{0: {1}}'.format(k, self.data[key]['format_gradient'])
        for key in values:
            values[key] = '{0:^6}'.format(values[key])
        self.gui.update_values_gradient(values)

    @_start_async(0.1, check_lastrun=True)
    def measure_helium(self):
        # measure helium
        helium_log = os.getcwd() + dt.datetime.now().strftime(CFG.HELIUM_LOG)
        helium_check_file = os.getcwd() + CFG.HELIUM_CHECK
        if not self.helium_check:
            if os.path.isfile(helium_check_file):
                # check if 'HELIUM_CHECK_file' exits -> if yes -> measure helium
                self.helium_check = True
                self.helium_save = False
                self.heliums = []
                self.main_loop_time = self.main_loop_time_slow
                time.sleep(0.8)
                self.transmit_outlet_code(turn_on=True)
                self.main_loop_time = self.main_loop_time_normal
                self.helium_turn_sensor_off = False  # we could also check whether it is on
                self.helium_turn_sensor_off_retries = 0
                self.t_hchk1 = time.time()
                print('Helium check.')
            if not os.path.isfile(helium_log):
                # write header to helium log file
                with open(helium_log, "w") as logfile_helium:
                    logfile_helium.write("Time\tLHE[mm]\n")
        if self.helium_check:
            self.t_hchk2 = time.time()
            # get values from ADC chip and average for a certain time
            if self.t_hchk2 - self.t_hchk1 > 10 and len(self.heliums) > 15 and np.mean(self.heliums) > 0:
                self.heliums = np.array(self.heliums, float)
                time.sleep(5)   # time to let helium level hardware start up
                helium = np.mean(self.heliums[abs(self.heliums - np.mean(self.heliums)) < 1 * np.std(self.heliums)])
                self.helium_save = True
                print('Helium check: successful.')
            elif self.t_hchk2 - self.t_hchk1 > 30:  # timeout
                helium = -3000
                self.helium_save = True
                print('Helium check: timeout.')
            elif self.t_hchk2 - self.t_hchk1 > 5:
                for i in range(5):
                    # print(self.adc[0].volts * 1000.0 / 2.0)
                    try:
                        helium = self.adc[0].volts * 1000.0 / 2.0
                    except Exception:
                        pass
                    finally:
                        if helium > 0:
                            self.heliums.append(helium)
        if self.helium_save:
            # save helium level to log
            now = dt.datetime.now()
            value = int(helium)
            self.helium_status['date_last_measured'] = now
            self.helium_status['value'] = value
            with open(helium_log, "a") as logfile_helium:
                logfile_helium.write("%s\t%i\n" % (now.strftime(CFG.date_fmt), value))
            if os.path.isfile(helium_check_file):
                os.remove(helium_check_file)
            self.helium_save = False
            self.helium_check = False
            self.helium_turn_sensor_off = True
            self.main_loop_time = self.main_loop_time_slow
            time.sleep(0.8)
            self.transmit_outlet_code(turn_on=False)
            self.main_loop_time = self.main_loop_time_normal
            print('Helium check: saved: {} mm.'.format(value))
            self.display_helium_now()
        if self.helium_turn_sensor_off:
            time.sleep(2 ** self.helium_turn_sensor_off_retries)
            if self.adc[0].volts < 0.02:  # baseline should be below this
                self.helium_turn_sensor_off = False
                print('Helium check: finished and sensor off.')
            else:
                self.main_loop_time = self.main_loop_time_slow
                time.sleep(2)
                self.transmit_outlet_code(turn_on=False)
                self.helium_turn_sensor_off_retries += 1
                print('Helium check: turning sensor off again, retry {}.'.format(self.helium_turn_sensor_off_retries))
                self.main_loop_time = self.main_loop_time_normal

    @_start_async(0.001)  # but it is not in the main loop
    def read_helium_from_log(self):
        data = self.measure_getlast()
        if data is not None and data.shape[0] > 0:
            date_last_measured = data.tail(1).index.to_pydatetime()[0]
            column_name = 'LHE[mm]'
            value = float(data.tail(1)[column_name])
        self.helium_status['date_last_measured'] = date_last_measured
        self.helium_status['value'] = value
        self.display_helium_now()

    @_start_async(1800)
    def display_helium(self):
        self.display_helium_now()

    def display_helium_now(self):
        value = self.helium_status['value']
        date_last_measured = self.helium_status['date_last_measured']
        if int(value) in self.decoding_dict:
            value = self.decoding_dict[value]
        if isinstance(value, str):
            str_value = '{}'.format(value)
        else:
            str_value = '{:.0f}'.format(value)
        str_out = "LHe: {} mm ({})".format(str_value, self.date_format_bot(date_last_measured))
        gui.update_helium(str_out) # forward helium lavel value to gui

    def date_format_bot(self, this_date):
        # returns a formatted date according to the config
        if dt.datetime.now() - this_date < dt.timedelta(hours=12):
            return this_date.strftime(CFG.date_fmt_display_he_short)
        else:
            return this_date.strftime(CFG.date_fmt_display_he)

    def str2date(self, x):
        # convert string from log to datetime object
        return dt.datetime(int(x[0:4]), int(x[5:7]), int(x[8:10]), int(x[11:13]), int(x[14:16]), int(x[17:19]))

    def measure_getlast(self):
        # reads last log entries for a specific measure entity
        helium_log = os.getcwd() + dt.datetime.now().strftime(CFG.HELIUM_LOG)
        df = pd.DataFrame()
        try:
            df = pd.read_csv(helium_log,
                             sep='\t',
                             comment='#',
                             parse_dates=True,
                             date_parser=self.str2date,
                             index_col=0,
                             dtype=np.float,
                             error_bad_lines=False)
        except pd.errors.EmptyDataError:
            return None
        return df[-1:]

    def check_day(self):
        self.pressurelogfile_name = dt.datetime.now().strftime(os.getcwd() + CFG.PRESSURE_LOGS)
        return(os.path.isfile(self.pressurelogfile_name))

    def save_header_to_log(self):
        if not self.check_day():  # write header if logfile doesnt exist
            self.log_writing_header = True
            header = 'Time\t'
            for key in self.data:
                if self.data[key]['log_to_file']:
                    header += '{0}[{1}]\t'.format(key, self.data[key]['unit'])
            header = header[:-1] + '\n'

            os.makedirs(os.path.dirname(self.pressurelogfile_name), exist_ok=True)
            with open(self.pressurelogfile_name, "a") as logfile:
                logfile.write(header)
            self.log_writing_header = False

    @_start_async(2, check_lastrun=True)
    def save_to_log(self):
        self.save_header_to_log()
        formattedData = [''] * len(self.data)
        for n, key in enumerate(self.data):
            if not self.data[key]['log_to_file']:
                continue
            if isinstance(self.data[key]['value'], str):
                formattedData[n] = '%s' % self.data[key]['value']
            else:
                formattedData[n] = '{0: {1}}'.format(float(self.data[key]['value']), self.data[key]['format'])
        with open(self.pressurelogfile_name, "a") as logfile:
            logfile.write("%s\t" % dt.datetime.now().strftime(CFG.date_fmt) + "\t".join(formattedData) + "\n")
        self.thread_save_to_log_running = False

    @_start_async(1, check_lastrun=True)
    def sanity_checks(self):
        # checks for values exceeding limits and initialize warning
        for key, ddict in self.data.items():
            if 'limit_max' in ddict:
                if ddict['value'] > ddict['limit_max']:
                    self.gui.warning(key, 'Warning: {}'.format(ddict['limit_max_warning']), key)
                else:
                    self.gui.dewarning(key)

    def thread_main_loop_sensors_start(self):
        self.thread_main_loop_sensors = threading.Timer(self.main_loop_time, self.main_loop_sensors)
        self.thread_main_loop_sensors.start()

    def main_loop_sensors(self):
        # measurement

        if ('ADC_diods' in self.sensor_types) or ('ADC_resistor' in self.sensor_types) or ('temp_chip' in self.sensor_types):
            self.measure_values_analog()
        if 'maxigauges' in self.sensor_types:
            self.measure_values_maxigauge()
        if 'mvc_prep' in self.sensor_types:
            self.measure_values_mvc_gauge_prep()
        if 'mvc_stm' in self.sensor_types:
            self.measure_values_mvc_gauge_stm()
        if ('ser_ion_prep' in self.sensor_types) or ('ser_ion_cryo' in self.sensor_types) or ('ser_ion_stm' in self.sensor_types):
            self.measure_values_ionpumps()
        if CFG.HELIUM != None:
            self.measure_helium()

        if CFG.GRADIENT_RUNEVERY > 0:
            self.measure_gradient()

        # display
        self.update_values()
        if CFG.HELIUM != None:
            self.display_helium()

        # log
        self.save_to_log()

        # sanity checks and warnings
        self.sanity_checks()

        if CFG.FPS_SHOW:
            self.fps = ' fps:{:4.1f}'.format(1 / (time.time() - self.time_loop))
        self.time_loop = time.time()

        if APP_RUNNING:
            self.thread_main_loop_sensors_start()
        else:
            self.cancel_all_threads()

    def main_loop_init(self):
        # if loop runs for the first time
        print('Reading initial sensor data.')
        if ('ADC_diods' in self.sensor_types) or ('ADC_resistor' in self.sensor_types) or ('temp_chip' in self.sensor_types):
            self.measure_values_analog()
        if 'maxigauges' in self.sensor_types:
            self.measure_values_maxigauge()
        if 'mvc_prep' in self.sensor_types:
            self.measure_values_mvc_gauge_prep()
        if 'mvc_stm' in self.sensor_types:
            self.measure_values_mvc_gauge_stm()
        if ('ser_ion_prep' in self.sensor_types) or ('ser_ion_cryo' in self.sensor_types) or ('ser_ion_stm' in self.sensor_types):
            self.measure_values_ionpumps()
        if CFG.HELIUM != None:
            self.read_helium_from_log()

        # wait for the first measurements
        if ('ADC_diods' in self.sensor_types) or ('ADC_resistor' in self.sensor_types) or ('temp_chip' in self.sensor_types):
            self.threads_running['measure_values_analog']['thread'].join()
        if 'maxigauges' in self.sensor_types:
            self.threads_running['measure_values_maxigauge']['thread'].join()
        if 'mvc_prep' in self.sensor_types:
            self.threads_running['measure_values_mvc_gauge_prep']['thread'].join()
        if 'mvc_stm' in self.sensor_types:
            self.threads_running['measure_values_mvc_gauge_stm']['thread'].join()
        if ('ser_ion_prep' in self.sensor_types) or ('ser_ion_cryo' in self.sensor_types) or ('ser_ion_stm' in self.sensor_types):
            self.threads_running['measure_values_ionpumps']['thread'].join()

        # self.threads_running['read_helium_from_log']['thread'].join()

        print('Starting main loop.')
        global APP_RUNNING
        APP_RUNNING = True
        self.thread_main_loop_sensors_start()


if __name__ == '__main__':
    print('Initializing measurement system.')
    msr = measure()
    print('Initializing GUI.')
    gui = GUI.initGUI()
    msr.init_labels(gui)
    gui.root.after(10, msr.main_loop_init)
    gui.startApp()
