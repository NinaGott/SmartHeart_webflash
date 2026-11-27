"""Validate PlatformIO artifacts and prepare a complete ESP32 browser install."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--project', type=Path, required=True, help='SmartHeart firmware checkout')
parser.add_argument('--pio-home', type=Path, default=Path.home() / '.platformio')
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
project = args.project.resolve()
version = re.search(r'kFirmwareVersion\[\]\s*=\s*"([0-9]+\.[0-9]+)"',
    (project / 'src/version.h').read_text(encoding='utf-8'))
if not version:
    raise SystemExit('Cannot read firmware version from src/version.h')
version = version[1]
for name in ['bootloader.bin', 'partitions.bin', 'firmware.bin', 'littlefs.bin']:
    source = root / name
    built = project / '.pio/build/wemos_d1_mini32' / name
    if not source.is_file() or not built.is_file() or source.read_bytes() != built.read_bytes():
        raise SystemExit(f'{name} does not match the current PlatformIO build. Build and copy all four artifacts first.')
if (version + '\0').encode('ascii') not in (root / 'firmware.bin').read_bytes():
    raise SystemExit('Firmware image does not contain the version from src/version.h. Rebuild it first.')

partitions = {}
data = (root / 'partitions.bin').read_bytes()
for position in range(0, len(data), 32):
    magic, kind, subtype, offset, size, label, flags = struct.unpack('<HBBII16sI', data[position:position + 32])
    if magic == 0x50AA:
        partitions[label.split(b'\0')[0].decode('ascii')] = (offset, size)
if partitions.get('app0') != (0x10000, 0x140000) or partitions.get('spiffs') != (0x290000, 0x160000):
    raise SystemExit('Unexpected partition layout; review the flash offsets before publishing.')
if partitions.get('otadata') != (0xE000, 0x2000):
    raise SystemExit('Unexpected OTA data partition.')
for name, partition in [('firmware.bin', 'app0'), ('littlefs.bin', 'spiffs')]:
    if (root / name).stat().st_size > partitions[partition][1]:
        raise SystemExit(f'{name} exceeds its partition.')

boot_app0 = args.pio_home / 'packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin'
esptool = args.pio_home / 'packages/tool-esptoolpy/esptool.py'
pio_python = args.pio_home / ('penv/Scripts/python.exe' if sys.platform == 'win32' else 'penv/bin/python')
if not boot_app0.is_file() or not esptool.is_file() or not pio_python.is_file():
    raise SystemExit('PlatformIO ESP32 tools are missing. Set --pio-home to your PlatformIO directory.')
shutil.copy2(boot_app0, root / 'boot_app0.bin')
scratch = root / '.helper'
scratch.mkdir(exist_ok=True)
merged = scratch / 'merged.tmp.bin'
parts = [('bootloader.bin', 0x1000), ('partitions.bin', 0x8000),
         ('boot_app0.bin', 0xE000), ('firmware.bin', 0x10000), ('littlefs.bin', 0x290000)]
command = [str(pio_python), str(esptool), '--chip', 'esp32', 'merge_bin', '-o', str(merged),
    '--flash_mode', 'dio', '--flash_freq', '40m', '--flash_size', '4MB']
for name, offset in parts:
    command.extend([hex(offset), str(root / name)])
subprocess.run(command, check=True)
image = merged.read_bytes()
for name, offset in parts:
    original = (root / name).read_bytes()
    if image[offset:offset + len(original)] != original:
        raise SystemExit(f'Merged image does not match {name}; inspect esptool flash header changes.')
if len(image) > 4 * 1024 * 1024:
    raise SystemExit('Merged image exceeds 4 MB flash.')
image_name = f'smartheart-{version}-esp32.bin'
merged.replace(root / image_name)
manifest = {'name': 'SmartHeart', 'version': version,
    'new_install_prompt_erase': False, 'new_install_improv_wait_time': 0,
    'builds': [{'chipFamily': 'ESP32', 'parts': [{'path': image_name, 'offset': 0}]}]}
(root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
names = [name for name, _ in parts] + [image_name]
checksums = ''.join(f'{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}\n' for name in names)
(root / 'checksums.sha256').write_text(checksums, encoding='ascii')
print(f'Prepared SmartHeart {version}: {image_name}, {len(image)} bytes; all five image regions verified.')
