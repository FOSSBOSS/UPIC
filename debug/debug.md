## wtf is that tapping??
Ok  its really on any frq shift.  might be a limitation of the device, 
Might be able to thing of a creative solution, I just havent yet. :(
The timing of it is the only part that really has me trippin. 
why isnt it instant???

```bleh
 ./utg_tap_scan.py --channel 1 --retune-seconds 20 570  
 ./utg_tap_scan.py --channel 1  
 ./utg_tap_scan.py --channel 2
```

```out
$ python3 ./utg_tap_scan.py --channel 1
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  5 Hz vibrato
Logging to /home/l/UPIC/debug/utg_tap_timing.csv
Press Enter when you hear tapping.
570 Hz
Tapping 570  (CH1, 1.86 s, retuning)
110 Hz
Tapping 110  (CH1, 2.32 s, retuning)
155.6 Hz
Tapping 155.6  (CH1, 2.29 s, retuning)
220 Hz
Tapping 220  (CH1, 2.05 s, retuning)
311.1 Hz
Tapping 311.1  (CH1, 1.77 s, retuning)
440 Hz
Tapping 440  (CH1, 1.71 s, retuning)
622.3 Hz
Tapping 622.3  (CH1, 1.71 s, retuning)
880 Hz
Tapping 880  (CH1, 2.34 s, retuning)
1244.5 Hz
Tapping 1244.5  (CH1, 1.74 s, retuning)
1760 Hz
Tapping 1760  (CH1, 1.78 s, retuning)

$ python3 ./utg_tap_scan.py --channel 2
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  5 Hz vibrato
Logging to /home/l/UPIC/debug/utg_tap_timing.csv
Press Enter when you hear tapping.
570 Hz

Tapping 570  (CH2, 1.82 s, retuning)
110 Hz
Tapping 110  (CH2, 2.24 s, retuning)
155.6 Hz
Tapping 155.6  (CH2, 2.35 s, retuning)
220 Hz
Tapping 220  (CH2, 1.90 s, retuning)
311.1 Hz
Tapping 311.1  (CH2, 1.73 s, retuning)
440 Hz
Tapping 440  (CH2, 2.18 s, retuning)
622.3 Hz
Tapping 622.3  (CH2, 1.81 s, retuning)
880 Hz
Tapping 880  (CH2, 1.90 s, retuning)
1244.5 Hz
Tapping 1244.5  (CH2, 1.77 s, retuning)
1760 Hz
Tapping 1760  (CH2, 1.75 s, retuning)

```  


## any frq change step might produce taps. 
```
$./utg_retune_test.py --pure --step-hz 0.4 --interval-ms 500
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 500.1 ms
C  Hold 570 Hz
D  Alternate 570 and 570.4 Hz
  Average interval including USB writes: 500.1 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 0.01 --interval-ms 500
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
^C
Interrupted.
$./utg_retune_test.py --pure --step-hz 0.01 --interval-ms 50
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.7 ms
C  Hold 570 Hz
D  Alternate 570 and 570.01 Hz
  Average interval including USB writes: 84.8 ms
E  Hold 570 Hz

$./utg_retune_test.py --pure --step-hz 0.9 --interval-ms 50
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.7 ms
C  Hold 570 Hz
D  Alternate 570 and 570.9 Hz
  Average interval including USB writes: 84.8 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 1.0 --interval-ms 50
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.7 ms
C  Hold 570 Hz
D  Alternate 570 and 571 Hz
  Average interval including USB writes: 84.8 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 0.25 --interval-ms 50
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.7 ms
C  Hold 570 Hz
D  Alternate 570 and 570.25 Hz
  Average interval including USB writes: 84.8 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 0.5 --interval-ms 30
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.6 ms
C  Hold 570 Hz
D  Alternate 570 and 570.5 Hz
  Average interval including USB writes: 84.9 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 0.2 --interval-ms 10
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.6 ms
C  Hold 570 Hz
D  Alternate 570 and 570.2 Hz
  Average interval including USB writes: 84.9 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 200 --interval-ms 10
usage: utg_retune_test.py [-h] [--pure] [--resource RESOURCE] [--step-hz STEP_HZ] [--interval-ms INTERVAL_MS]
utg_retune_test.py: error: use a step of 0.000001–100 Hz and an interval of 1–2000 ms
$./utg_retune_test.py --pure --step-hz 20.0 --interval-ms 10
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.7 ms
C  Hold 570 Hz
D  Alternate 570 and 590 Hz
  Average interval including USB writes: 84.8 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 200.0 --interval-ms 10
usage: utg_retune_test.py [-h] [--pure] [--resource RESOURCE] [--step-hz STEP_HZ] [--interval-ms INTERVAL_MS]
utg_retune_test.py: error: use a step of 0.000001–100 Hz and an interval of 1–2000 ms
$./utg_retune_test.py --pure --step-hz 100.0 --interval-ms 10
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.7 ms
C  Hold 570 Hz
D  Alternate 570 and 670 Hz
  Average interval including USB writes: 84.8 ms
E  Hold 570 Hz
$./utg_retune_test.py --pure --step-hz 100.0 --interval-ms 10
UNI-T Technologies,UTG900E,AWG1225220117,3.06  |  Pure sine
A  Hold 570 Hz
B  Repeatedly write 570 Hz
  Average interval including USB writes: 70.7 ms
C  Hold 570 Hz
D  Alternate 570 and 670 Hz
  Average interval including USB writes: 84.8 ms
E  Hold 570 Hz


```
