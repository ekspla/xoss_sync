# xoss_sync
Python (**CPython** and **Micropython**) codes to fetch FIT files from **XOSS G+** cyclo-computer over bluetooth (BLE) for you.

(C) 2024 [ekspla](https://github.com/ekspla/xoss_sync)

A quick/preliminary version of code to use with XOSS G+ GPS cyclo-computer, inspired by [f-xoss project](https://github.com/DCNick3/f-xoss).

The code is a modified version of [cycsync.py](https://github.com/Kaiserdragon2/CycSync) for Cycplus M2, which does not work for my use case as is.

**The PC version** (```xoss_sync.py```) was tested with XOSS G+ (Gen1), Windows10 on Core-i5, TPLink USB BT dongle (UB400, v4.0, CSR8510 chip), Python-3.8.6 and Bleak-0.22.2 
while **the Micropython (MPY) version** (```mpy_xoss_sync.py```) with MPY-1.23.0 on ESP32-WROOM-32E, SD card, and aioble.

## Features
This script allows you to:

- Obtain a list of data files on your device
- Download data (in FIT fromat) from your device
- See free/usage of storage in your device

## Usage (PC version)
1. Install bluetooth low energy interface/driver software on your PC.

2. Check if your device and the PC are paired.

3. Install [python](https://www.python.org/) (of course).

4. Install [bleak](https://pypi.org/project/bleak/):

```
pip install bleak
```

5. Download and run the script ```python xoss_sync.py```:

```
D:\backup\Bicycle\XOSS\python>python xoss_sync.py
Scanning for Bluetooth devices...
Found device: XOSS G-040989 - EC:37:9F:xx:yy:zz
Found target device: XOSS G-040989 - EC:37:9F:xx:yy:zz
Connected to XOSS G-040989
Notifications started
Free Diskspace: 684/8104kb
Successfully wrote combined data to filelist.txt
Skip: 20240713062144.fit
Skip: 20240609141047.fit
Skip: 20240504063456.fit
Skip: 20240525060956.fit
Skip: 20240511055922.fit
Skip: 20240609130215.fit
Skip: 20240608063049.fit
Skip: 20240615062615.fit
Retrieving 20240715062336.fit
Successfully wrote combined data to 20240715062336.fit
Skip: 20240420055014.fit
Skip: 20240427061131.fit
Skip: 20240502061739.fit
Skip: 20240518060936.fit
Skip: 20240707055411.fit
Skip: 20240429060242.fit
Skip: 20240622055813.fit
Skip: 20240629073413.fit
Skip: 20240506053748.fit
Skip: 20240706062605.fit
Skip: 20240601060515.fit

D:\backup\Bicycle\XOSS\python>
```

Though I tested this only with XOSS G+ (Gen1) and Windows10 & 11, combinations of the other XOSS device/OS might work.
C.f. [Bleak](https://github.com/hbldh/bleak) supports Android, MacOS, Windows, and Linux.


## Usage (Micropython version)
1. Install SD card/interface on your ESP32 board.

2. Install [Micropython](https://micropython.org/) (of course).

3. Install [aioble](https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble):

```
mpremote mip install aioble
```

4. Download/install and run the script 

``` python
>>> import mpy_xoss_sync
>>> mpy_xoss_sync.start()
```

Though it works very well as PC version, this is an ad hoc implementation to MPY/aioble. 

Throughput (see Note 3) can be increased by specifying the optional connection parameters of *scan_duration_ms*, *min_conn_interval_us* and 
*max_conn_interval_us* [as described here.](https://github.com/micropython/micropython/issues/15418)  These intervals can be reduced to the 
minimum value of 7_500 (7.5 ms) on ESP32-S3, although I am not sure about the real connection interval.

Modify ```async def _connect()``` in aioble/central.py:
``` Diff
-           ble.gap_connect(device.addr_type, device.addr)
+           ble.gap_connect(device.addr_type, device.addr, 5_000, 11_500, 11_500)
```
With the short intervals, you might have to add a short ```sleep_ms``` before reading the notification queue as following.

Modify  ```async def _notified_indicated()``` in aioble/client.py:
``` Diff
        # Either we started > 1 item, or the wait completed successfully, return
        # the front of the queue.
+       await asyncio.sleep_ms(5)
        return queue.popleft()
```
The code was also tested with MPY-1.24.0-preview/aioble on ESP32-S3-WROOM-1-N16R8 (see Note 3).

## Limitation
The script seems to work perfectly for my use case as shown above, but there are possible limitations due mainly to the implementation
of YMODEM in part as followings.

- The script expects a transport with MTU of 23, 128-byte data per block, and CRC16/ARC (not CRC16/XMODEM).  I am not sure
if the SoC(seems to be nRF52832)/software in the XOSS device supports larger MTU or 1024-byte data in YMODEM (see, Notes 1 & 2).

## Notes
1. My XOSS-G+ (Gen1) was found to be not changing MTU(23)/block size(128) with Win11 and Bluetooth 5.1 interface, which always 
requests MTU of 525, while [f-xoss project](https://github.com/DCNick3/f-xoss) for XOSS-NAV used MTU of 206.

2. The proprietary XOSS App on mobile phone itself seems to support larger MTU/block size by DLE (data length extension) and STX.  See, 
for example [this Xingzhe's web site](https://developer.imxingzhe.com/docs/device/tracking_data_service/).

3. Sync times using my FIT file of 235,723 bytes were as followings (as of 4 SEP 2024).
   - Proprietary XOSS App using Android-x86 and TPLink UB400, 00:07:27 (4.2 kbps). Connection interval could not be changed (see Note 4).
   - PC/Bleak version using Windows10 and TPLink UB400, 00:03:45 (8.4 kbps).
   - PC/Bleak version using Windows11 and Intel wireless, 00:08:41 (3.6 kbps).
   - MPY/aioble version using MPY-1.23.0 on ESP32-WROOM-32E, 00:07:11 (4.4 kbps).
   - MPY/aioble with 11.5 ms conn_intervals on ESP32, 00:04:04 (7.7 kbps).
   - MPY/aioble with 11.5 ms conn_intervals on ESP32-S3, 00:03:46 (8.3 kbps).
   - MPY/aioble with 7.5 ms conn_intervals, reduced ACK delays and no garbage-collection on ESP32-S3, 00:02:42 (11.6 kbps). Further 
optimization may require [a modified firmware with increased tick-rate in FreeRTOS](https://github.com/orgs/micropython/discussions/15594)
; ```CONFIG_FREERTOS_HZ=1000```.

(c.f.)
Theoretical limit using 11.5 ms connection interval on MPY/ESP32:

1 s / 11.5 ms = 87 connections; 1 connection = 6 packets * 20 bytes (mtu=23);
so, 128 bytes (1 block) == 2 connections + 1 connection for ACK.

87 connections/s * (128 bytes / 3 connections) * 8 bits/byte = 29.7 kbps.


On Win11, the limits are 1.9, 5.7 and 22.8 kbps for PowerOptimized (180 ms), Balanced (60 ms) and ThroughputOptimized (15 ms) BLE settings, 
respectively.  There is no API in Bleak on Windows to change this setting though.  The measured throughput of 3.6 kbps on Win11 using 
Intel wireless adaptor (as shown above) suggests Balanced setting.
On Linux, the min/max connection intervals might be specified by the user (see below).

4. Conn_min_interval/conn_max_interval on Linux kernels.

Unfortunately, changing the parameters did not work for the XOSS App/Android-x86 in my case.
``` ShellSession
x86:/ $ su
x86:/ # cat /sys/kernel/debug/bluetooth/hci0/conn_min_interval
40                                                                      # 40 * 1.25  = 50 ms
x86:/ # cat /sys/kernel/debug/bluetooth/hci0/conn_max_interval
56                                                                      # 56 * 1.25 = 70 ms
x86:/ # echo 9 > /sys/kernel/debug/bluetooth/hci0/conn_min_interval     # 9 * 1.25 = 11.25 ms
x86:/ # echo 20 > /sys/kernel/debug/bluetooth/hci0/conn_max_interval    # 20 * 1.25 = 25 ms
```
