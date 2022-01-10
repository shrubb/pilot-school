import pilotschool

import copy
import math

def load_frc(path):
    retval = []

    with open(path, 'r') as f:
        line = next(f)
        while '#Data' not in line:
            line = next(f)
        param_names = line[7:].split()

        for line in f:
            param_values = map(float, line.split())
            record = {k: v for k,v in zip(param_names, param_values)}

            record['vertical speed'] = record['velocityY'] * 60
            record['speed'] = math.sqrt( \
                record['velocityX'] ** 2 +
                record['velocityY'] ** 2 +
                record['velocityZ'] ** 2) * 0.592484 # 1 ft/sec in kts

            retval.append(record)

    return retval

def assess_one_flight(schedule_path, flight_rec_txt, debug=False):
    recording = load_frc(flight_rec_txt)

    flight = pilotschool.Flight(schedule_path)
    progress = pilotschool.Progress(flight)

    for record in recording[1:]:
        progress.step(record, record['timestamp'])

    total_penalties, penalties_history = progress.get_summary()
    return total_penalties, penalties_history, len(flight)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Assess a student\'s flight.')
    parser.add_argument('schedule', metavar='path-to-schedule.csv', type=str,
                       help='Path to schedule csv containing flight segments, desired pitch/bank/altitude etc.')
    parser.add_argument('flight_rec_txt', metavar='path-to-flight-recording.txt', type=str,
                       help='Path to flight recording converted to *.txt from *.frc')
    parser.add_argument('--debug', action='store_true',
                        help='Print debug data such as intermediate penalties')
    args = parser.parse_args()

    total_penalties, penalties_history, total_segments_in_file = assess_one_flight(args.schedule, args.flight_rec_txt, args.debug)

    for segment_name, segment_penalties in penalties_history:
        if args.debug:
            print(f'Penalties for {segment_name}:')
            for param, penalty in segment_penalties.items():
                    print('{:16}{}'.format(param, penalty))
            print('')

    if len(penalties_history) != total_segments_in_file:
        print('WARNING: only first {}/{} segments completed'.format(len(penalties_history), total_segments_in_file))

    print('********** Total penalties: **********')
    muted_criteria = 'pitch', 'flaps', 'throttle1'
    for k, v in total_penalties.items():
        if k not in muted_criteria:
            print('{:16}{:.2f}'.format(k, v))
    print('')

    print('Sum: ' + str(sum(total_penalties.values())))
