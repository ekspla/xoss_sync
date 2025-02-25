﻿#!/usr/bin/env python
#coding:utf-8
#
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
# 6. timings/delays were adjusted for my use case (XOSS G+, Win10 on Core-i5, TPLink UB400 BT dongle, py-3.8.6 and bleak-0.22.2).
#
# TODO:
# 1. handling of fit-file data more efficiently on memory.

import asyncio
from bleak import BleakScanner, BleakClient
import re
import os
import datetime

#TARGET_NAME = "XOSS G-040989"
TARGET_NAME = "XOSS"
#SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
CTL_CHARACTERISTIC_UUID = "6e400004-b5a3-f393-e0a9-e50e24dcca9e"
TX_CHARACTERISTIC_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
RX_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

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
TIME_SET = bytearray([0x54]) # w
OK_TIME_SET = bytearray([0x55]) # r
VALUE_STATUS = bytearray([0xff, 0x00, 0xff]) # w

VALUE_SOH = bytearray([0x01])                             # SOH == 128-byte data
VALUE_STX = bytearray([0x02])                             # STX == 1024-byte data
VALUE_C = bytearray([0x43])                               # 'C'
#VALUE_G = bytearray([0x47])                               # 'G'
VALUE_ACK = bytearray([0x06])                             # ACK
VALUE_NAK = bytearray([0x15])                             # NAK
VALUE_EOT = bytearray([0x04])                             # EOT
VALUE_CAN = bytearray([0x18])                             # CAN

AWAIT_NEW_DATA = bytearray(b'AwaitNewData')

class BluetoothFileTransfer:
    def __init__(self):
        self.lock = asyncio.Lock()
        # **Packet**
        self.notification_data = bytearray()
        # **Block**
        self.is_block = False
        self.block_buf = bytearray(3 + 1024 + 2)                                 # Header(SOH, num, ~num); data(128 or 1024 bytes); CRC16
        self.block_num = 0 # Block number(0-255).
        self.idx_block_buf = 0 # Index in block_buf.
        self.mv_block_buf = memoryview(self.block_buf)
        ##self.block_size = None
        self.block_data = None
        self.block_crc = None
        self.block_size_data_crc = (
            (3 + 128 + 2, self.mv_block_buf[3:131], self.mv_block_buf[131:133], ), # SOH
            (3 + 1024 + 2, self.mv_block_buf[3:-2], self.mv_block_buf[-2:], ),     # STX
        )
        self.block_error = False
        # **File**                                                               A file is made of blocks; a block is made of packets.
        self.data = bytearray()
        self.data_size = 0

    def create_notification_handler(self):
        async def notification_handler(sender, data):
            ##print(data) # For test.
            if data == VALUE_EOT:                                               # Receive EOT.
                self.is_block = False
                self.notification_data = data
            elif self.is_block:                                                 # Packets should be combined to make a block.
                async with self.lock: # Use asyncio.Lock() for safety.
                    self.mv_block_buf[self.idx_block_buf:self.idx_block_buf + (len_data := len(data))] = data
                    self.idx_block_buf += len_data
            else:
                self.notification_data = data                                   # Other messages/responses.

        return notification_handler

    async def discover_device(self, target_name):
        print("Scanning for Bluetooth devices...")
        retries = 3
        while retries > 0:
            devices = await BleakScanner.discover(timeout=30.0)

            for device in devices:
                print(f"Found device: {device.name} - {device.address}")
                if device.name is not None and target_name in device.name:
                    print(f"Found target device: {device.name} - {device.address}")
                    return device
            retries -= 1

        print(f"Device with name {target_name} not found.")
        return None

    async def start_notify(self, client, uuid):
        try:
            await client.start_notify(uuid, self.create_notification_handler())
        except Exception as e:
            print(f"Failed to start notifications: {e}")

    async def send_cmd(self, client, uuid, value, delay):
        try:
            await client.write_gatt_char(uuid, value, False)
        except Exception as e:
            print(f"Failed to write value to characteristic: {e}")
        await asyncio.sleep(delay)

    async def get_idle_status(self, client):
        self.notification_data = AWAIT_NEW_DATA
        self.is_block = False
        await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, VALUE_STATUS, 5.0)  # Send STATUS (0xff, 0x00, 0xff)
        await self.wait_until_data(client)
        if self.notification_data == VALUE_IDLE:                                  # Receive IDLE (0x04, 0x00, 0x04)
            return True
        if self.notification_data == AWAIT_NEW_DATA:                              # Timeout; No response
            await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, VALUE_IDLE, 0.1) # Send IDLE (0x04, 0x00, 0x04)
            await self.wait_until_data(client)
            if self.notification_data == VALUE_IDLE:                              # Receive IDLE (0x04, 0x00, 0x04)
                return True
        print(f'Error: {self.notification_data}')
        return False

    async def read_block_zero(self, client):
        self.block_num = -1
        self.idx_block_buf = 0
        self.is_block = True
        self.block_error = False
        await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_C, 0.1)      # Send 'C'.
        await self.read_block(client)

    async def read_block(self, client):
        #_SOH = VALUE_SOH[0] # SOH == 128-byte data
        _STX = VALUE_STX[0] # STX == 1024-byte data
        async def check_block_buf():
            while self.idx_block_buf == 0:
                await asyncio.sleep(0.01)
            if not self.is_block: return
            block_size, self.block_data, self.block_crc = self.block_size_data_crc[int(self_block_buf[0] == _STX)]
            while self.idx_block_buf < block_size:
                await asyncio.sleep(0.01)

        try:
            await asyncio.wait_for(check_block_buf(), timeout=10)
            if not self.is_block: return # The 1st EOT may arrive very late.
            if int.from_bytes(self.block_crc, 'big') != self.crc16_arc(self.block_data):
                self.block_error = True
            else:
                self.data.extend(self.block_data)                                # Blocks should be combined to make a file.
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

    async def end_of_transfer(self, client):
        # The first EOT was received already.
        await asyncio.sleep(0.1) # This avoids NAK to be sent too fast.
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_NAK, 0.1) # Send NAK.
        await self.wait_until_data(client)                                   # Receive the second EOT.
        await asyncio.sleep(0.1) # This avoids ACK to be sent too fast.
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_ACK, 0.1) # Send ACK.
        await self.wait_until_data(client)                                   # Receive IDLE (0x04, 0x00, 0x04)

    async def fetch_file(self, client, filename):
        if self.notification_data != VALUE_IDLE:
            if not await self.get_idle_status(client): return
        # Request the File
        self.notification_data = AWAIT_NEW_DATA
        value_file_fetch = self.make_command(FILE_FETCH, filename)
        await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, value_file_fetch, 0.1) # Request starts with 0x05
        await self.wait_until_data(client)

        if self.notification_data == self.make_command(OK_FILE_FETCH, filename):    # Response starts with 0x06
            retries = 3
            while retries > 0:
                await self.read_block_zero(client) # Block 0 consists of name and size of the file.
                if self.block_error:
                    retries -= 1
                    self.is_block = False # Wait 0.2 s for garbage.
                    await asyncio.sleep(0.2)
                    self.is_block = True
                    await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_NAK, 0.1) # Send NAK on error.
                else:
                    break
            if retries == 0: # Too many errors in reading block zero; cancel transport.
                await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_CAN, 0.1)    # Send CAN (cancel).
                return

            self.data_size = int(self.block_data.tobytes().rstrip(b'\x00').decode('utf-8').split()[1])
            self.data = bytearray() # Where the file to be stored.

            await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_ACK, 0.1)       # Send ACK.
            await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_C, 0.1)         # Send 'C'.

            # Blocks of num>=1 should be combined to obtain the file.
            while self.is_block:                                                       # Receive EOT to exit this loop.
                await self.read_block(client)
                if not self.is_block: break # The 1st EOT may arrive very late.
                if self.block_error:
                    self.is_block = False # Wait 0.2 s for garbage.
                    await asyncio.sleep(0.2)
                    self.is_block = True
                    await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_NAK, 0.1) # Send NAK on error.
                else:
                    await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_ACK, 0.1) # Send ACK.
            await self.end_of_transfer(client)
            self.save_file_raw(filename)

    async def wait_until_data(self, client):
        i = 0
        while self.notification_data == AWAIT_NEW_DATA:
            await asyncio.sleep(0.01)
            i = i + 1
            if i >= 1000:
                print(f"Something went wrong. No new notification data.")
                break

    async def read_diskspace(self, client):
        # Read Diskspace; e.g. bytearray(b'\n556/8104\x1e')
        self.notification_data = AWAIT_NEW_DATA
        self.is_block = False
        await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, VALUE_DISKSPACE, 0.1)      # Request starts with 0x09
        await self.wait_until_data(client)                                              # Response starts with 0x0a(b'\n')
        if (self.crc8_xor(self.notification_data) == 0 and 
            self.notification_data.startswith(OK_DISKSPACE)):
            diskspace = self.notification_data[1:-1].decode('utf-8')
            print(f"Free Diskspace: {diskspace}kb")

    async def time_set(self, client):
        # Set RTC on the device (32-bit uint, UTC, and 1970/1/1 epoch)
        self.notification_data = AWAIT_NEW_DATA
        self.is_block = False
        value_time_set = (TIME_SET
            + bytearray(int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp()).to_bytes(4, 'little'))
            + bytearray([0x00]))
        value_time_set[-1] = self.crc8_xor(value_time_set)
        await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, value_time_set, 0.1)      # Request starts with 0x54
        #await self.wait_until_data(client)                                             # Response starts with 0x55
        await asyncio.sleep(1) # Wait 1 sec because of no response from XOSS-G+ gen1.

    async def run(self):
        device = await self.discover_device(TARGET_NAME)
        if not device:
            return

        async with BleakClient(device.address, timeout=60.0) as client:
            if client.is_connected:
                print(f"Connected to {device.name}")
                ##print(f"MTU {client.mtu_size}")

                await self.start_notify(client, CTL_CHARACTERISTIC_UUID)
                await self.start_notify(client, TX_CHARACTERISTIC_UUID)
                print(f"Notifications started")

                #await self.time_set(client)
                await self.read_diskspace(client)

                await self.fetch_file(client, 'filelist.txt')
                fit_files = self.extract_fit_filenames('filelist.txt')

                for fit_file in fit_files:
                    if os.path.exists(fit_file):
                        print(f'Skip: {fit_file}')
                    else:
                        print(f"Retrieving {fit_file}")
                        await self.fetch_file(client, fit_file)

                await client.stop_notify(CTL_CHARACTERISTIC_UUID)
                await client.stop_notify(TX_CHARACTERISTIC_UUID)
            else:
                print(f"Failed to connect to {device.name}")

    def extract_fit_filenames(self, file_path):
        fit_files = set()
        pattern = re.compile(r'\d{14}\.fit')

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

    def save_file_raw(self, filename):
        mv_file_data = memoryview(self.data)
        i = -1
        while self.data[i] == 0x00: # Remove padded zeros at the end.
            i -= 1

        with open(filename, "wb") as file:
            size = file.write(mv_file_data[:i+1] if i < -1 else self.data)
        if size != self.data_size:
            print(f"Error: {size}(file size) != {self.data_size}(spec)")
        else:
            print(f"Successfully wrote combined data to {filename}")

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


if __name__ == "__main__":
    transfer = BluetoothFileTransfer()
    try:
        asyncio.run(transfer.run())
    finally:
        asyncio.new_event_loop() # Clear retained state.
