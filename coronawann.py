#!/usr/bin/env python3

import datetime
import io
import json
import sqlite3
import struct
import urllib.request as request
import zipfile
import itertools as it

from multiprocessing import Pool

from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from expb_pb2 import TemporaryExposureKeyExport

URL_API_BASE = 'https://svc90.main.px.t-online.de/version/v1/diagnosis-keys/country/DE/date'

def generate_rpis(tek, interval_start):
    rpik = HKDF(master=tek, key_len=16, salt=None, hashmod=SHA256, context="EN-RPIK".encode("UTF-8"))
    cipher = AES.new(rpik, AES.MODE_ECB)

    padding = b"EN-RPI" + bytes([0x00] * 6)

    return tuple(
        cipher.encrypt(padding + struct.pack("<I", interval_start + i))
        for i in range(144)
    )

def handle_key_chunk(key_chunk):
    i, key_chunk = key_chunk

    print(f'{i}')

    return tuple(
        (rpi, key)
        for key in key_chunk
        for rpi in generate_rpis(key.key_data, key.rolling_start_interval_number)
    )

def download_diagnosis_keys():
    cur_files = request.urlopen(URL_API_BASE).read().decode('utf-8')
    cur_files = set(json.loads(cur_files))

    for name in sorted(cur_files)[::-1]:
        print(f'Downloading {name}')
        content = request.urlopen(URL_API_BASE + '/' + name).read()
        content = io.BytesIO(content)
        content = zipfile.ZipFile(content)
        content = content.open('export.bin').read()

        export = TemporaryExposureKeyExport()
        export.ParseFromString(content[16:])

        print(f'Download complete. Got {len(export.keys)} keys to process')

        def key_chunks():
            for i in it.count(0, 10000):
                r = export.keys[i:i+10000]
                if len(r) == 0:
                    break
                yield (i, r)

        with Pool(12) as p:
            for chunk in p.imap_unordered(handle_key_chunk, key_chunks()):
                yield chunk

def read_exposure_db(exposure_db):
    exp_db = sqlite3.connect(exposure_db)
    adv = exp_db.execute('SELECT rpi, aem, timestamp, rssi, duration FROM advertisements')

    return dict(
        (rpi, (aem, timestamp, rssi, duration))
        for rpi, aem, timestamp, rssi, duration in adv
    )

def summarize(exposure_db_path):
    exp_db = read_exposure_db(exposure_db_path)
    for key_chunk in download_diagnosis_keys():
        for rpi, key in key_chunk:
            if rpi not in exp_db:
                continue

            print(rpi, key)

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print(f'{sys.argv[1]} exposure.db')
        sys.exit(1)

    summarize(sys.argv[1])
