import pilotschool

def assess_one_flight(task, flight_rec_txt, task_config, debug=False):
    recording = pilotschool.load_frc(flight_rec_txt)
    task = pilotschool.load_task(task)
    default_tolerances, default_penalties = \
        pilotschool.load_task_config(task_config)

    current_task_idx = 0
    prev_timestamp = 0
    task[0]['StartTime'] = 0
    total_penalties = {k: 0.0 for k in default_tolerances}
    current_segment_penalties = {k: 0.0 for k in default_tolerances}

    from copy import copy
    current_tolerances = copy(default_tolerances)
    current_penalties = copy(default_penalties)
    all_penalties = []
    pilotschool.separate_tolerances_and_penalties(
        current_tolerances, current_penalties, task[current_task_idx])

    for i,record in enumerate(recording[1:]):
        duration = record['timestamp'] - prev_timestamp
        prev_timestamp = record['timestamp']
        
        # maybe jump to next segment (maybe even several times)
        while pilotschool.segment_has_ended(record, task[current_task_idx]):
            current_segment_penalties['Segment'] = task[current_task_idx]['Name']
            all_penalties.append(copy(current_segment_penalties))

            for param in total_penalties.keys():
                current_segment_penalties[param] = 0
                
            current_task_idx += 1
                
            if current_task_idx == len(task):
                # no more task segments left
                break
            else:
                # update default tolerances and penalties if custom ones are defined in current segment
                current_tolerances = copy(default_tolerances)
                current_penalties = copy(default_penalties)
                pilotschool.separate_tolerances_and_penalties(
                    current_tolerances, current_penalties, task[current_task_idx])
            
                task[current_task_idx]['StartTime'] = record['timestamp']

        if current_task_idx == len(task):
            # no more task segments left
            break
        
        # check params and maybe apply penalty
        pilotschool.update_penalty(
            current_segment_penalties, current_penalties, record, task[current_task_idx], current_tolerances, duration)

    return all_penalties, len(task)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Assess a student\'s flight.')
    parser.add_argument('task', metavar='path-to-task.csv', type=str,
                       help='Path to task csv containing flight segments, desired pitch/bank/altitude etc.')
    parser.add_argument('flight_rec_txt', metavar='path-to-flight-recording.txt', type=str,
                       help='Path to flight recording converted to *.txt from *.frc')
    parser.add_argument('task_config', metavar='path-to-task-config.csv', type=str, nargs='?',
                       help='Path to task config csv containing tolerances and penalties')
    parser.add_argument('--debug', action='store_true',
                        help='Print debug data such as intermediate penalties')
    args = parser.parse_args()

    all_penalties, total_segments_in_file = assess_one_flight(args.task, args.flight_rec_txt, args.task_config, args.debug)
    
    total_penalties = {k: 0.0 for k in all_penalties[0] if k != 'Segment'}
    for segment_penalties in all_penalties:
        if args.debug:
            print('Penalties for ' + segment_penalties['Segment'] + ':')
            for param, penalty in segment_penalties.items():
                if param != 'Segment':
                    print('{:16}{}'.format(param, penalty))
            print('')

        for param, penalty in segment_penalties.items():
            if param != 'Segment':
                total_penalties[param] += segment_penalties[param]
            
    if len(all_penalties) != total_segments_in_file:
        print('WARNING: only {}/{} tasks completed'.format(len(all_penalties), total_segments_in_file))

    print('********** Total penalties: **********')
    muted_criteria = 'pitch', 'flaps', 'throttle1'
    for k, v in total_penalties.items():
        if k not in muted_criteria:
            print('{:16}{:.2f}'.format(k, v))
    print('')

    print('Sum: ' + str(sum(total_penalties.values())))
