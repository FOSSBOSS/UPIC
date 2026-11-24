The Bash upic was pretty hacked. Now I have a dual chanel UNI-T UTG932E function generator.
Programed with pyvisa. 
https://pyvisa.readthedocs.io/en/latest/  
https://www.iannis-xenakis.org/  

## setup udev
```cmd
 echo 'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="6656", ATTR{idProduct}=="0834", TAG+="uaccess"' |
  sudo tee /etc/udev/rules.d/70-utg932e.rules
```
## get libraries
```py
python -m pip install pyvisa pyvisa-py pyusb
```


## linux dependencies:
```
sudo apt install python3-venv libusb-1.0-0
```

