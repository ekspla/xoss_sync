# (c) 2024 ekspla.
# MIT License.  https://github.com/ekspla/xoss_sync
#
# A quick/preliminary version of code to fetch fit files from XOSS G+ cyclo-computer, inspired by f-xoss project 
# (https://github.com/DCNick3/f-xoss).
#
# This code is a modified version of cycsync.py (https://github.com/Kaiserdragon2/CycSync) for Cycplus M2.
#
# The main differences from Cycsync are:
# 1. additions of crc_xor8 and crc16_arc to check the data.
# 2. use of memoryview in handling notification packets (to form a block in YMODEM protocol).
# 3. tested with XOSS G+ instead of Cycplus M2.
# 4. timings/delays were adjusted for my use case (XOSS G+, Win10 on Core-i5, TPLink USB BT dongle, py-3.8.6 and bleak-0.22.2).
#
# TODO:
# 1. send NACK on error, to request the correct data block once again.
# 2. handling of fit-file data more efficiently on memory.

import asyncio
from bleak import BleakScanner, BleakClient
import re
import sys
import os

#TARGET_NAME = "XOSS G-040989"
TARGET_NAME = "XOSS"
#SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
CTL_CHARACTERISTIC_UUID = "6e400004-b5a3-f393-e0a9-e50e24dcca9e"
TX_CHARACTERISTIC_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
RX_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

VALUE_DISKSPACE = bytearray([0x09, 0x00, 0x09])
VALUE_READ = bytearray([0xff, 0x00, 0xff])
VALUE_SOH = bytearray([0x01])                             # SOH == 128-byte data
#VALUE_STX = bytearray([0x02])                             # STX == 1024-byte data
VALUE_C = bytearray([0x43])                               # 'C'
#VALUE_G = bytearray([0x47])                               # 'G'
VALUE_ACK = bytearray([0x06])                             # ACK
VALUE_NAK = bytearray([0x15])                             # NAK
VALUE_EOT = bytearray([0x04])                             # EOT
#VALUE_CAN = bytearray([0x18])                             # CAN

AWAIT_NEW_DATA = bytearray([0x41, 0x77, 0x61, 0x69, 0x74, 0x4E, 0x65, 0x77, 0x44, 0x61, 0x74, 0x61]) # 'AwaitNewData'

class BluetoothFileTransfer:
    def __init__(self):
        self.data = bytearray()
        self.count = 0
        self.notification_data = bytearray()
        self.is_block = False
        self.block_buf = bytearray(3 + 128 + 2)
        self.idx_block = 0
        self.mv_block_buf = memoryview(self.block_buf)
        self.block_data = self.mv_block_buf[3:-2]
        self.block_crc = self.mv_block_buf[-2:]

    def create_notification_handler(self):
        async def notification_handler(sender, data):
            ##print(data) # For test.

            if data == VALUE_EOT:  # Receive EOT.
                self.count = 6
                self.idx_block = 0
                self.is_block = False
                self.notification_data = data
            elif self.is_block:
                self.block_buf[self.idx_block:self.idx_block + (len_data := len(data))] = data
                self.idx_block += len_data
                self.count += 1
            else:
                self.notification_data = data

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

    async def request_read_file(self, client):
        self.notification_data = AWAIT_NEW_DATA
        self.is_block = False
        await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, VALUE_READ, 5.0)
        await self.wait_until_data(client)

    async def read_block_zero(self, client):
        self.count = 0
        self.idx_block = 0
        self.is_block = True
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_C, 0.1)
        while self.count <= 5:
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.1)
        if (crc := int.from_bytes(self.block_crc, 'big')) != (calc_crc := self.crc16_arc(self.block_data)):
            print('Error in block 0.')

    async def read_blocks_combine(self, client):
        while self.count <= 5:                                              # 23(MTU) * 6(packets) = 138 bytes; c.f. 1+1+1+128+2=133 bytes (block)
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.1)
        # Prepare for the next data block.
        self.idx_block = 0
        self.count = 0

        if (crc := int.from_bytes(self.block_crc, 'big')) != (calc_crc := self.crc16_arc(self.block_data)):
            print(f'Error in block {self.block_buf[1]}.')

        self.data.extend(self.block_data)                                   # Omit headers and CRC16.

    async def end_of_transfer(self, client):
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_NAK, 0.1) # Send NAK.
        await self.wait_until_data(client)                                   # Receive EOT.
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_ACK, 0.1) # Send ACK.
        await self.wait_until_data(client)

    # Function to fetch a file
    async def fetch_file(self, client, filename):
        # Request Read Permission
        await self.request_read_file(client)
        # Request the File
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, self.request_array(filename), 0.1)

        await self.wait_until_data(client)

        if self.crc_xor8(self.notification_data) == 0: # bytearray(0x06, filename, crc_xor8)
            await self.read_block_zero(client)

            self.count = 0
            self.idx_block = 0
            self.is_block = True
            self.data = bytearray()

            await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_ACK, 0.1) # Send ACK.
            await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_C, 0.1) # Send 'C'.

            while self.is_block:                                              # Receive EOT to exit this loop.
                await self.read_blocks_combine(client)
                await self.send_cmd(client, RX_CHARACTERISTIC_UUID, VALUE_ACK, 0.1) # Send ACK.
            await self.end_of_transfer(client)
            self.save_file_raw(filename, self.data)

    async def wait_until_data(self, client):
        i=0
        while self.notification_data == AWAIT_NEW_DATA:
            await asyncio.sleep(0.01)
            i = i+1
            if i>=1000:
                print(f"Something went wrong No new notification data")
                break

    async def read_diskspace(self, client):
        # Read Diskspace; e.g. bytearray(b'\n556/8104\x1e')
        self.notification_data = AWAIT_NEW_DATA
        await self.send_cmd(client, CTL_CHARACTERISTIC_UUID, VALUE_DISKSPACE, 0.1)
        await self.wait_until_data(client)
        if self.crc_xor8(self.notification_data) == 0:
            diskspace = self.notification_data[1:-1].decode('utf-8')  # Decode bytearray to string
            print(f"Free Diskspace: {diskspace}kb")

    async def run(self):
        device = await self.discover_device(TARGET_NAME)
        if not device:
            return

        async with BleakClient(device.address, timeout=60.0) as client:
            if client.is_connected:
                print(f"Connected to {device.name}")
                ##print(f"MTU {client.mtu_size}")

                await asyncio.sleep(5)
                # Start Notification Services
                await self.start_notify(client, CTL_CHARACTERISTIC_UUID)
                await self.start_notify(client, TX_CHARACTERISTIC_UUID)
                print(f"Notifications started")
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
            sys.exit()

        return fit_files

    def save_file_raw(self, name, data):
        while data and data[-1] == 0x00:    # Remove padded zeros at the end.
            data = data[:-1]
        try:
            with open(name, "wb") as file:
                file.write(data)
            print(f"Successfully wrote combined data to {name}")
        except Exception as e:
            print(f"Failed to decode/write data: {e}")

    def crc_xor8(self, data):
        '''
        See request_array() how to use.
        '''
        crc = 0
        for x in data:
            crc ^= x
        return crc & 0xff

    def crc16_arc(self, data):
        '''crc16/arc
        Xoss uses CRC16/ARC instead of CRC16/XMODEM. 
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

    def request_array(self, string):
        byte_array = bytearray([0x05]) + bytearray(string, 'utf-8') + bytearray([0x00])
        byte_array[-1] = self.crc_xor8(byte_array)    # Replace the padded zero with crc_xor8.
        return byte_array


if __name__ == "__main__":
    transfer = BluetoothFileTransfer()
    asyncio.run(transfer.run())
