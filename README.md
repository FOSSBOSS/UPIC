The Bash upic was pretty hacked. Now I have a dual chanel UNI-T UTG932E function generator.
Programed with pyvisa. 
https://pyvisa.readthedocs.io/en/latest/  
https://www.centre-iannis-xenakis.org/cix_upic_presentation?lang=en  

## setup udev
```cmd
 echo 'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="6656", ATTR{idProduct}=="0834", TAG+="uaccess"' |
  sudo tee /etc/udev/rules.d/70-utg932e.rules
```
## get libraries
```py
python -m pip install pyvisa pyvisa-py pyusb zeroconf
```


## linux dependencies:
```
sudo apt install python3-venv libusb-1.0-0
```

## run:
```
$ ./bridge.py 
/home/l/.local/lib/python3.12/site-packages/pyvisa/resources/messagebased.py:702: UserWarning: read string doesn't end with termination characters
  return self.read()
UNI-T Technologies,UTG900E,AWG1225220117,3.06
Open http://127.0.0.1:8765 in your browser. Ctrl-C to quit.

```
The warning is from pyvisa, and I havent found the fix yet


## Notes: 
Swtiching OFF, produces clicks on the chanels so we avoid that except for turning the 
Function Generator off with  stop button. 

Else, we set the output low, to 0.1 hz to be inaudable, but not trigger the chanel relays.

## Todo:
- low drop out pulsing on transient beats. 
- gracefull exit.
- gracefull disconnect

## video
<a href="https://www.youtube.com/watch?v=3b8PJqtfe9s"> web interface</a>

<img src="img/scketch.png">
