import pilotschool

import fsuipc

import tkinter.ttk
import tkinter.messagebox
import tkinter.font
import tkinter.simpledialog

import datetime
import pathlib
import threading
import sys
import contextlib
import time
import argparse
import math

import logging
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="PID %(process)d - %(asctime)s - %(levelname)s - %(name)s - %(message)s")


WINDOW_SIZE = (300, 350)

class FlightInfoWindow(tkinter.Tk):
    def __init__(self, on_load_fn=lambda: None, on_close_fn=lambda: None, title="<no title set>"):
        """
        on_close:
            callable
        """
        self.logger = logging.getLogger('FlightInfoWindow')

        self.is_running = False

        super().__init__()
        tkinter.ttk.Style().theme_use('clam')
        width, height = WINDOW_SIZE
        self.geometry(f"{width}x{height}")
        self.geometry(f"+0+0")
        self.attributes('-topmost', True)
        self.configure(bg='white')
        self.columnconfigure(0, weight=1)

        # Create widgets
        self.title_widget = tkinter.ttk.Label(self, text=title, background='white')
        separator = tkinter.ttk.Separator(self, orient='horizontal')
        self.main_info_widget = FlightInfoFrame(self)

        # Set widgets' positions
        self.title_widget.grid(row=0)
        separator.grid(row=1, sticky='ew')
        self.main_info_widget.grid(row=2, sticky='ew')

        # self.title_widget.grid_columnconfigure(0, weight=1)
        # separator.grid_columnconfigure(0, weight=1)
        # self.main_info_widget.grid_columnconfigure(0, weight=1)

        def _on_close():
            if tkinter.messagebox.askokcancel("Quit", "Really quit?"):
                on_close_fn()
                self.destroy()
        self.protocol("WM_DELETE_WINDOW", _on_close)

        self.withdraw()
        self.captain_name = tkinter.simpledialog.askstring(
            "Hi Cadet!", "Captain's name:", parent=self) or ""
        self.title(f"{self.captain_name} - Flight Examiner")
        self.deiconify()

        on_load_fn()

    def run(self):
        if self.is_running:
            self.logger.error("Cannot run() FlightInfoWindow twice")

        self.is_running = True
        self.mainloop()

class FlightInfoFrame(tkinter.Text):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, relief=tkinter.FLAT)

        hint_config = {'font': tkinter.font.Font(family='Calibri', size=14, weight='bold')}
        finish_condition_config = {'font': tkinter.font.Font(family='Calibri', size=14)}
        simple_text_config = {'font': tkinter.font.Font(family='Calibri', size=14)}
        met_constraint_config = {'font': tkinter.font.Font(family='Arial', size=16), 'foreground': 'white', 'background': '#38761d'}
        unmet_constraint_config = {'font': tkinter.font.Font(family='Arial', size=16), 'foreground': 'white', 'background': '#990000'}
        penalty_config = {'font': tkinter.font.Font(family='Calibri', size=14)}

        self.tag_configure('HINT', **hint_config)
        self.tag_configure('FINISH_CONDITION', **finish_condition_config)
        self.tag_configure('SIMPLE_TEXT', **simple_text_config)
        self.tag_configure('MET_CONSTRAINT', **met_constraint_config)
        self.tag_configure('UNMET_CONSTRAINT', **unmet_constraint_config)
        self.tag_configure('PENALTY', **penalty_config)

        self.insert('end', "This line tells you what you're expected to do now.\n\n", 'HINT')
        self.insert('end', "This explains when will the next stage start.\n\n", 'FINISH_CONDITION')
        self.insert('end', "Active constraints:\n", 'SIMPLE_TEXT')
        self.insert('end', "This is a satisfied constraint.\n", ('MET_CONSTRAINT', 'CONSTRAINTS'))
        self.insert('end', "Unmet constraints are in red.\n", ('UNMET_CONSTRAINT', 'CONSTRAINTS'))
        self.insert('end', "\nTotal penalty for this segment: <...>", 'PENALTY')

    def _update_text_by_tag(self, text: str, tag: str):
        tag_start_position = self.index(f'{tag}.first')
        self.delete(tag_start_position, f'{tag}.last')
        self.insert(tag_start_position, text, tag)

    def update_hint(self, text: str):
        self._update_text_by_tag(text + "\n\n", 'HINT')

    def update_finish_condition(self, param_name: str, param_value: float):
        if param_name == 'Time':
            text = f"Waiting for {self.parameter_to_readable(param_name, param_value)}..."
        else:
            text = f"Waiting for {self.parameter_to_description(param_name)} to reach " \
                   f"{self.parameter_to_readable(param_name, param_value)}..."
        self._update_text_by_tag(text + "\n\n", 'FINISH_CONDITION')

    def update_penalty(self, penalty):
        text = f"\nTotal penalty for this segment: {round(penalty, 2)}"
        self._update_text_by_tag(text, 'PENALTY')

    def display_summary(self, total_penalty, report_csv_path):
        self.update_hint("Done, congrats!")
        self._update_text_by_tag(
            f"Your overall penalty is {round(total_penalty, 2)}\n\n", 'FINISH_CONDITION')
        self._update_text_by_tag(f"", 'SIMPLE_TEXT')
        self._update_text_by_tag(f"A detailed report written to:\n\n{report_csv_path}", 'PENALTY')

    def update_constraints(self, constraints):
        """
        constraints
            list of (str, number, bool)
            Each tuple means (parameter name, parameter value, is constraint currently met)
        """
        constraints = sorted(constraints, key=lambda x: -__class__.PARAMETER_PRIORITY[x[0]])

        common_tag = 'CONSTRAINTS'
        tag_start_position = self.index(f'{common_tag}.first')
        self.delete(tag_start_position, f'{common_tag}.last')

        if constraints == []:
            self.insert(tag_start_position, "\n\n", ('MET_CONSTRAINT', common_tag))
            return

        current_position = tag_start_position
        for param_name, param_value, is_constraint_met in constraints:
            if param_name == 'ResponseTime':
                text = f"You have {self.parameter_to_readable(param_name, param_value)}"
            else:
                text = f"{self.parameter_to_description(param_name).capitalize()} = " \
                       f"{self.parameter_to_readable(param_name, param_value)}"

            met_unmet_tag = is_constraint_met and 'MET_CONSTRAINT' or 'UNMET_CONSTRAINT'

            self.insert(current_position, text + "\n", (met_unmet_tag, common_tag))

    def blink(self, color='#bb00bb', time_ms=500):
        self.configure(bg=color)

        def revert_color():
            self.configure(bg='white')

        self.after(time_ms, revert_color)

    @staticmethod
    def parameter_to_readable(param_name, param_value):
        param_value = float(param_value)

        if 'Time' in param_name:
            return f"{round(param_value)} second(s)"
        elif param_name == 'altitude':
            return f"{round(param_value)} ft"
        elif param_name == 'vertical speed':
            return f"{round(param_value)} ft/min"
        elif param_name == 'heading':
            if param_value < 1.0:
                param_value = 360.0
            return f"{round(param_value)}°"
        elif param_name == 'speed':
            return f"{round(param_value)} kts"
        elif param_name == 'pitch':
            return f"{round(param_value)}°"
        elif param_name == 'bank':
            return f"{round(param_value)}°"
        elif param_name == 'flaps':
            return f"{round(param_value)}"
        elif param_name == 'rpm':
            return f"{round(param_value)} RPM"
        elif param_name == 'throttle':
            return f"{round(param_value * 100)}%"
        elif param_name == 'distance':
            return f"{round(param_value, 1)} km"
        elif param_name == 'g-force':
            return f"{round(param_value, 1)}"
        elif param_name == 'pause':
            return f"'{param_value}'"
        else:
            raise ValueError(f"{param_name}")

    @staticmethod
    def parameter_to_description(param_name):
        if 'Time' in param_name:
            return "time"
        elif param_name == 'rpm':
            return "engine"
        else:
            return param_name

    PARAMETER_PRIORITY = {name: i for i, name in enumerate(
        ['Time', 'ResponseTime', 'speed', 'throttle', 'rpm', 'altitude', 'flaps',
        'heading', 'bank', 'pitch', 'vertical speed', 'distance', 'g-force'])}


class FlightSimParametersReader:
    def __init__(self):
        self.fsuipc = fsuipc.FSUIPC()

        # def size_per_dtype(dtype):
        #     if dtype in ('b', 'c'):
        #         return 1
        #     elif dtype in ('h', 'H'):
        #         return 2
        #     elif dtype in ('d', 'u', 'F'):
        #         return 4
        #     elif dtype in ('l', 'L', 'f'):
        #         return 8
        #     else:
        #         raise ValueError(f"Wrong py-fsuipc dtype: {dtype}")

        # FSUIPC offset, FSUIPC dtype, name, conversion
        def convert_bank(bank):
            actual_bank = [0, 5  , 10  , 15  , 20  , 25  , 30, 45  , 60, 90]
            msfs_bank =   [0, 9.5, 15.9, 21.5, 27.6, 34.9, 42, 52.5, 66, 90]

            i = None
            for i in range(1, len(msfs_bank)):
                if abs(bank) < msfs_bank[i]:
                    break
            else:
                return -bank

            retval = actual_bank[i - 1] + (actual_bank[i] - actual_bank[i - 1]) * \
                ((abs(bank) - msfs_bank[i - 1]) / (msfs_bank[i] - msfs_bank[i - 1]))
            if bank > 0:
                retval = -retval

            return retval

        self.PARAMETERS_OF_INTEREST = [
            (0x3324, 'd', "altitude",       lambda x: x),
            (0x2B00, 'f', "heading",        lambda x: x ),
            (0x02BC, 'u', "speed",          lambda x: x / 128),
            (0x02C8, 'd', "vertical speed", lambda x: x * 60 * 3.28084 / 256),
            (0x0578, 'd', "pitch",          lambda x: -x * 360 / (65536*65536)),
            # (0x057C, 'd', "bank",           lambda x: -x * 360 / (65536*65536)),
            (0x2F78, 'f', "bank",           convert_bank),
            (0x0BFC, 'b', "flaps",          lambda x: x),
            (0x2400, 'f', "rpm",            lambda x: x),
            (0x088C, 'h', "throttle",       lambda x: x / 16384),
            (0x1140, 'f', "g-force",        lambda x: x),
            (0x0264, 'H', "pause",          lambda x: 1 * (x & 0x4 != 0)),
            (0x6010, 'f', "latitude",       lambda x: x),
            (0x6018, 'f', "longitude",      lambda x: x),
            (0x0366, 'h', "on ground",      lambda x: x),
        ]

        self.data_spec = self.fsuipc.prepare_data(
            [x[:2] for x in self.PARAMETERS_OF_INTEREST], for_reading=True)

    def get_parameters(self):
        param_values = self.data_spec.read()
        return {
            param_name: conversion(param_value) \
            for (_, _, param_name, conversion), param_value \
            in zip(self.PARAMETERS_OF_INTEREST, param_values)}

    def close(self):
        self.fsuipc.close()

class MainBackgroundWorker(threading.Thread):
    REFRESH_INTERVAL_MSEC = 75

    def __init__(self, args):
        self.should_exit = threading.Event()
        super().__init__(target=self, args=(args,))

    def __call__(self, args):
        try:
            flight = pilotschool.Flight(args.schedule)
            flight_progress = pilotschool.Progress(flight)
            captain_name = main_window.captain_name

            # from assess import load_frc
            # class flightsim_parameters_reader:
            #     records = load_frc("./old/tmp-flight.txt")[3000::]
            #     from tqdm import tqdm
            #     it = iter(tqdm(records))
            #     def get_parameters():
            #         return next(__class__.it)
            flightsim_parameters_reader = FlightSimParametersReader()

            prev_constraints = None
            prev_penalty = -1e9
            total_pause_time = 0.0
            pause_start_time = None

            while not self.should_exit.is_set():
                parameters = flightsim_parameters_reader.get_parameters()

                if parameters['pause'] == 1:
                    if pause_start_time is None:
                        pause_start_time = time.time()
                    continue
                else:
                    timestamp = time.time() # parameters['timestamp']
                    if pause_start_time is not None:
                        total_pause_time += timestamp - pause_start_time
                        pause_start_time = None

                has_segment_changed, constraints = flight_progress.step(parameters, timestamp - total_pause_time)

                if has_segment_changed:
                    if flight_progress.all_segments_completed():
                        total_penalties, _ = flight_progress.get_summary()
                        total_penalty = sum(total_penalties.values())

                        def get_output_path(total_penalty=0.0):
                            date = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
                            signature = \
                                round((math.sin(total_penalty + float(date.split('-')[-1])) + 1) * 1000)
                            output_file_name = \
                                f"{args.schedule.with_suffix('').name}, {captain_name}, " \
                                f"{date}, {signature}.csv"
                            return pathlib.Path("./Results") / output_file_name

                        output_path = get_output_path(total_penalty)
                        main_window.main_info_widget.display_summary(
                            total_penalty, output_path.resolve())
                        flight_progress.save_report(output_path)

                        return
                    else:
                        current_segment = flight_progress.get_current_segment()

                        hint = current_segment['Hint']
                        finish_param_name = current_segment['EndsAt']
                        finish_param_value = current_segment['EndsAtValue']

                        main_window.main_info_widget.update_hint(hint)
                        main_window.main_info_widget.update_finish_condition(finish_param_name, finish_param_value)

                    main_window.main_info_widget.blink()

                have_constraints_changed = constraints != prev_constraints
                if have_constraints_changed:
                    main_window.main_info_widget.update_constraints(constraints)
                    prev_constraints = constraints

                current_penalty = flight_progress.get_current_segment_penalty_total()
                has_penalty_changed = abs(current_penalty - prev_penalty) > 0.01
                if has_penalty_changed:
                    main_window.main_info_widget.update_penalty(current_penalty)
                    prev_penalty = current_penalty

                time.sleep(__class__.REFRESH_INTERVAL_MSEC / 1000)
        except Exception as exc:
            tkinter.messagebox.showerror("Unrecoverable error", str(exc))
            raise

    def exit(self):
        self.should_exit.set()
        self.join()


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="Assess a student's flight.")
    argparser.add_argument('schedule', metavar='path-to-schedule.csv', type=pathlib.Path,
                       help="Path to schedule csv containing flight segments, target parameters "
                            "(speed/bank/altitude/...) for each etc.")
    args = argparser.parse_args()

    background_worker = MainBackgroundWorker(args)

    # Create the GUI
    main_window = FlightInfoWindow(
        on_load_fn=background_worker.start,
        on_close_fn=background_worker.exit,
        title=args.schedule.with_suffix("").name)

    # Run the GUI main loop
    main_window.run()
