# xoss_sync
Python (**CPython** and **MicroPython**) codes to fetch FIT files from **XOSS G+** cyclo-computer over bluetooth (BLE) for you.
The codes make you free from proprietary XOSS app/software on the cloud; you take full control of your gps track log files in FIT format.

(C) 2024-2025 [ekspla](https://github.com/ekspla/xoss_sync)

A quick/preliminary version of code to use with XOSS G+ GPS cyclo-computer, inspired by [f-xoss project](https://github.com/DCNick3/f-xoss). 
The code is a modified version of [cycsync.py](https://github.com/Kaiserdragon2/CycSync) for Cycplus M2, which does not work for my use case as is.

**The PC (CPython) version** (```xoss_sync.py```) was tested with XOSS G+ (Gen1), Windows10/11/Linux(BlueZ 5.56), TPLink USB BT dongle 
(UB400, v4.0, CSR8510 chip)/Intel Wireless (v5.1), Python-3.8.6/3.12.6 and Bleak-0.22.2.

**The MicroPython (MPY) version** (```mpy_xoss_sync.py```) was tested with MPY-1.23.0/1.24.0-preview on ESP32-WROOM-32E/ESP32-S3-WROOM-1, 
micro SD card, and aioble.  After a bit of modification (changes in the path to /sd), this code was also tested with a unix-port of MPY-1.23.0(+ 
[PR#14006](https://github.com/micropython/micropython/pull/14006))/aioble on the same PC-Linux-x64 and TPLink UB400.

## Features
These scripts allow you to:

- Obtain a list of data files on your device
- Download data (in FIT fromat) from your device
- See free/usage of storage in your device

## Usage (PC version)
1. Install bluetooth low energy interface/driver software on your PC.

2. Check if your device and the PC can be paired.

3. Install [Python](https://www.python.org/) (of course).

4. Install [Bleak](https://pypi.org/project/bleak/):

``` Shell
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

Though I tested this only with XOSS G+ (Gen1) and Windows10/11/Linux(BlueZ 5.56), combinations of the other XOSS device/OS may work. 
For the other devices such as Cycplus and CooSpo, you may have to change the ```TARGET_NAME``` appropriately.
[Bleak](https://github.com/hbldh/bleak) supports Android, MacOS, Windows, and Linux.

6. Change settings: 

Settings of the device \(e.g. timezone, backlight, autopause, etc.\) can be changed via JSON file. In my case \(XOSS-G+ gen1\), 

 a. Download the file.
``` Python
await self.fetch_file(client, 'Setting.json')
```
 b. Modify the file.

 c. Upload the modified file.
``` Python
await self.send_file(client, 'Setting.json')
```
After the successful upload, you hear a short beep from the device. 


## Usage (MicroPython version)
1. Install SD card/interface on your ESP32 board.

2. Install [MicroPython](https://micropython.org/) (of course).

3. Install [aioble](https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble):

``` Shell
mpremote mip install aioble
```

4. Download/install and run the script 

``` python
>>> import mpy_xoss_sync
>>> mpy_xoss_sync.start()
```

Though it works very well as PC version, this is an ad hoc implementation to MPY/aioble. 
The code was also tested with MPY-1.24.0-preview/aioble on ESP32-S3 and with unix-port of MPY-1.23.0/aioble on PC-Linux-x64 (Core-i5).

For the other devices such as Cycplus and CooSpo, you may have to change the ```_TARGET_NAME``` appropriately.

5. Optional

Throughput (see Note 3) can be increased by specifying the optional connection parameters of *scan_duration_ms*, *min_conn_interval_us* and 
*max_conn_interval_us* [as described here.](https://github.com/micropython/micropython/issues/15418)  These intervals can be reduced to the 
minimum value of 7_500 (7.5 ms) on ESP32-S3 and on PC-Linux-x64 using unix port.

Modify ```async def _connect()``` in aioble/central.py:
``` Diff
-           ble.gap_connect(device.addr_type, device.addr)
+           ble.gap_connect(device.addr_type, device.addr, 5_000, 11_500, 11_500)
```

Alternatively, if you have installed the latest aioble after 
[commit 68e3e07](https://github.com/micropython/micropython-lib/commit/68e3e07bc7ab63931cead3854b2a114e9a084248), 

modify ```async def run()``` in mpy_xoss_sync.py:
``` Diff
-               connection = await device.connect(timeout_ms=60_000)
+               connection = await device.connect(timeout_ms=60_000, scan_duration_ms=5_000, min_conn_interval_us=11_500, max_conn_interval_us=11_500)
```

Update(MAR2025): the default connection interval has been changed to 7_500 micro sec.  If you have installed aioble prior to 
[the commit 68e3e07](https://github.com/micropython/micropython-lib/commit/68e3e07bc7ab63931cead3854b2a114e9a084248), 
modify the cord appropriately.


~~The look-up-table (256 elements) with Viper implementation of CRC16/ARC used in this version may be overkill.~~ 
For those working together with web client/server in memory constrained systems, I would suggest using ~~either~~ 
the ordinary one (as shown in the CPython version) ~~or~~ 
~~[LUT with index-width of four bits \(16 elements\)](https://github.com/ekspla/xoss_sync/blob/main/reference/crc16_arc_table.py)~~.

## Limitation
The scripts work perfectly for my use case as shown above, but there are possible limitations due mainly to the implementation
of YMODEM in part as followings.

- The script expects a transport with ~~MTU of 23, 128-byte data per block, and~~ CRC16/ARC (not CRC16/XMODEM).  I am not sure
if the SoC(seems to be nRF52832)/software in the XOSS device supports larger MTU or 1024-byte data in YMODEM (see, Notes 1 & 2).

- Update(FEB 2025):  1024-byte data block (STX) in YMODEM is now supposed to work only in CPython version, though it's not well tested.
If you can control MTU size, 206 which is used in [f-xoss project](https://github.com/DCNick3/f-xoss) 
\(see below\) may be a good number because an STX block of 1029 bytes in YMODEM fits quite well in 
1030 = mtu*5.

- Update(MAR 2025):  1024-byte data block (STX) in YMODEM is now supposed to work also in MicroPython version, though it's not well tested.

## Notes
1. My XOSS-G+ (Gen1) was found to be not changing MTU(23)/block data size(128) with Win11 and Bluetooth 5.1 interface, which always 
requests MTU of 527, while [f-xoss project](https://github.com/DCNick3/f-xoss) for XOSS-NAV used MTU of 206.

2. The proprietary XOSS App on mobile phone itself seems to support larger MTU/block data size by DLE (data length extension) and STX. 
See, for example [this Xingzhe's web site](https://developer.imxingzhe.com/docs/device/tracking_data_service/).

3. Sync times (throughputs in parentheses) using my FIT file of 235,723 bytes were as followings (as of 31 OCT 2024). 
The connection intervals were measured by using 
[nRF Sniffer for BLE](https://www.nordicsemi.com/Products/Development-tools/nRF-Sniffer-for-Bluetooth-LE/Download) (nRF52840 dongle) and 
[Wireshark](https://www.wireshark.org/download.html).
- Proprietary XOSS App
    - Android-x86 and TPLink UB400, 00:07:27 (4.2 kbps).
       - 50.0 ms connection interval (measured); this could not be changed (see Note 4).
- CPython/Bleak version
    - Windows10 and TPLink UB400, 00:03:45 (8.4 kbps).
       - 15.0 ms connection interval (measured).
    - Windows11 and Intel Wireless, 00:08:41 (3.6 kbps).
       - 60.0 ms connection interval (measured).
    - Linux (BlueZ 5.56) and TPLink UB400, 00:07:08 (4.4 kbps).
       - 50.0 ms connection interval (measured).
- MPY/aioble version (hereafter: ESP32 = ESP32-WROOM-32E; ESP32-S3 = ESP32-S3-WROOM-1-N16R8; MPY-Linux = unix-port on PC-Linux-x64/TPLink UB400)
    - ESP32/aioble, 00:07:11 (4.4 kbps).
       - 50.0 ms connection interval (measured).
    - ESP32/modified aioble(conn_intervals=11.5 ms), 00:04:04 (7.7 kbps).
       - 11.25 ms connection interval (measured).
    - ESP32-S3/modified aioble(conn_intervals=11.5 ms), 00:03:46 (8.3 kbps).
    - ESP32-S3/modified aioble(conn_intervals=7.5 ms), reduced NAK/ACK delays and no explicit garbage-collection (GC), 00:02:42 (11.6 kbps).
       - Further optimization requires [a modified firmware with increased tick-rate in FreeRTOS](https://github.com/orgs/micropython/discussions/15594)
; change ```CONFIG_FREERTOS_HZ``` from default value of 100 Hz \[10 ms\] to 1000 Hz \[1 ms\].
    - ESP32-S3(```CONFIG_FREERTOS_HZ=1000```)/modified aioble(conn_intervals=7.5 ms), optimized delays and no GC, 00:02:05 (15.0 kbps).
       - 7.5 ms connection interval (measured).
       - While the client (mpy_xoss_sync.py) using ```_thread``` in ```file.write()``` improves a little, 00:02:00 (15.7 kbps), **the throughput is 
determined by the unresponsive peripheral** to the ACKs in YMODEM (i.e. no packets sent from XOSS-G+).  **Typically, 2-4 ACKs 
(using 2-4 connection events) are necessary irrespective of connection intervals**.  The theoretical limit of 3 connections/block, as shown below, 
does not occur because of the unresponsiveness.  See example sniffer logs of 
[7.5](https://github.com/ekspla/xoss_sync/blob/main/reference/conn_intvl_7r5ms.png) 
and [50 ms](https://github.com/ekspla/xoss_sync/blob/main/reference/conn_intvl_50ms.png) for details.  This strange issue, irrespective of 
the intervals, may be caused by [Nordic's SoftDevice](https://www.nordicsemi.com/products/nrf52832/) in XOSS-G+.
    - MPY-Linux/modified aioble(conn_intervals=7.5 ms), optimized delays and no GC, 00:02:25 (13.0 kbps).
       - 7.5 ms connection interval (measured).
       - The throughput was a bit less than those of ESP32-S3, probably because of the difference in bluetooth stacks; 
[BTstack](https://github.com/bluekitchen/btstack) vs. [NimBLE](https://github.com/apache/mynewt-nimble).  Prior to the YMODEM-ACK an unnecessary 
empty packet is always sent from BTstack to XOSS-G+, while this is not the case in ESP32s (using NimBLE).
    - Using [a pair of test codes](https://github.com/ekspla/micropython_aioble_examples) (```nus_modem_server.py```, ```nus_modem_client.py```): 
MPY-Linux (server) --> ESP32-S3 (client), 00:01:08 (27.7 kbps).
       - 7.5 ms connection interval (measured).
       - The throughput was significantly faster 
[without the strange unresponsive delays caused by XOSS-G+](https://github.com/ekspla/xoss_sync/blob/main/reference/test_code_pair_7r5ms.png).

(c.f.)
Theoretical limit using 11.5 ms connection interval on MPY/aioble:

1 s / 11.5 ms = 87 connections; 1 connection = 6 packets * 20 bytes (mtu=23);
so, 133 bytes (data/block \[128\], header \[3\] and CRC \[2\]) == 2 connections + 1 connection for ACK in YMODEM.
(The 6-packet limit in XOSS-G+ is, probably, required for compatibility to very old mobile phones.)

87 connections/s * (128 data bytes / 3 connections) * 8 bits/byte = 29.7 kbps \[this would be 45.5 kbps for 7.5 ms interval\].


On Win11, the limits are 1.9, 5.7 and 22.8 kbps for *PowerOptimized* (180 ms), *Balanced* (60 ms) and *ThroughputOptimized* (15 ms) BLE settings, 
respectively.  There is no API in Bleak on Windows to change this setting though.  The measured throughput of 3.6 kbps on Win11 using 
Intel Wireless adapter (as shown above) suggests *Balanced* setting, which agrees well with those of the measured value using the sniffer.
On Linux, the min/max connection intervals may be specified by the user (see below).

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

5. LE 2M PHY support of XOSS-G+.

Although my XOSS-G+ shows `LE_2M_PHY = True` (BLE 5.0) in the feature response packet, [it stops communication silently and starts advertising again 
after receiving a `LL_PHYS_REQ (preference of 2M PHY)` packet](https://github.com/ekspla/xoss_sync/blob/main/reference/Test_LL_PHYS_REQ.png). 
It seems that the client's request of changing from 1M to 2M is not handled appropriately in the XOSS-G+ software as specified in the Bluetooth Core 
Spec. This is similar to the case of unfunctional `Data Length Extension (DLE) = True` (BLE 4.2) as described in Notes 1 & 2. 

I am not sure if these problems are solved in the latest models.

## Appendix
[A DIY Battery Replacement](https://github.com/ekspla/xoss_sync/blob/main/reference/batt_replacement.md)
