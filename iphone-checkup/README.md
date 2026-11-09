# iPhone Checkup (Windows)

Reads health information from an iPhone plugged into a Windows PC with a cable:
storage, battery health, configuration profiles, installed apps, and crash logs.
It only **reads**. It doesn't change or delete anything on the phone.

## Before you start
1. Install **Python** from python.org (tick **Add Python to PATH**).
2. Install the **Apple Devices** app from the Microsoft Store (or iTunes).
3. Plug in the iPhone, unlock it, and tap **Trust** if asked.

## Run it
1. Download this folder (on GitHub: **Code → Download ZIP**, then unzip it).
2. Double-click **`run_checkup.bat`**.
3. When it finishes, open **`iphone_report.txt`** in the same folder.

Lines starting with `>>` point to likely problems.

The report doesn't include your serial number, IMEI, or phone number.
It does list the names of your installed apps.
