import math
import csv
import pathlib

class Flight:
    """A flight with stages/limits/penalties (predefined by "schedule", a .csv table) and progress.
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

        self.schedule = self.load_schedule(schedule_path)
        self.tolerances, self.penalty_coefficients = self.load_penalty_config(schedule_path)

    @staticmethod
    def load_schedule(schedule_path: pathlib.Path):
        with open(schedule_path, newline='') as csvfile:
            # strip because Excel seems not to allow cell values starting with minus
            return [{k: v.strip() for k,v in x.items()} for x in csv.DictReader(csvfile) if x['EndsAt']]

    @staticmethod
    def load_penalty_config(schedule_path: pathlib.Path):
        # Default values: how much is the pilot allowed to deviate without penalty
        tolerances = {
            'altitude': 100.0,
            'vertSpeed': 150.0,
            'heading': 5.0,
            'speed': 7.0,
            'pitch': 5.0,
            'bank': 5.0,
            'flaps': 0.0,
            'throttle1': 1000.0,
            'ResponseTime': 0.0}

        # Default values: what is the penalty for 1 second of deviation
        penalties = {
            'altitude': 1.0,
            'vertSpeed': 1.0,
            'heading': 1.0,
            'speed': 1.0,
            'pitch': 1.0,
            'bank': 1.0,
            'flaps': 1.0,
            'throttle1': 1.0,
            'ResponseTime': 1.0}

        special_config_suffix = " (config)"
        config_path = schedule_path.parent / \
            f"{schedule_path.with_suffix('')}{special_config_suffix}{schedule_path.suffix}"

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
                        tolerances[name] = parse_tolerance(value)

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



def parse_tolerance(tol_range_string):
    # accepts '+-9.45' or '+7-3.5'
    if tol_range_string[:2] == '+-':
        radius = float(tol_range_string[2:])
        return (-radius, radius)
    elif tol_range_string:
        radius_lo = float(tol_range_string[tol_range_string.index('-'):])
        radius_hi = float(tol_range_string[:tol_range_string.index('-')])
        return (radius_lo, radius_hi)


def segment_has_ended(record, segment):
    if segment['EndsAtParameterTolerance'] == '>=':
        if segment['EndsAt'] == 'Time':
            return record['timestamp'] - segment['StartTime'] >= float(segment['EndsAtParameter'])
        else:
            return float(record[segment['EndsAt']]) >= float(segment['EndsAtParameter'])
    elif segment['EndsAtParameterTolerance'] == '<=':
        return float(record[segment['EndsAt']]) <= float(segment['EndsAtParameter'])
    else:
        target_param = float(segment['EndsAtParameter'])
        actual_param = record[segment['EndsAt']]
        tolerance = float(segment['EndsAtParameterTolerance'])
        return target_param - tolerance <= actual_param and actual_param <= target_param + tolerance

def check_within_tolerance(param_name, task, record, tolerance):
    if not task[param_name]:
        return True

    target_param = task[param_name]

    if param_name == 'ResponseTime':
        actual_param = record['timestamp'] - task['StartTime']
        return actual_param <= target_param + tolerance[1]
    else:
        actual_param = record[param_name]
        return target_param + tolerance[0] <= actual_param and actual_param <= target_param + tolerance[1]

def separate_tolerances_and_penalties(tolerances, penalties, task_segment):
    for parameter in tolerances.keys():
        tol_range_string = task_segment[parameter]

        # strip '; p4.5' at the end
        if '; p' in tol_range_string:
            penalty_idx = tol_range_string.index('; p')
            penalties[parameter] = float(tol_range_string[penalty_idx+3:])
            tol_range_string = tol_range_string[:penalty_idx]

        # remove the "ideal" desired parameter value
        if '+' in tol_range_string:
            tol_range = tol_range_string.lstrip('0123456789.-')
            tolerances[parameter] = parse_tolerance(tol_range)

            tol_range_string = tol_range_string[:tol_range_string.index('+')]

        task_segment[parameter] = float(tol_range_string) if tol_range_string else None

def update_penalty(current_penalties, penalties, record, task, tolerances, record_duration):
    for param, param_penalty in penalties.items():
        if not check_within_tolerance(param, task, record, tolerances[param]):
            current_penalties[param] += penalties[param] * record_duration
