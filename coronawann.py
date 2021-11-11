#!/usr/bin/env python3

# USAGE
#
# $ python3 -i coronawann.py
# >>> cw = CoronaWann()
# >>> cw.update_diagnosis_keys()
# Downloading 2021-11-09
# Import keys
# 0/70518
# ...
# >>> cw.import_exposure_db('exposure.db') # The exposure database exported from microG
# >>> cw.summarize()
# Contact with Alice at 2021-11-10 08:08:30.323000 for 0.0s strength: -101
# Contact with Alice at 2021-11-10 08:19:35.923000 for 542.317s strength: -94
# Contact with Alice at 2021-11-10 08:49:53.435000 for 0.0s strength: -99
# ...

import datetime
import io
import json
import sqlite3
import struct
import urllib.request as request
import zipfile

from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from expb_pb2 import TemporaryExposureKeyExport

URL_API_BASE = 'https://svc90.main.px.t-online.de/version/v1/diagnosis-keys/country/DE/date'

DB_SCHEMA_ADVERTISEMENTS = '''
CREATE TABLE IF NOT EXISTS advertisements (
  rpi BLOB NOT NULL,
  aem BLOB NOT NULL,
  timestamp INT NOT NULL,
  rssi INT NOT NULL,
  duration INT NOT NULL
);
'''

DB_SCHEMA_EXPOSURE_KEY_FILE = '''
CREATE TABLE IF NOT EXISTS exposure_key_file (
  name TEXT NOT NULL
)
'''

DB_SCHEMA_EXPOSURE_KEYS = '''
CREATE TABLE IF NOT EXISTS exposure_keys (
  days_since_onset_of_symptoms INT NOT NULL,
  key_data BLOB NOT NULL,
  report_type INT NOT NULL,
  rolling_start_interval_number INT NOT NULL,
  transmission_risk_level INT NOT NULL,
  key_file INT NON NULL,
  FOREIGN KEY(key_file) REFERENCES exposure_key_file(rowid)
);
'''

DB_SCHEMA_EXPOSURE_DERIVED_KEYS = '''
CREATE TABLE IF NOT EXISTS exposure_derived_keys (
  rpi BLOB NOT NULL,
  exposure_key INT NON NULL,
  FOREIGN KEY(exposure_key) REFERENCES exposure_keys(rowid)
);
'''

DB_QUERY_CONTACTS = '''
SELECT timestamp, duration, rssi, exposure_key
FROM advertisements
INNER JOIN exposure_derived_keys
ON advertisements.rpi = exposure_derived_keys.rpi
ORDER BY timestamp;
'''

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
            idx = len(self.ids)
            self.ids[id] = idx

        return self.NAMES[self.ids[id]]

class CoronaWann(object):
    def __init__(self, wann_db='wann.db'):
        self.db = sqlite3.connect(wann_db)

        cur = self.db.cursor()
        cur.execute(DB_SCHEMA_ADVERTISEMENTS)
        cur.execute(DB_SCHEMA_EXPOSURE_KEY_FILE)
        cur.execute(DB_SCHEMA_EXPOSURE_KEYS)
        cur.execute(DB_SCHEMA_EXPOSURE_DERIVED_KEYS)
        cur.execute('CREATE INDEX IF NOT EXISTS adv_rpi_index ON advertisements(rpi);')
        cur.execute('CREATE INDEX IF NOT EXISTS exp_rpi_index ON exposure_derived_keys(rpi);')
        self.db.commit()

    def import_exposure_db(self, exposure_db):
        exp_db = sqlite3.connect(exposure_db)
        inp = exp_db.execute('SELECT rpi, aem, timestamp, rssi, duration FROM advertisements')

        cur = self.db.cursor()
        cur.executemany('INSERT OR REPLACE INTO advertisements VALUES (?, ?, ?, ?, ?)', inp)
        self.db.commit()

    def _generate_rpis(self, tek, interval_start):
        rpik = HKDF(master=tek, key_len=16, salt=None, hashmod=SHA256, context="EN-RPIK".encode("UTF-8"))
        cipher = AES.new(rpik, AES.MODE_ECB)
        for i in range(144):
            enin = struct.pack("<I", interval_start + i)
            padded_data = "EN-RPI".encode("UTF-8") + bytes([0x00] * 6) + enin
            yield cipher.encrypt(padded_data)

    def update_diagnosis_keys(self):
        cur_files = request.urlopen(URL_API_BASE).read().decode('utf-8')
        cur_files = set(json.loads(cur_files))

        have_files = set(
            r[0]
            for r in
            self.db.execute('SELECT name from exposure_key_file')
        )

        new_files = cur_files.difference(have_files)

        for name in sorted(new_files)[::-1]:
            print(f'Downloading {name}')
            content = request.urlopen(URL_API_BASE + '/' + name).read()
            content = io.BytesIO(content)
            content = zipfile.ZipFile(content)
            content = content.open('export.bin').read()

            export = TemporaryExposureKeyExport()
            export.ParseFromString(content[16:])

            cur = self.db.cursor()

            cur.execute('INSERT INTO exposure_key_file VALUES (?)', (name, ))
            file_id = cur.lastrowid

            print('Import keys')

            for i, key in enumerate(export.keys):
                if (i % 1000) == 0:
                    print(f'{i}/{len(export.keys)}')

                values =(
                    key.days_since_onset_of_symptoms, key.key_data, key.report_type,
                    key.rolling_start_interval_number, key.transmission_risk_level, file_id
                )

                cur.execute('INSERT INTO exposure_keys VALUES (?, ?, ?, ?, ?, ?)', values)

                exposure_key_id = cur.lastrowid

                rpis = iter(
                    (rpi, exposure_key_id)
                    for rpi in
                    self._generate_rpis(key.key_data, key.rolling_start_interval_number)
                )

                cur.executemany('INSERT INTO exposure_derived_keys VALUES (?, ?)', rpis)

            self.db.commit()

    def summarize(self):
        aliases = AliasFactory()

        for ts, dur, rssi, key_id in self.db.execute(DB_QUERY_CONTACTS).fetchall():
            when = datetime.datetime.fromtimestamp(ts / 1000)
            dur = dur / 1000
            who = aliases.get(key_id)

            print(f'Contact with {who} at {when} for {dur}s strength: {rssi}')
