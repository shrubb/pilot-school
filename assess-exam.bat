frc2ascii %1 tmp-flight.txt
python assess.py Exam/ExamNew.csv tmp-flight.txt Exam/ExamConfig.csv --debug
pause