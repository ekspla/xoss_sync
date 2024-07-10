# xoss_sync
A python code to fetch fit files from XOSS G+ cyclo-computer over bluetooth (BLE) for you.

(C) 2024 [ekspla](https://github.com/ekspla/xoss_sync)

A quick/preliminary version of code to fetch fit files from XOSS G+ cyclo-computer, inspired by [f-xoss project](https://github.com/DCNick3/f-xoss).

This code is a modified version of [cycsync.py](https://github.com/Kaiserdragon2/CycSync) for Cycplus M2, which does not work for my use case as is.

This code was tested with XOSS G+, Win10 on Core-i5, TPLink USB BT dongle, py-3.8.6 and bleak-0.22.2.

TODO:
1. check successive block numbers for duplicates.
2. handling of fit-file data more efficiently on memory.
