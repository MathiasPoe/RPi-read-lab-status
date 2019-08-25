# tkinter based GUI for raspberry pi status
#
# info on tkinter as thread:
# https://stackoverflow.com/questions/459083/how-do-you-run-your-own-code-alongside-tkinters-event-loop
#

import colorsys
import datetime as dt
import numpy as np
import os
import time
import tkinter as tk
import threading
from google_speech import Speech

import config as CFG

def color_brightness(color, amount=0.5):
    crgb = tuple(int(color[i+1:i+3], 16) for i in (0, 2 ,4))
    c = colorsys.rgb_to_hls(*crgb)
    crgb = colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])
    crgb = [int(c) for c in crgb]
    return "#{0:02x}{1:02x}{2:02x}".format(*crgb)      


class MainWindow(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.start()

        self.root = tk.Tk()
        self.root.title("{} Status".format(CFG.MACHINE))
        self.root.tk.call('wm', 'iconphoto', self.root._w, tk.PhotoImage(file='icons8-dove-96.png'))
        self.root.geometry('800x600')
        self.root.configure(background=CFG.COLOR_BACKGROUND_WINDOW)
        # self.root.configure(padx=20)
        # self.root.configure(pady=20)
        # self.root.state('zoomed')
        # self.root.wm_state('zoomed')
        self.root.lift()

        self.font = (CFG.FONT_FAMILY, 50, 'bold')
        self.font_time = (CFG.FONT_FAMILY, 30)
        self.font_helium = (CFG.FONT_FAMILY, 24)
        self.font_gui = (CFG.FONT_FAMILY, CFG.font_size_gui)

        self.topmost = False
        self.geometry = '800x600'

        self.root.bind("<Configure>", self.resize)
        self.root.bind("<F12>", self.toggle_fullscreen)
        self.root.bind("<F11>", self.toggle_zoomed)
        self.root.bind("<F10>", self.toggle_topmost)
        self.root.protocol("WM_DELETE_WINDOW", self.endApp)

        self.labels_names = {}
        self.labels_values = {}
        self.label_time = None
        self.font_scaling_factor = 10
        
        self.warnings = {}
        self.warning_notification_output = False
        
        self.measure_helium_symbol = u"\u21bb"
        self.measure_animation_current = 0
        self.measure_animation = []
        self.measure_animation_speed = 100
        self.measure_helium_animation_timer_id = 0
        
        # w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        # root.geometry("%dx%d+0+0" % (w, h))

    def startApp(self):
        # start in fullscreen mode
        if not self.is_fullscreen():
            self.toggle_fullscreen(None)
        
        self.root.mainloop()

    def endApp(self):
        global APP_RUNNING
        APP_RUNNING = False
        self.root.quit()
        
    def init_labels(self, labels, colors, sizes):
        """initialiyes layout with labels"""

        self.menu_top = tk.Frame(self.root, height=12, borderwidth=0, highlightthickness=0, bg=CFG.COLOR_BACKGROUND_WINDOW)
        self.main_area = tk.Frame(self.root, borderwidth=0, highlightthickness=0, bg=CFG.COLOR_BACKGROUND_WINDOW)
        self.menu_top.pack(fill=tk.X)
        self.main_area.pack(expand=True, fill=tk.BOTH)

        self.label_gui_ontop = tk.Label(
            self.menu_top, text=u"\u25C9", font=self.font_gui, fg=CFG.COLOR_status_gui_inactive, bg=CFG.COLOR_BACKGROUND,
            borderwidth=0, highlightthickness=0
        )
        self.label_gui_ontop.pack(side=tk.RIGHT)
        self.label_gui_ontop.bind("<Button-1>", self.toggle_topmost)
        
        self.label_gui_spacers = {}
        self.label_gui_warnings = {}
        for l in labels:
            self.label_gui_spacers[l] = tk.Label(
                self.menu_top, text=u" ", font=self.font_gui, fg=CFG.COLOR_status_gui_inactive, bg=CFG.COLOR_BACKGROUND,
                borderwidth=0, highlightthickness=0
            )
            self.label_gui_warnings[l] = tk.Label(
                self.menu_top, text="", font=self.font_gui, fg=CFG.COLOR_status_gui_inactive, bg=CFG.COLOR_BACKGROUND,
                borderwidth=0, highlightthickness=0
            )
            self.label_gui_warnings[l].bind("<Button-1>", self.warning_remove)

        row_num = 0
        row_height_relative = []
        self.label_time = tk.Label(self.main_area, text="", font=self.font_time, fg=CFG.COLOR_TIME, bg=CFG.COLOR_BACKGROUND) 
        self.label_time.grid(column=0, row=row_num, columnspan=4, padx=0, pady=0, sticky=tk.N + tk.E + tk.W)
        tk.Grid.rowconfigure(self.main_area, row_num, weight=CFG.height_ratio_time)
        row_height_relative.append(CFG.height_ratio_time)

        self.labels_names = {}
        self.labels_values_container = {}
        self.labels_values = {}
        self.labels_values_gradient = {}
        self.labels_values_gradient_unit = {}
        self.labels_small = {}
        total_size = 0
        # TODO: so far only sizes 1 and 2 are supported
        for l, val in labels.items():
            extra_column = total_size % 2
            if sizes[l] >=2:
                if extra_column:
                    total_size += total_size % 2
                    extra_column = 0
            else:
                self.labels_small[l] = True
            if extra_column == 0:
                row_num += 1
            self.labels_values_container[l] = tk.Frame(self.main_area, borderwidth=0, highlightthickness=0, bg=CFG.COLOR_BACKGROUND_WINDOW)
            self.labels_names[l] = tk.Label(self.main_area, text=val, font=self.font, fg=colors[l], bg=CFG.COLOR_BACKGROUND)
            self.labels_values[l] = tk.Label(self.labels_values_container[l], text="", font=self.font, fg=colors[l], bg=CFG.COLOR_BACKGROUND)
            if sizes[l] >= 2:  # no gradients for the small labels
                self.labels_values_gradient[l] = tk.Label(self.labels_values_container[l], text="      ", font=self.font, fg=color_brightness(colors[l], CFG.COLOR_gradient_brightness_factor), bg=CFG.COLOR_BACKGROUND)
                self.labels_values_gradient_unit[l] = tk.Label(self.labels_values_container[l], text="/{}s".format(CFG.GRADIENT_SHOW), font=self.font, fg=color_brightness(colors[l], CFG.COLOR_gradient_unit_brightness_factor), bg=CFG.COLOR_BACKGROUND)
            self.labels_values[l].grid(column=0, row=0, rowspan=2, padx=0, pady=0, sticky=tk.N + tk.S + tk.E)
            if sizes[l] >= 2:
                self.labels_values_gradient[l].grid(column=1, row=0, padx=0, pady=0, sticky=tk.N + tk.S + tk.W)
                self.labels_values_gradient_unit[l].grid(column=1, row=1, padx=0, pady=0, sticky=tk.N + tk.E + tk.W)
                self.labels_values_container[l].columnconfigure(1, weight=1)
            self.labels_values_container[l].rowconfigure(0, weight = 1)
            self.labels_values_container[l].rowconfigure(1, weight = 1)
            self.labels_values_container[l].columnconfigure(0, weight=1)
            if sizes[l] >= 2:
                c_label = 0
                c_value = 2
            else:
                c_label = extra_column * 2
                c_value = extra_column * 2 + 1
            self.labels_names[l].grid(column=c_label, row=row_num, columnspan=sizes[l], padx=0, pady=0, sticky=tk.N + tk.S + tk.E)
            self.labels_values_container[l].grid(column=c_value, row=row_num, columnspan=sizes[l], padx=2, pady=0, sticky=tk.N + tk.S + tk.W)
            total_size += sizes[l]
            self.main_area.rowconfigure(row_num, weight=CFG.height_ratio_normal)
            row_height_relative.append(CFG.height_ratio_normal)

        row_num += 1
        
        if CFG.HELIUM != None:
            self.frame_helium = tk.Frame(self.main_area, borderwidth=0, highlightthickness=0, bg=CFG.COLOR_BACKGROUND_WINDOW)
            self.frame_helium.grid(column=0, row=row_num, columnspan=4, padx=0, pady=0, sticky=tk.N + tk.S + tk.E + tk.W)
            self.button_measure_helium = tk.Button(
                self.frame_helium, text=self.measure_helium_symbol, command=self.measure_helium,
                font=self.font_helium, fg=CFG.COLOR_button_helium_fg, bg=CFG.COLOR_button_helium_bg,
                borderwidth=0, highlightthickness=0
            )
            self.button_measure_helium.pack(side=tk.LEFT)
            
            self.label_helium = tk.Label(self.frame_helium, text="", font=self.font_helium, fg=CFG.COLOR_HELIUM, bg=CFG.COLOR_BACKGROUND)
            self.label_helium.pack()
        
            tk.Grid.rowconfigure(self.main_area, row_num, weight=CFG.height_ratio_helium)
            row_height_relative.append(CFG.height_ratio_helium)

        row_height_relative = np.array(row_height_relative)
        self.font_scaling_factor = np.sum(row_height_relative / np.max(row_height_relative))

        for i in range(4):
            tk.Grid.columnconfigure(self.main_area, i, weight=1)

    def update_values(self, values, str_time):
        '''updates values'''
        for k, v in values.items():
            self.labels_values[k]['text'] = v
        self.label_time['text'] = str_time

    def update_values_gradient(self, values):
        '''updates values'''
        for k, v in values.items():
            if k in self.labels_values_gradient:
                self.labels_values_gradient[k]['text'] = v

    def update_helium(self, str_helium):
        self.label_helium['text'] = str_helium
        
        if self.measure_helium_animation_timer_id:
            self.root.after_cancel(self.measure_helium_animation_timer_id)
        self.measure_animation_current = 0
        self.button_measure_helium['text'] = self.measure_helium_symbol
        self.button_measure_helium.config(state="normal")

    def measure_helium(self):
        with open(os.getcwd() + CFG.HELIUM_CHECK, 'a'):
            os.utime(os.getcwd() + CFG.HELIUM_CHECK)
            
        self.button_measure_helium.config(state="disabled")
        num = np.random.randint(len(CFG.measure_animations))
        self.measure_animation = CFG.measure_animations[num]
        self.measure_animation_speed = CFG.measure_animations_speed[num]
        self.measure_helium_animation()
        
    def measure_helium_animation(self):
        self.button_measure_helium['text'] = self.measure_animation[self.measure_animation_current].encode('utf-8').decode()
        self.measure_animation_current += 1
        if self.measure_animation_current >= len(self.measure_animation):
            self.measure_animation_current = 0
        self.measure_helium_animation_timer_id = self.root.after(self.measure_animation_speed, self.measure_helium_animation)
              
    def is_fullscreen(self):
        return self.root.attributes('-fullscreen')

    def toggle_fullscreen(self, event):
        if self.is_fullscreen():
            self.root.wm_attributes('-fullscreen', False)
            self._set_topmost(self.topmost)
        else:
            self.root.wm_attributes('-fullscreen', True)
            self._set_topmost(False)

    def is_zoomed(self):
        if self.root.state() == 'zoomed':
            return True
        if self.root.wm_state() == 'zoomed':
            return True
        zoomed = False
        try:
            geometry_size = [int(x) for x in self.geometry.split('+')[0].split('x')]
            actual_geometry_size = [int(x) for x in self.root.geometry().split('+')[0].split('x')]
            if actual_geometry_size[0] > geometry_size[0] and actual_geometry_size[1] > geometry_size[1]:
                zoomed = True
        except ValueError:
            pass
        return zoomed

    def toggle_zoomed(self, event):
        if not self.is_zoomed():
            self.geometry = self.root.geometry()
            try:
                self.root.wm_state('zoomed')
            except Exception:
                pass
            try:
                self.root.wm_attributes('-zoomed', True)
            except Exception:
                pass
            self._set_topmost(False)
        else:
            self.root.wm_state('normal')
            try:
                self.root.wm_attributes('-zoomed', False)
            except Exception:
                pass
            self._set_topmost(self.topmost)
            self.root.geometry(self.geometry)

    def toggle_topmost(self, event):
        if self.root.wm_attributes("-topmost"):
            self._set_topmost(False)
            self.topmost = False
        else:
            if not self.is_zoomed() and not self.is_fullscreen():
                self._set_topmost(True)
            self.topmost = True

    def _set_topmost(self, active=True):
        self.root.wm_attributes("-topmost", active)
        if active:
            self.label_gui_ontop.config(fg=CFG.COLOR_status_gui_active)
        else:
            self.label_gui_ontop.config(fg=CFG.COLOR_status_gui_inactive)

    def resize(self, event):
        if (event.widget == self.root):
            size = min(event.height / 3, event.width / 4)
            s = int(size / self.font_scaling_factor * CFG.FONT_SCALING)
            ssmall = int(s * CFG.font_ratio_small)
            stime = int(s * CFG.font_ratio_time)
            sgradient = int(s * CFG.font_ratio_gradient)
            sgradientsmall = int(ssmall * CFG.font_ratio_gradient)
            sgradientunit = int(s * CFG.font_ratio_gradient_unit)
            sgradientunitsmall = int(ssmall * CFG.font_ratio_gradient_unit)
            if CFG.HELIUM != None:
                shelium = int(s * CFG.font_ratio_helium)
            self.font = (CFG.FONT_FAMILY, s, 'bold')
            self.font_small = (CFG.FONT_FAMILY, ssmall, 'bold')
            self.font_time = (CFG.FONT_FAMILY, stime)
            self.font_gradient = (CFG.FONT_FAMILY, sgradient)
            self.font_gradientsmall = (CFG.FONT_FAMILY, sgradientsmall)
            self.font_gradientunit = (CFG.FONT_FAMILY, sgradientunit)
            self.font_gradientunitsmall = (CFG.FONT_FAMILY, sgradientunitsmall)
            if CFG.HELIUM != None:
                self.font_helium = (CFG.FONT_FAMILY, shelium)
            for k in self.labels_values:
                if k in self.labels_small:
                    self.labels_values[k].config(font=self.font_small)
                    # self.labels_values_gradient[k].config(font=self.font_gradientsmall)
                    # self.labels_values_gradient_unit[k].config(font=self.font_gradientunitsmall)
                    self.labels_names[k].config(font=self.font_small)
                else:
                    self.labels_values[k].config(font=self.font)
                    self.labels_values_gradient[k].config(font=self.font_gradient)
                    self.labels_values_gradient_unit[k].config(font=self.font_gradientunit)
                    self.labels_names[k].config(font=self.font)
            if self.label_time is not None:
                self.label_time.config(font=self.font_time)
            if CFG.HELIUM != None:
                if self.label_helium is not None:
                    self.label_helium.config(font=self.font_helium)
            # print("New size is: {}x{}".format(event.width, event.height))
            
    def warning_notification(self, text):
        print(dt.datetime.now().strftime('%b %d, %H:%M:%S'), text)
        while self.warning_notification_output:
            time.sleep(0.5)
        self.warning_notification_output = True
        speech = Speech(text, 'en')
        speech.play()
        time.sleep(3)
        self.warning_notification_output = False
        
    def warning(self, key, text, text_short):
        if key not in self.warnings:
            self.warnings[key] = {}
            self.warnings[key]['last_sound'] = dt.datetime.now()-dt.timedelta(hours=24*365*10)
            self.warnings[key]['num_warnings'] = 0
            self.warning_notification(text)
        if (dt.datetime.now() - self.warnings[key]['last_sound']).seconds > 3 + 2 ** self.warnings[key]['num_warnings']:
            self.warning_notification(text)
            self.warnings[key]['num_warnings'] += 1
            self.warnings[key]['last_sound'] = dt.datetime.now()
        self.label_gui_warnings[key]['text']=text_short
        self.label_gui_warnings[key].pack(side=tk.LEFT)
        self.label_gui_spacers[key].pack(side=tk.LEFT)
        self.label_gui_warnings[key].config(fg=CFG.COLOR_status_gui_warning)
        
    def dewarning(self, key):
        if key in self.warnings:
            self.label_gui_warnings[key].config(fg=CFG.COLOR_status_gui_inactive)
            self.warnings[key]['num_warnings'] = 0
        
    def warning_remove(self, event):
        for key, label in self.label_gui_warnings.items():
            if event.widget == label:
                label.pack_forget()
                self.label_gui_spacers[key].pack_forget()
                self.warnings[key]['num_warnings'] = 0
                return
        
def initGUI():
    gui = MainWindow()
    return gui


if __name__ == "__main__":
    # test code
    import datetime as dt
    gui = initGUI()
    labels = {
        "sfdfd": "sfdfdf", "sfdfd2": "sfdfdf2", "sfdfd3": "sfdfdf3", "sfdfd4":
        "sfdfdf4", "sfdfd5": "sfdfdf5", "sfdfd6": "sfdfdf6", "sfdfd7": "sfdfdf7", "sfdfd8": "sfdfdf8",
        "sfdfd9": "sfdfdf9", "sfdfd10": "sfdfdf10",
    }
    labels_gradients = {
        "sfdfd": "20", "sfdfd2": "30", "sfdfd3": "50", "sfdfd4":
        "60", "sfdfd5": "70", "sfdfd6": "80", "sfdfd7": "90", "sfdfd8": "100",
        "sfdfd9": "110", "sfdfd10": "100",
    }
    colors = {key: '#c0c0c0' for key in labels}
    sizes = {key: 2 for key in labels}
    sizes['sfdfd'] = 1
    sizes['sfdfd2'] = 1
    sizes['sfdfd9'] = 1
    sizes['sfdfd10'] = 1
    gui.init_labels(labels, colors, sizes)
    gui.update_values(labels, dt.datetime.now().strftime("%b %d, %H:%M:%S"))
    gui.update_values_gradients(labels_gradients)
    if CFG.HELIUM != None:
        gui.update_helium('LHe 007 mm (Aug 1st, 19:17)')
        
    gui.root.mainloop()
