frc2ascii %1 tmp-flight.txt
python assess.py TurnsTest/TurnsTest.csv tmp-flight.txt TurnsTest/TurnsConfig.csv --debug
pause