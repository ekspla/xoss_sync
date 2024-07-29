# (c) 2024 ekspla.
# MIT License.  https://github.com/ekspla/xoss_sync
#
# A quick/preliminary version of code to fetch fit files from XOSS G+ cyclo-computer, inspired by f-xoss project 
# (https://github.com/DCNick3/f-xoss).
#
# This code is a modified version of cycsync.py (https://github.com/Kaiserdragon2/CycSync) for Cycplus M2.
#
# The main differences from Cycsync are:
# 1. additions of crc8_xor and crc16_arc to check the data.
# 2. check successive block numbers in YMODEM protocol.
# 3. check size of the retrieved file. 
# 4. use of slice assignment and memoryview in handling notification packets and blocks.
# 5. tested with XOSS G+ instead of Cycplus M2.
# 6. timings/delays were adjusted for my use case (XOSS G+, Micropython-1.23.0 on ESP32-WROOM-32E with SD card, and aioble).
#
# TODO:
# 1. handling of fit-file data more efficiently on memory.
# 2. some brush-up, esp. in handling notify packets from aioble.
# 3. still room to optimize timings/delays.

import sys

sys.path.append('')

import machine
import asyncio
import aioble
import bluetooth
import re
import os
import gc
from collections import deque


#_TARGET_NAME = "XOSS G-040989"
_TARGET_NAME = "XOSS"
_SERVICE_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
_CTL_CHARACTERISTIC_UUID = bluetooth.UUID("6e400004-b5a3-f393-e0a9-e50e24dcca9e")
_TX_CHARACTERISTIC_UUID = bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
_RX_CHARACTERISTIC_UUID = bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e")

VALUE_IDLE = bytearray([0x04, 0x00, 0x04]) # r(ead)/w(rite)
FILE_FETCH = bytearray([0x05]) # w
OK_FILE_FETCH = bytearray([0x06]) # r
#FILE_SEND = bytearray([0x07]) # w
#OK_FILE_SEND = bytearray([0x08]) # r 
VALUE_DISKSPACE = bytearray([0x09, 0x00, 0x09]) # w
OK_DISKSPACE = bytearray([0x0a]) # r
#FILE_DELETE = bytearray([0x0d]) # w
#OK_FILE_DELETE = bytearray([0x0e]) # r
#VALUE_STOP = bytearray([0x1f, 0x00, 0x1f]) # w
#VALUE_ERR_CMD = bytearray([0x11, 0x00, 0x11]) # r
#ERR_FILE_NA = bytearray([0x12]) # r
#VALUE_ERR_MEMORY = bytearray([0x13, 0x00, 0x13]) # r
#VALUE_ERR_NO_IDLE = bytearray([0x14, 0x00, 0x14]) # r
#ERR_FILE_PARSE = bytearray([0x15]) # r
VALUE_STATUS = bytearray([0xff, 0x00, 0xff]) # w

VALUE_SOH = bytearray([0x01])                             # SOH == 128-byte data
#VALUE_STX = bytearray([0x02])                             # STX == 1024-byte data
VALUE_C = bytearray([0x43])                               # 'C'
#VALUE_G = bytearray([0x47])                               # 'G'
VALUE_ACK = bytearray([0x06])                             # ACK
VALUE_NAK = bytearray([0x15])                             # NAK
VALUE_EOT = bytearray([0x04])                             # EOT
VALUE_CAN = bytearray([0x18])                             # CAN

AWAIT_NEW_DATA = bytearray(b'AwaitNewData')

class BluetoothFileTransfer:
    def __init__(self):
        #self.lock = asyncio.Lock()
        self.ctl_characteristic = None
        self.tx_characteristic = None
        self.rx_characteristic = None
        # **Packet**
        self.notification_data = bytearray()
        # **Block**
        self.is_block = False
        self.block_data_size = 128
        self.block_buf = bytearray(3 + self.block_data_size + 2)               # Header(SOH, num, ~num); data; CRC16
        self.block_num = 0 # Block number(0-255).
        self.idx_block_buf = 0 # Index in block_buf.
        self.mv_block_buf = memoryview(self.block_buf)
        self.block_data = self.mv_block_buf[3:-2]
        self.block_crc = self.mv_block_buf[-2:]
        self.block_error = False
        # **File**                                                               A file is made of blocks; a block is made of packets.
        self.data_size = 0
        self.data_written = 0
        self.filename = ''
        self.is_write_mode = False

    async def notify_handler(self):
        _EOT = bytes(VALUE_EOT)
        queue = self.tx_characteristic._notify_queue

        def append_to_block_buf(data):
            if (len_data := len(data)):
                self.block_buf[self.idx_block_buf:self.idx_block_buf + len_data] = data
                self.idx_block_buf += len_data

        while True:
            data = await self.tx_characteristic.notified()
            if data == _EOT:                                                         # Receive EOT.
                self.is_block = False
                self.notification_data[:] = data
            elif self.is_block:                                                     # Packets should be combined to make a block.
                await asyncio.sleep_ms(150)
                append_to_block_buf(data)
                while len(queue) >= 1:
                    append_to_block_buf(queue.popleft())
            else:
                self.notification_data[:] = data                                    # Other messages/responses.
            await asyncio.sleep(0)

    async def clear_notify_queue(self):
        queue = self.tx_characteristic._notify_queue
        await asyncio.sleep_ms(200)
        while len(queue) >= 1:
            _ = queue.popleft()

    async def discover_device(self, target_name):
        # Scan for 5 seconds, in active mode, with very low interval/window (to
        # maximise detection rate).
        ##async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async with aioble.scan(duration_ms=20_000, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                # See if it matches target_name.
                ##print(result.name(), result.device)
                if (name := result.name()) is not None and target_name in name:
                    print(f"Found target device: {name} - {result.device}")
                    return result.device

        print(f"Device with name {target_name} not found.")
        return None

    async def send_cmd(self, char, value, delay_ms):
        try:
            await char.write(value, False)
        except Exception as e:
            print(f"Failed to write value to characteristic: {e}")
        await asyncio.sleep_ms(delay_ms)

    async def get_idle_status(self):
        self.notification_data = AWAIT_NEW_DATA
        self.is_block = False
        await self.send_cmd(self.ctl_characteristic, VALUE_STATUS, 5_000)         # Send STATUS (0xff, 0x00, 0xff)
        await self.wait_until_data(self.ctl_characteristic)
        if self.notification_data == VALUE_IDLE:                                  # Receive IDLE (0x04, 0x00, 0x04)
            return True
        if self.notification_data == AWAIT_NEW_DATA:                              # Timeout; No response
            await self.send_cmd(self.ctl_characteristic, VALUE_IDLE, 100)         # Send IDLE (0x04, 0x00, 0x04)
            await self.wait_until_data(self.ctl_characteristic)
            if self.notification_data == VALUE_IDLE:                              # Receive IDLE (0x04, 0x00, 0x04)
                return True
        print(f'Error: {self.notification_data}')
        return False

    async def read_block_zero(self):
        self.block_num = -1
        self.idx_block_buf = 0
        self.is_block = True
        self.block_error = False
        await self.send_cmd(self.rx_characteristic, VALUE_C, 100)                     # Send 'C'.
        await self.read_block()

    async def read_block(self):
        async def check_block_buf(self):
            while self.idx_block_buf < 113: # 133 bytes - 1 packet * 20(MTU=23) = 113 bytes; c.f. 1+1+1+128+2=133 bytes (one block)
                await asyncio.sleep_ms(100)
            await asyncio.sleep_ms(100)
        try:
            await asyncio.wait_for(check_block_buf(self), timeout=10)
            if int.from_bytes(self.block_crc, 'big') != self.crc16_arc(self.block_data):
                self.block_error = True
            else:
                if self.is_write_mode:                                                    # Blocks should be combined to make a file.
                    if (self.data_written + self.block_data_size) <= self.data_size:
                        self.data_written += self.save_chunk_raw(self.block_data)
                    else:
                        mv_block_data = memoryview(self.block_data)
                        i = -1
                        while self.block_data[i] == 0x00: # Remove padded zeros at the end.
                            i -= 1
                        self.data_written += self.save_chunk_raw(mv_block_data[:i+1])
                if self.block_buf[1] == (self.block_num + 1) % 256:
                    if self.block_error: print(f'Fixed error in block{self.block_buf[1]}.')
                else:
                    print(f'Unexpected block: {self.block_num} -> {self.block_buf[1]}')
                self.block_num = self.block_buf[1]
                self.block_error = False
        except asyncio.TimeoutError:
            self.block_error = True
        # Prepare for the next data block.
        self.idx_block_buf = 0

    async def end_of_transfer(self):
        # The first EOT was received already.
        await asyncio.sleep_ms(100) # This avoids NAK to be sent too fast.
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(self.rx_characteristic, VALUE_NAK, 100) # Send NAK.
        await self.wait_until_data(self.tx_characteristic)                                   # Receive the second EOT.
        await asyncio.sleep_ms(100) # This avoids ACK to be sent too fast.
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(self.rx_characteristic, VALUE_ACK, 100) # Send ACK.
        await self.wait_until_data(self.ctl_characteristic)                                   # Receive IDLE (0x04, 0x00, 0x04)

    async def fetch_file(self, filename):
        if self.notification_data != VALUE_IDLE:
            if not await self.get_idle_status(): return
        # Request the File
        self.filename = filename
        self.notification_data = AWAIT_NEW_DATA
        value_file_fetch = self.make_command(FILE_FETCH, filename)
        await self.send_cmd(self.ctl_characteristic, value_file_fetch, 100)                   # Request starts with 0x05
        await self.wait_until_data(self.ctl_characteristic)

        if self.notification_data == self.make_command(OK_FILE_FETCH, filename):              # Response starts with 0x06
            self.is_write_mode = False                                                         # Do not write block 0
            notify_handler_task = asyncio.create_task(self.notify_handler())
            await asyncio.sleep(1)
            retries = 3
            while retries > 0:
                await self.read_block_zero() # Block 0 consists of name and size of the file.
                if self.block_error:
                    retries -= 1
                    await self.clear_notify_queue()
                    await self.send_cmd(self.rx_characteristic, VALUE_NAK, 100)               # Send NAK on error.
                else:
                    break
            if retries == 0: # Too many errors in reading block zero; cancel transport.
                await self.send_cmd(self.rx_characteristic, VALUE_CAN, 100)                   # Send CAN (cancel).
                notify_handler_task.cancel()
                return

            self.data_size = int(bytes(self.block_data).rstrip(b'\x00').decode('utf-8').split()[1])

            await self.send_cmd(self.rx_characteristic, VALUE_ACK, 100)                       # Send ACK.
            await self.send_cmd(self.rx_characteristic, VALUE_C, 100)                         # Send 'C'.

            # Blocks of num>=1 should be combined to obtain the file.
            self.is_write_mode = True
            self.data_written = 0
            while self.is_block:                                                              # Receive EOT to exit this loop.
                await self.read_block()
                if self.block_num % 128 == 0: gc.collect()
                if self.block_error:
                    await self.clear_notify_queue()
                    await self.send_cmd(self.rx_characteristic, VALUE_NAK, 100)              # Send NAK on error.
                else:
                    await self.send_cmd(self.rx_characteristic, VALUE_ACK, 100)              # Send ACK.
                await asyncio.sleep_ms(100)
            await self.end_of_transfer()
            notify_handler_task.cancel()
            if self.data_written != self.data_size:
                print(f"Error: {self.data_written}(file size) != {self.data_size}(spec)")
            else:
                print(f"Successfully wrote combined data to {filename}")
            gc.collect()

    async def wait_until_data(self, char):
        try:
            self.notification_data[:] = await char.notified(timeout_ms=10_000)
        except asyncio.TimeoutError:
                print(f"Something went wrong. No new notification data.")

    async def read_diskspace(self):
        # Read Diskspace; e.g. bytearray(b'\n556/8104\x1e')
        self.notification_data = AWAIT_NEW_DATA
        self.is_block = False
        await self.send_cmd(self.ctl_characteristic, VALUE_DISKSPACE, 100)                   # Request starts with 0x09
        await self.wait_until_data(self.ctl_characteristic)                                  # Response starts with 0x0a(b'\n')
        if (self.crc8_xor(self.notification_data) == 0 and 
            self.notification_data[0] == OK_DISKSPACE[0]):
            diskspace = self.notification_data[1:-1].decode('utf-8')
            print(f"Free Diskspace: {diskspace}kb")

    async def run(self):
        device = await self.discover_device(_TARGET_NAME)
        if not device:
            return

        try:
            connection = await device.connect(timeout_ms=80_000)
        except asyncio.TimeoutError:
            print(f"Failed to connect to {device}")
            return

        async with connection:
            print(f"Connected to {device}")
            await asyncio.sleep(5)
            service = await connection.service(_SERVICE_UUID)
            self.ctl_characteristic = await service.characteristic(_CTL_CHARACTERISTIC_UUID)
            self.tx_characteristic = await service.characteristic(_TX_CHARACTERISTIC_UUID)
            self.tx_characteristic._notify_queue = deque((), 6)
            self.rx_characteristic = await service.characteristic(_RX_CHARACTERISTIC_UUID)
            await self.ctl_characteristic.subscribe(notify=True)
            await self.tx_characteristic.subscribe(notify=True)
            print(f"Notifications started")

            await self.read_diskspace()

            if 'filelist.txt' in os.listdir('/sd'):
                os.rename('/sd/filelist.txt', '/sd/filelist.old')
            await self.fetch_file('filelist.txt')
            fit_files = self.extract_fit_filenames('/sd/filelist.txt')

            for fit_file in fit_files:
                if fit_file in os.listdir('/sd'):
                    print(f'Skip: {fit_file}')
                else:
                    print(f"Retrieving {fit_file}")
                    await self.fetch_file(fit_file)

    def extract_fit_filenames(self, file_path):
        fit_files = set()
        pattern = re.compile(r'\d+\.fit')

        try:
            with open(file_path, 'r') as file:
                lines = file.readlines()
                for line in lines:
                    match = pattern.search(line)
                    if match:
                        fit_files.add(match.group(0))
        except Exception as e:
            print(f"Failed to read/parse file: {e}")

        return fit_files

    def save_chunk_raw(self, data):
        with open(f'/sd/{self.filename}', 'ab') as f:
            return f.write(data)

    def crc8_xor(self, data):
        '''crc8/xor
        See make_command() how to use.
        '''
        crc = 0
        for x in data:
            crc ^= x
        return crc & 0xff

    def crc16_arc(self, data):
        '''crc16/arc
        XOSS uses CRC16/ARC instead of CRC16/XMODEM.
        '''
        crc = 0
        for x in data:
            crc ^= x
            for _ in range(8):
                if (crc & 0x0001) > 0:
                    crc = (crc >> 1) ^ 0xa001
                else:
                    crc = crc >> 1
        return crc & 0xffff

    def make_command(self, cmd, string=None):
        byte_array = cmd + bytearray(string.encode('utf-8') if string is not None else b'\x00') + bytearray([0x00])
        byte_array[-1] = self.crc8_xor(byte_array) # Replace the padded zero with crc8_xor.
        return byte_array


def start():
    if not "sd" in os.listdir():
        sdcard = machine.SDCard(slot=2, freq=20_000_000)
        try:
            os.mount(sdcard, "/sd")
        except:
            del sdcard
            print("No sdcard")
            sys.exit()

    transfer = BluetoothFileTransfer()
    try:
        asyncio.run(transfer.run())
    finally:
        asyncio.new_event_loop() # Clear retained state.
