# sigpert-gr-iridium (from SMARTSP 2026)

Hello! Welcome to sigpert-gr-iridium. This is a modified gr-iridium library, designed as part of "Satellite Signal Perturbation for Dual-Fingerprint Authentication and Spoofing Detection", to appear in SmartSP 2026. This is a fork of [gr-iridium](https://github.com/muccc/gr-iridium), the GNU Radio out-of-tree module for receiving and demodulating Iridium satellite signals. Our fork adds an IQ export path: for every burst that passes the sync-word check, the demodulator pushes the burst's IQ samples over ZeroMQ to a small Python script that stores them in an SQLite database.

Two variants of the demodulator are included:

| Variant | Source files (`lib/`) | Database writer | What is stored per burst |
|---|---|---|---|
| **Decimated (default)** | `iridium_qpsk_demod_impl.cc` / `.h` | `db_write.py` | Two vectors of `n_symbols` samples: after the PLL (`iq`) and the decimated burst before the PLL (`iq_pre`) |
| **Single** | `iridium_qpsk_demod_impl_single.cc` / `_single.h` | `db_write_single.py` | One vector: the burst samples (`iq`) |

The default build compiles the decimated variant. See [Switching to the single variant](#switching-to-the-single-variant) to use the other.

All standard `iridium-extractor` behaviour (the `.bits` output, configuration files, command-line options) is unchanged from upstream.

---

## Requirements

- Linux (also works under WSL2 on Windows)
- [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- GNU Radio 3.9 or newer (installed via conda below)
- An SDR supported by GNU Radio (HackRF, USRP, RTL-SDR, Airspy, BladeRF, LimeSDR…), or a recorded capture file for offline processing
- An Iridium downlink compatible antenna and bandpass filter
- A Low Noise Amplifier (LNA) is optional, depending on your antenna and signal strength

---

## Installation

### 1. Create the conda environment

```bash
conda create -n sigpert -c conda-forge python=3.11
conda activate sigpert
```

### 2. Install dependencies

```bash
conda install -c conda-forge \
    gnuradio gnuradio-osmosdr soapysdr \
    cmake make pkg-config cxx-compiler \
    libboost-devel pybind11 numpy volk spdlog fmt \
    zeromq cppzmq pyzmq sqlite
```

Add the driver package for your SDR if it is not covered above, for example `uhd` for Ettus USRPs or `soapysdr-module-hackrf` for HackRF via SoapySDR.

### 3. Build and install

From the root of this repository:

```bash
mkdir build && cd build
cmake .. \
    -DCMAKE_PREFIX_PATH=$CONDA_PREFIX \
    -DCMAKE_INSTALL_PREFIX=$CONDA_PREFIX \
    -DPython3_EXECUTABLE=$CONDA_PREFIX/bin/python
make -j$(nproc)
make install
cd ..
```

### 4. Verify

```bash
which iridium-extractor
python -c "import iridium; print(iridium.__file__)"
```

Both should point inside your conda environment (`$CONDA_PREFIX`).

---

## Running

The extractor and the database writer run in two separate terminals. Start the database writer first.

### Terminal 1: database writer

```bash
conda activate sigpert
python db_write.py
```
It binds to `tcp://127.0.0.1:5555` and prints:
```
Database writer is running and listening for incoming data...
```
Note: We hard-coded the output file name in the script itself, but feel free to modify the script to create the I-Q signal file from a command-line argument.

### Terminal 2: extractor

**Live, with an SDR** (choose the config matching your hardware from `examples/`):

```bash
conda activate sigpert
iridium-extractor -D 4 examples/usrp-b2x0-uhd.conf > output.bits
```
Note: Remember to set the correct arguments for your USRP. This includes the IP address and the antenna!

**Offline, from a recording:**

```bash
iridium-extractor -c 1626000000 -r 2000000 -f float capture.cfile > output.bits
iridium-extractor recording.sigmf-meta > output.bits
```

As bursts are detected, Terminal 1 prints one line per burst:

```
Data for ID 1791858864 written to database. IQ vector sizes: 61, 61
```

Stop both programs with `Ctrl+C`.

### Outputs

- **`output.bits`**: demodulated frames in the standard gr-iridium `RAW:` format. These can be parsed further with [iridium-toolkit](https://github.com/muccc/iridium-toolkit).
- **`d_burst_test2.db`** (decimated variant) or **`d_burst_test.db`** (single variant): SQLite database of burst IQ samples, created in the directory where you ran the writer.

---

## Database format

### Decimated variant (`db_write.py`)

Table `iq_data`:

| Column | Type | Contents |
|---|---|---|
| `id` | INTEGER | Burst ID (matches the `I:` field in `output.bits`) |
| `iq` | BLOB | Burst after the PLL, `complex64`, `n_symbols` samples |
| `iq_pre` | BLOB | Decimated burst before the PLL, `complex64`, `n_symbols` samples |

### Single variant (`db_write_single.py`)

Table `iq_data`:

| Column | Type | Contents |
|---|---|---|
| `id` | INTEGER | Burst ID |
| `iq` | BLOB | Burst samples, `complex64` |

This contains the raw captured samples of a burst. Decimate by indexing the 0th index for each 10 samples (from 0-9) in a burst. 

### Reading the data back

```python
import sqlite3
import numpy as np

conn = sqlite3.connect("d_burst_test2.db")
for id, iq, iq_pre in conn.execute("SELECT id, iq, iq_pre FROM iq_data"):
    iq = np.frombuffer(iq, dtype=np.complex64)
    iq_pre = np.frombuffer(iq_pre, dtype=np.complex64)
    print(id, len(iq), len(iq_pre))
conn.close()
```

### ZeroMQ message layout

Each message sent by the demodulator to `tcp://127.0.0.1:5555` (PUSH → PULL) is:

```
[int32 burst id][complex64 × n  (iq)][complex64 × n  (iq_pre)]
```

The single variant sends one vector instead of two.

---

## Switching to the single variant

The build always compiles `lib/iridium_qpsk_demod_impl.cc` and its header, so switch variants by renaming both files together:

```bash
cd lib
mv iridium_qpsk_demod_impl.cc iridium_qpsk_demod_impl_decimated.cc
mv iridium_qpsk_demod_impl.h  iridium_qpsk_demod_impl_decimated.h
mv iridium_qpsk_demod_impl_single.cc iridium_qpsk_demod_impl.cc
mv iridium_qpsk_demod_impl_single.h  iridium_qpsk_demod_impl.h
cd ../build
make -j$(nproc) && make install
cd ..
```

Then run `python db_write_single.py` instead of `db_write.py`. To switch back, reverse the renames and rebuild.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `Gnuradio could not be found because dependency Boost could not be found` | `conda install -c conda-forge libboost-devel`, then reconfigure from an empty `build/` with `-DCMAKE_PREFIX_PATH=$CONDA_PREFIX`. Make sure `which cmake` points into the conda env. |
| `fatal error: zmq.hpp: No such file or directory` | `conda install -c conda-forge cppzmq` |
| `fatal error: pybind11/complex.h: No such file or directory` | `conda install -c conda-forge pybind11 numpy` |
| `fatal error: sqlite3.h: No such file or directory` | `conda install -c conda-forge sqlite` |
| `ModuleNotFoundError: No module named 'iridium.iridium_extractor_flowgraph'` | Run `make install`. Do not run the extractor from inside the repository's `python/` folder. Check `python -c "import iridium; print(iridium.__file__)"` points into `$CONDA_PREFIX`. |
| `ModuleNotFoundError: No module named 'zmq'` | `conda install -c conda-forge pyzmq` |
| Database writer prints nothing | Make sure the writer is running before or while the extractor runs, and that both use port `5555`. Only bursts with a valid sync word are sent. |
| `Address already in use` | Another writer is already running on port 5555. Stop it first. |

After installing a missing dependency, rebuild from a clean directory:

```bash
rm -rf build && mkdir build && cd build
cmake .. -DCMAKE_PREFIX_PATH=$CONDA_PREFIX -DCMAKE_INSTALL_PREFIX=$CONDA_PREFIX
make -j$(nproc) && make install
```

---

## Upstream documentation

For configuration file sections, all command-line options, SDR sample-rate guidance and the `.bits` output format, see the [gr-iridium README](https://github.com/muccc/gr-iridium#readme).

## Citation

If you use this work, please cite:

> Wijewardena, K.P. (2026). *Satellite Signal Perturbation for Dual-Fingerprint Authentication and Spoofing Detection.* In: 4th EAI International Conference on Security and Privacy in Cyber-Physical Systems and Smart Vehicles (SmartSP 2026). https://github.com/kpwijewardena/sigpert-gr-iridium

```bibtex
@inproceedings{wijewardena2026sigpert,
  author    = {Wijewardena, Kanishka, and Klevering, Griffin, and Yan, Qiben, and Xiao, Li},
  title     = {Satellite Signal Perturbation for Dual-Fingerprint Authentication and Spoofing Detection},
  booktitle = {EAI International Conference on Security and Privacy in Cyber-Physical Systems and Smart Vehicles (SmartSP)},
  year      = {2026},
}
```

This project builds on [gr-iridium](https://github.com/muccc/gr-iridium). We kindly ask that you acknowledge the original work as well. 

## License

GPL-3.0-or-later, the same as upstream gr-iridium. See `LICENSE`.

This project is a modified version of [gr-iridium](https://github.com/muccc/gr-iridium) by the muccc contributors.