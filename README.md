# xoss_sync
A python code to fetch fit files from XOSS G+ cyclo-computer over bluetooth (BLE) for you.

(C) 2024 [ekspla](https://github.com/ekspla/xoss_sync)

A quick/preliminary version of code for use with XOSS G+ GPS cyclo-computer, inspired by [f-xoss project](https://github.com/DCNick3/f-xoss).

This code is a modified version of [cycsync.py](https://github.com/Kaiserdragon2/CycSync) for Cycplus M2, which does not work for my use case as is.

The code shown here was tested with XOSS G+ (gen1), Windows10 on Core-i5, TPLink USB BT dongle (UB400, v4.0), Python-3.8.6 and Bleak-0.22.2.

## Features
This script allows you to:

- Obtain a list of data files on your device
- Download data (in FIT fromat) from your device
- See free/usage of storage in your device

## Usage
1. Install bluetooth low energy interface/driver software on your PC.

2. Check if your device and the PC are paired.

3. Install [python](https://www.python.org/) (of course).

4. Install [bleak](https://pypi.org/project/bleak/):

```
pip install bleak
```

5. Download and run the script:

```
python xoss_sync.py
```

Though I tested this only with XOSS G+ (gen1) and Windows10/11, combinations of the other XOSS device/OS might work.
C.f. [Bleak](https://github.com/hbldh/bleak) supports Android, MacOS, Windows, and Linux.


## Limitation
The script seems to work perfectly for my use case as shown above, but there are possible limitations due mainly to the implementation
of YMODEM in part as followings.

- The script expects a transport with MTU of 23, 128-byte data per block, and CRC16/ARC (not CRC16/XMODEM).  I am not sure
if the SoC(seems to be nRF52832)/software in the XOSS device supports larger MTU nor 1024-byte data in YMODEM(see, Notes 1).
- Successive block numbers in YMODEM transport are not checked.

## Notes
1. My XOSS-G+ (Gen1) was found to be not changing MTU(23)/data size(128) with Win11 and Bluetooth 5.1 interface, which always 
request MTU of 525, while [f-xoss project](https://github.com/DCNick3/f-xoss) for XOSS-NAV used MTU of 206.
