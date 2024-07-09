# xoss_sync
A python code to fetch fit files from XOSS G+ cyclo-computer

(C) 2024 [ekspla](https://github.com/ekspla/xoss_sync)

A quick/preliminary version of code to fetch fit files from XOSS G+ cyclo-computer, inspired by f-xoss project 
(https://github.com/DCNick3/f-xoss).

This code is a modified version of cycsync.py (https://github.com/Kaiserdragon2/CycSync) for Cycplus M2, and 
it was tested with XOSS G+, Win10 on Core-i5, TPLink USB BT dongle, py-3.8.6 and bleak-0.22.2.

TODO:
1. send NACK on error, to request the correct data block once again.
2. handling of fit-file data more efficiently on memory.
