import pilotschool

import fsuipc

import pathlib
import tkinter.ttk, tkinter.messagebox
import threading
import sys
import contextlib
import time
import argparse

import logging
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="PID %(process)d - %(asctime)s - %(levelname)s - %(name)s - %(message)s")


class FlightInfoWindow(tkinter.Tk):
    def __init__(self, on_close_fn=lambda: None, title="<no title set>"):
        """
        on_close:
            callable
        """
        self.logger = logging.getLogger('FlightInfoWindow')

        self.is_running = False

        super().__init__()
        self.title("Flight Examiner")
        width, height = 300, 300
        self.geometry(f"{width}x{height}")
        self.attributes('-topmost',True)

        self.main_frame = tkinter.ttk.Frame(self)
        self.main_frame.grid() #pack(expand=True, fill='y')

        # Create widgets
        self.title_widget = tkinter.ttk.Label(self.main_frame, text=title)
        separator = tkinter.ttk.Separator(self.main_frame, orient='horizontal')
        self.main_text_widget = tkinter.ttk.Label(self.main_frame, text="")

        # Set widgets' positions
        self.title_widget.grid(row=0)
        separator.grid(row=1, sticky='ew')
        self.main_text_widget.grid(row=2)

        def _on_close():
            if tkinter.messagebox.askokcancel("Quit", "Really quit?"):
                on_close_fn()
                self.destroy()
        self.protocol("WM_DELETE_WINDOW", _on_close)

    def update_text(self, text):
        self.main_text_widget.config(text=text)

    def run(self):
        if self.is_running:
            self.logger.error("Cannot run() FlightInfoWindow twice")

        self.is_running = True
        self.mainloop()

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
        self.PARAMETERS_OF_INTEREST = [
            (0x3324, 'd', "altitude",  lambda x: x),
            (0x2B00, 'f', "heading",   lambda x: x ),
            (0x02BC, 'u', "speed",     lambda x: x / 128),
            (0x02C8, 'd', "vertSpeed", lambda x: x * 60 * 3.28084 / 256),
            (0x0578, 'd', "pitch",     lambda x: -x * 360 / (65536*65536)),
            (0x057C, 'd', "bank",      lambda x: -x * 360 / (65536*65536)),
            (0x0BFC, 'b', "flaps",     lambda x: x),
            (0x2400, 'f', "rpm",       lambda x: x),
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
    REFRESH_INTERVAL_MSEC = 50

    def __init__(self, args):
        self.should_exit = threading.Event()
        super().__init__(target=self, args=(args,))

    def __call__(self, args):
        try:
            flight = pilotschool.Flight(args.schedule)
            flight_progress = pilotschool.Progress(flight)

            flightsim_parameters_reader = FlightSimParametersReader()

            while not self.should_exit.is_set():
                parameters = flightsim_parameters_reader.get_parameters()
                text = "\n".join(f"{param_name}: {param_value}" for param_name, param_value in parameters.items())
                main_window.update_text(text)

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

    main_window = FlightInfoWindow(
        on_close_fn=background_worker.exit,
        title=args.schedule.with_suffix("").name)

    # Run main() in the background
    background_worker.start()

    main_window.run()
