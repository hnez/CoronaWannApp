CoronaWannApp
=============

A little script that helps you estimate the severity of a Corona-Warn-App
notifaction by providing the exact time and date of potentially infectious
encounters.

Uses an `exposures.db` sqlite3 file that can e.g. be exported from the
microG exposure notification implementation.


Usage
-----

    $ python3 -i coronawann.py
    >>> cw = CoronaWann()
    >>> cw.update_diagnosis_keys()
    Downloading 2021-11-09
    Import keys
    0/70518
    ...
    >>> cw.import_exposure_db('exposure.db') # The exposure database exported from microG
    >>> cw.summarize()
    Contact with Alice at 2021-11-10 08:08:30.323000 for 0.0s strength: -101
    Contact with Alice at 2021-11-10 08:19:35.923000 for 542.317s strength: -94
    Contact with Alice at 2021-11-10 08:49:53.435000 for 0.0s strength: -99
    ...
