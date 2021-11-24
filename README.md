CoronaWannApp
=============

A little script that helps you estimate the severity of a Corona-Warn-App
notifaction by providing the exact time and date of potentially infectious
encounters.

Uses an `exposures.db` sqlite3 file that can e.g. be exported from the
microG exposure notification implementation.

Be warned, that this is a a hobby project i've cobbled together when I
needed it, so the code and comment quality is rather bad and my usage of
protobufs and sqlite3 are not quite how their creators intended them to be.

If you want something that just works™ please have a look at
[corona-warn-companion](https://github.com/mh-/corona-warn-companion-android)
first. I did not test it but the screenshots look well-made.

Also **Do not blindly take health advice from this software** there can be all
kinds of issues, like bad timezone handling that could lead you to wrong conclusions.

Dependencies
------------

To install the required dependencies on an Arch Linux based system execute
the following command:

    $ sudo pacman -S python python-protobuf python-pycryptodome

Usage
-----

Please not that the script will generate a database file, containing all the
ids derived from the published diagnosis keys. At the time of writing this file
will be about 4.5GB in size. Due to some issue in the database handling[^1], this
file will be heavily written to and read from, resulting in heavy thrashing of
your SSD. If you have enough RAM to spare you might want to put this database
file in a tmpfs, this will speed up the `update_diagnosis_keys` by orders of magnitude.

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

[^1]: Patches welcome