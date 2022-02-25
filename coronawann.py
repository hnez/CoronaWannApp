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

class AliasFactory(object):
    NAMES = [
        'Alice', 'Bob', 'Carol', 'Dan', 'Eve',
        'Faythe', 'Grace', 'Heidi', 'Ivan',
        'Judy', 'Mallory', 'Michael', 'Niaj',
        'Olivia', 'Peggy'
    ]

    def __init__(self):
        self.ids = dict()

    def get(self, id):
        if id not in self.ids:
            self.ids[id] = len(self.ids)

        return self.NAMES[self.ids[id]]

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
        (rpi, i, key)
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
            yield from p.imap_unordered(handle_key_chunk, key_chunks())

def read_exposure_db(exposure_db):
    exp_db = sqlite3.connect(exposure_db)
    adv = exp_db.execute('SELECT rpi, aem, timestamp, rssi, duration FROM advertisements')

    return dict(
        (rpi, (aem, timestamp, rssi, duration))
        for rpi, aem, timestamp, rssi, duration in adv
    )

def summarize(exposure_db_path):
    aliases = AliasFactory()

    exp_db = read_exposure_db(exposure_db_path)
    for key_chunk in download_diagnosis_keys():
        for rpi, key_id, key in key_chunk:
            if rpi not in exp_db:
                continue

            aem, ts, rssi, duration = exp_db[rpi]
            trl = key.transmission_risk_level
            dsos = key.days_since_onset_of_symptoms

            rtype = [
                'UNKNOWN', 'CONFIRMED_TEST', 'CONFIRMED_CLINICAL_DIAGNOSIS',
                'SELF_REPORT', 'RECURSIVE', 'REVOKED'
            ][key.report_type]

            alias = aliases.get(key_id)
            when = datetime.datetime.fromtimestamp(ts / 1000)

            print(f'{when} (maybe UTC?) - Contact with {alias} (Has shown symptoms for {dsos} days):')
            print(f' Signal strength: {rssi}, Duration: {duration}, Risk Level: {trl}, Report Type: {rtype}')

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print(f'{sys.argv[1]} exposure.db')
        sys.exit(1)

    summarize(sys.argv[1])
