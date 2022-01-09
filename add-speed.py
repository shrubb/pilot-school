with open('tmp-flight.txt', 'r') as input_file:
    with open('tmp-flight-speeds.txt', 'w') as output_file:
        for i, line in enumerate(input_file):
            if i <= 3:
                output_file.write(line)
                continue

            vals = line.split()
            x,y,z = map(float, vals[7:7+3])
            import math
            speed = math.sqrt(x**2 + y**2 + z**2) * 0.592484
            output_file.write('%.2f\t' % speed + '\t'.join(vals) + '\n')
