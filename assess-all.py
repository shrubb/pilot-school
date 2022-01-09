import csv
import os
from assess import assess_one_flight

try:
    with open('Exam\\points.csv', 'w', newline='') as csv_file:
        field_names = [
            'Last name',
            'Segments completed',
            'altitude',
            'vertSpeed',
            'heading',
            'speed',
            'bank',
            'flaps',
            'MaxTimeLength']
        csv_writer = csv.DictWriter(csv_file, field_names)

        csv_writer.writeheader()

        for new_or_old in 'Old', 'New':
            recordings_dir = 'Exam\\Recordings\\' + new_or_old + ' scenario\\'
            for file_name in os.listdir(recordings_dir):
                os.system('frc2ascii.exe "' + recordings_dir + file_name + '" tmp-flight.txt')
                all_penalties, total_tasks = assess_one_flight(
                    'Exam\\Exam' + new_or_old + '.csv',
                    'tmp-flight.txt',
                    'Exam\\ExamConfig.csv')

                total_penalties = {k: 0.0 for k in all_penalties[0] if k != 'Segment'}
                for segment_penalties in all_penalties:
                    for param, penalty in segment_penalties.items():
                        if param != 'Segment':
                            total_penalties[param] += segment_penalties[param]

                del total_penalties['throttle1'], total_penalties['pitch']
                total_penalties['Segments completed'] = len(all_penalties)
                total_penalties['Last name'] = file_name[6:file_name.index('-exam.frc')]

                csv_writer.writerow(total_penalties)
                
except Exception as e:
    print(e)
    input()
