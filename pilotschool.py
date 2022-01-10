import math
import csv
import pathlib
import copy

# Default values that can be overriden both in "... (config).csv" (for the entire flight)
# and in ".csv" (for each segment separately).
class DEFAULTS:
    # How much is the pilot allowed to deviate without penalty?
    tolerances = {
        'altitude': 90.0,
        'vertical speed': 150.0,
        'heading': 5.0,
        'speed': 7.0,
        'pitch': 5.0,
        'bank': 5.0,
        'flaps': 0.0,
        'throttle': 0.06,
        'rpm': 90.0,
        'ResponseTime': 0.0,
    }

    # What is the penalty for 1 second of deviation?
    penalties = {
        'altitude': 1.0,
        'vertical speed': 1.0,
        'heading': 1.0,
        'speed': 1.0,
        'pitch': 1.0,
        'bank': 1.0,
        'flaps': 1.0,
        'throttle': 1.0,
        'rpm': 1.0,
        'ResponseTime': 1.0,
    }


class Flight:
    """A flight with stages/limits/penalties (predefined by "schedule", a .csv table).
    """
    def __init__(self, schedule_path: pathlib.Path):
        """
        schedule_path:
            Path to a .csv file defining flight stages.
            If a file suffixed " (config)" is also found (example: "Exam.csv" and
            "Exam (config).csv"), it's treated as the penalty config. Its two only rows (the
            header not counted) define tolerances (the non-penalizable parameter corridor) and
            penalty coefficients (what is the penalty for 1 second of deviation) respectively.
        """
        schedule_path = pathlib.Path(schedule_path)

        self.tolerances, self.penalty_coeffs, self.schedule = \
            self.load_schedule_and_config(schedule_path)

    def __len__(self):
        return len(self.schedule)

    @staticmethod
    def load_schedule_and_config(schedule_path: pathlib.Path):
        # Load "XYZ.csv"
        schedule = __class__.load_schedule(schedule_path)

        # Load "XYZ (config).csv"
        special_config_suffix = " (config)"
        config_path = schedule_path.parent / \
            f"{schedule_path.with_suffix('')}{special_config_suffix}{schedule_path.suffix}"
        default_tolerances, default_penalty_coeffs = __class__.load_penalty_config(config_path)

        # Remove penalties from loaded schedule and apply them to get
        # tols/penalty_coeffs for each segment.
        tolerances_per_segment, penalty_coeffs_per_segment, schedule_updated = \
            zip(*[__class__.extract_tolerances_and_penalty_coeffs(
                default_tolerances, default_penalty_coeffs, segment) for segment in schedule])

        return tolerances_per_segment, penalty_coeffs_per_segment, schedule_updated

    @staticmethod
    def load_schedule(schedule_path: pathlib.Path):
        with open(schedule_path, newline='') as csvfile:
            # strip because Excel seems not to allow cell values starting with minus
            return [{k: v.strip() for k,v in x.items()} for x in csv.DictReader(csvfile) if x['EndsAt']]

    @staticmethod
    def load_penalty_config(config_path: pathlib.Path):
        tolerances = copy.copy(DEFAULTS.tolerances)
        penalties = copy.copy(DEFAULTS.penalties)

        if config_path.is_file():
            with open(config_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                new_tolerances = next(reader)
                new_penalties = next(reader)

                for name,value in new_tolerances.items():
                    assert name in tolerances, name + ' in ' + path + ' is invalid'
                    if value:
                        # strip because Excel seems not to allow cell values starting with minus
                        value = value.strip()
                        tolerances[name] = __class__.parse_tolerance(value)

                for name,value in new_penalties.items():
                    assert name in penalties, name + ' in ' + path + ' is invalid'
                    if value:
                        # strip because Excel seems not to allow cell values starting with minus
                        value = value.strip()
                        penalties[name] = float(value)

        for k,v in tolerances.items():
            if type(tolerances[k]) is not tuple:
                assert type(tolerances[k]) is float
                tolerances[k] = (-tolerances[k], tolerances[k])

        return tolerances, penalties

    @staticmethod
    def extract_tolerances_and_penalty_coeffs(
        default_tolerances, default_penalty_coeffs, segment):
        """Strips `segment`'s (segment definition) entries of tolerances and penalty coeffs
        (i.e. "60+5-10; p4.5" becomes 60.0 and "10+-3.5" becomes 10.0).
        `default_tolerances`, `default_penalty_coeffs` are updated with the extracted ones
        and returned.

        Not in-place, copies are returned.

        return:
            updated_tolerances
            updates_penalty_coeffs
            segment_stripped_of_tolerances_and_penalty_coeffs
        """
        updated_tolerances = copy.copy(default_tolerances)
        updated_penalty_coeffs = copy.copy(default_penalty_coeffs)
        segment_without_tol_pen = copy.copy(segment)

        for parameter in default_tolerances.keys():
            tol_range_string = segment[parameter]

            # strip '; p4.5' at the end
            if '; p' in tol_range_string:
                penalty_idx = tol_range_string.index('; p')
                updated_penalty_coeffs[parameter] = float(tol_range_string[penalty_idx+3:])
                tol_range_string = tol_range_string[:penalty_idx]

            # remove the "ideal" desired parameter value
            if '+' in tol_range_string:
                tol_range = tol_range_string.lstrip('0123456789.-')
                updated_tolerances[parameter] = __class__.parse_tolerance(tol_range)

                tol_range_string = tol_range_string[:tol_range_string.index('+')]

            segment_without_tol_pen[parameter] = float(tol_range_string) if tol_range_string else None

        return updated_tolerances, updated_penalty_coeffs, segment_without_tol_pen

    @staticmethod
    def parse_tolerance(tol_range_string):
        # accepts '+-9.45' or '+7-3.5'
        if tol_range_string[:2] == '+-':
            radius = float(tol_range_string[2:])
            return (-radius, radius)
        elif tol_range_string:
            radius_lo = float(tol_range_string[tol_range_string.index('-'):])
            radius_hi = float(tol_range_string[:tol_range_string.index('-')])
            return (radius_lo, radius_hi)


class Progress:
    """Progress tracker for a Flight that also evaluates penalty scores.
    """
    def __init__(self, flight: Flight):
        self.flight = copy.copy(flight)

        self.penalties_history = []
        self.current_segment_idx = None
        self.prev_timestamp = None
        self.current_segment_penalties = {k: 0.0 for k in DEFAULTS.tolerances}

        self.flight.schedule[0]['StartTime'] = 0 # TODO remove

    def all_segments_completed(self):
        return self.current_segment_idx is not None and \
               self.current_segment_idx >= len(self.flight)

    def get_current_segment(self):
        if self.current_segment_idx is None:
            retval = {param_name: None for param_name in DEFAULTS.tolerances.keys()}
            retval['Hint'] = '(dummy)'
            return retval
        else:
            return self.flight.schedule[self.current_segment_idx]

    def step(self, record, timestamp):
        """
        return:
        has_segment_changed
            bool
            True if this step has shifted us to some next segment.
        constraints
            list of (str, number, bool)
            Each tuple means (parameter name, parameter value, is constraint currently met)
        """
        if self.all_segments_completed():
            return False, []

        if self.prev_timestamp is None:
            self.prev_timestamp = timestamp
            return False, []

        duration = timestamp - self.prev_timestamp
        self.prev_timestamp = timestamp

        # maybe jump to next segment (maybe even several times)
        segment_has_changed = False
        while self.segment_has_ended(record, timestamp):
            segment_has_changed = True

            if self.current_segment_idx is None:
                self.current_segment_idx = 0
            else:
                segment_name = self.get_current_segment()['Hint']
                self.penalties_history.append(
                    (segment_name, copy.copy(self.current_segment_penalties)))

                self.current_segment_idx += 1

            self.current_segment_penalties = {k: 0.0 for k in DEFAULTS.tolerances}

            if self.all_segments_completed():
                # no more schedule segments left
                break
            else:
                # TODO remove
                self.get_current_segment()['StartTime'] = timestamp

        if self.all_segments_completed():
            # no more schedule segments left
            return segment_has_changed, []

        # check params and maybe apply penalty
        constraints = self._update_penalty(record, timestamp, duration)

        return segment_has_changed, constraints

    def _update_penalty(self, record, timestamp, record_duration):
        tolerances = self.flight.tolerances[self.current_segment_idx]
        penalty_coeffs = self.flight.penalty_coeffs[self.current_segment_idx]
        segment = self.get_current_segment()
        constraints_retval = []

        for param_name, param_penalty in penalty_coeffs.items():
            constraint_is_met = __class__.check_within_tolerance(
                param_name, segment, record, timestamp, tolerances[param_name])

            if not constraint_is_met:
                self.current_segment_penalties[param_name] += penalty_coeffs[param_name] * record_duration

            if segment[param_name] is not None:
                constraints_retval.append((param_name, segment[param_name], constraint_is_met))

        return constraints_retval

    def get_current_segment_penalty_total(self):
        return sum(self.current_segment_penalties.values())

    def get_summary(self):
        total_penalties = {k: 0.0 for k in DEFAULTS.tolerances}

        for segment_name, segment_penalties in self.penalties_history:
            for param in DEFAULTS.tolerances:
                total_penalties[param] += segment_penalties[param]

        return total_penalties, self.penalties_history

    def save_report(self, output_path):
        with open(output_path, 'w', newline='') as csvfile:
            field_names = ['Segment name'] + sorted(DEFAULTS.tolerances)
            csv_writer = csv.DictWriter(csvfile, field_names, delimiter=',')

            csv_writer.writeheader()
            for segment_name, segment_penalties in self.penalties_history:
                row = copy.copy(segment_penalties)
                row['Segment name'] = segment_name
                csv_writer.writerow(row)

    def segment_has_ended(self, record, timestamp):
        if self.current_segment_idx is None:
            return True

        segment = self.get_current_segment()

        if segment['EndsAtValueTolerance'] == '>=':
            if segment['EndsAt'] == 'Time':
                return timestamp - segment['StartTime'] >= float(segment['EndsAtValue'])
            else:
                return float(record[segment['EndsAt']]) >= float(segment['EndsAtValue'])
        elif segment['EndsAtValueTolerance'] == '<=':
            return float(record[segment['EndsAt']]) <= float(segment['EndsAtValue'])
        else:
            if segment['EndsAtValueTolerance'] == "":
                tolerance = DEFAULTS.tolerances[segment['EndsAt']]
            else:
                tolerance = float(segment['EndsAtValueTolerance'])

            target_param = float(segment['EndsAtValue'])
            actual_param = record[segment['EndsAt']]
            return target_param - tolerance <= actual_param and actual_param <= target_param + tolerance

    @staticmethod
    def check_within_tolerance(param_name, segment, record, timestamp, tolerance):
        if segment[param_name] is None:
            return True

        target_param = segment[param_name]

        if param_name == 'ResponseTime':
            actual_param = timestamp - segment['StartTime']
            return actual_param <= target_param + tolerance[1]
        else:
            actual_param = record[param_name]
            return target_param + tolerance[0] <= actual_param and actual_param <= target_param + tolerance[1]
