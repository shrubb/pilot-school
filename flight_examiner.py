from fsuipc import FSUIPC

import tkinter.ttk, tkinter.messagebox
import threading
import sys
import time

import logging
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="PID %(process)d - %(asctime)s - %(levelname)s - %(name)s - %(message)s")


class FlightInfoWindow(tkinter.Tk):
    def __init__(self, title="<no title set>"):
        self.logger = logging.getLogger('FlightInfoWindow')

        self.is_running = False

        super().__init__()
        self.title("Flight Examiner")
        width, height = 300, 300
        self.geometry(f"{width}x{height}")
        self.main_frame = tkinter.ttk.Frame(self)
        self.main_frame.pack(expand=True, fill='y')

        self.title_widget = tkinter.ttk.Label(self.main_frame, text=title)
        separator = tkinter.ttk.Separator(self.main_frame, orient='horizontal')
        self.main_text_widget = tkinter.ttk.Label(self.main_frame, text="")

        self.title_widget.grid(row=0)
        separator.grid(row=1, sticky='ew')
        self.main_text_widget.grid(row=2)

    def update_text(self, text):
        self.main_text_widget.config(text=text)

    def run(self):
        if self.is_running:
            self.logger.error("Cannot run() FlightInfoWindow twice")

        self.is_running = True
        self.mainloop()


def main():
    while True:
        new_text = f"""
        a {time.time()}
        b {666}
        """
        main_window.update_text(new_text)
        time.sleep(1)

    try:
        with FSUIPC() as fsuipc:
            data_spec = []

            def size_per_dtype(dtype):
                if dtype in ('b', 'c'):
                    return 1
                elif dtype in ('h', 'H'):
                    return 2
                elif dtype in ('d', 'u', 'F'):
                    return 4
                elif dtype in ('l', 'L', 'f'):
                    return 8
                else:
                    raise ValueError(f"Wrong py-fsuipc dtype: {dtype}")

            def add_field_to_spec(address, dtype):
                data_spec.append((address, dtype))
                return size_per_dtype(dtype)

            ptr = 0x02B4
            ptr += add_field_to_spec(ptr, 'u')
            ptr += add_field_to_spec(ptr, 'u')
            ptr += add_field_to_spec(ptr, 'u')
            ptr = 0x0560
            ptr += add_field_to_spec(ptr, 'l')
            ptr += add_field_to_spec(ptr, 'l')
            ptr += add_field_to_spec(ptr, 'l')
            ptr += add_field_to_spec(ptr, 'd')
            ptr += add_field_to_spec(ptr, 'd')
            ptr += add_field_to_spec(ptr, 'u')

            prepared = fsuipc.prepare_data(data_spec, True)

            while True:
                gs, tas, ias, lat, lon, alt, pitch, bank, hdgT = prepared.read()

                gs = (gs * 3600) / (65536 * 1852)
                tas = tas / 128
                ias = ias / 128
                lat = lat * 90 / (10001750 * 65536 * 65536)
                lon = lon * 360 /  (65536 * 65536 * 65536 * 65536)
                alt = alt * 3.28084 / (65536 * 65536)
                pitch = pitch * 360 / (65536 * 65536)
                bank = bank * 360 / (65536 * 65536)

                print(f"gs = {gs}")
                print(f"tas = {tas}")
                print(f"ias = {ias}")
                print(f"lat = {lat}")
                print(f"lon = {lon}")
                print(f"alt = {alt}")
                print(f"pitch = {pitch}")
                print(f"bank = {bank}")

                input("Press ENTER to read again")
    except Exception as exc:
        tkinter.messagebox.showerror("Unrecoverable error", str(exc))
        raise


if __name__ == "__main__":
    main_window = FlightInfoWindow()

    # Run main() in the background
    threading.Thread(target=main).start()

    main_window.run()
