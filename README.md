# SmartHeart firmware for browser installation

Public firmware artifacts for the **classic ESP32 D1 Mini, 4 MB flash**.

The browser installer uses ESP Web Tools. Its `manifest.json` describes a complete, merged image installed at **offset 0**. The firmware version is generated from the firmware project's `src/version.h`.

## Contents

| Input | Flash address | Purpose |
| --- | --- | --- |
| `bootloader.bin` | `0x1000` | ESP32 bootloader |
| `partitions.bin` | `0x8000` | SmartHeart partition table |
| `boot_app0.bin` | `0xE000` | Arduino OTA boot selection data |
| `firmware.bin` | `0x10000` | SmartHeart application |
| `littlefs.bin` | `0x290000` | Dashboard and onboarding assets |

`smartheart-<version>-esp32.bin` combines all five inputs with flash mode **DIO**, flash frequency **40 MHz**, and flash size **4 MB**. `checksums.sha256` records hashes of all inputs and the merged image. The partition labeled `spiffs` contains **LittleFS**, not a SPIFFS image.

This is a **full installation**: it erases saved Wi-Fi credentials and SmartHeart settings. It is not an OTA update image. ESP8266 and ESP32-S2/S3/C3 variants are not supported by this firmware.

## Wi-Fi after installation

Join **SmartHeart Setup**, password **remindi2387**. Open the standard WiFiManager portal, or `http://192.168.4.1/`, and select your home Wi-Fi. Save the dashboard address displayed during setup, then reconnect to your home Wi-Fi when the setup AP turns off. SmartHeart uses WiFiManager onboarding, not Improv Serial; the manifest disables the Improv wait.

## Preparing a new release

1. Set the requested firmware version in the SmartHeart checkout's `src/version.h`.
2. Build firmware and filesystem in that checkout:

   ```sh
   pio run -e wemos_d1_mini32
   pio run -e wemos_d1_mini32 -t buildfs
   ```

3. Copy `bootloader.bin`, `partitions.bin`, `firmware.bin`, and `littlefs.bin` from `.pio/build/wemos_d1_mini32/` into this repository. Do not copy device NVS dumps or Wi-Fi credentials.
4. Generate and validate the merged image and manifest:

   ```sh
   python tools/prepare_firmware.py --project /path/to/SmartHeart
   ```

   `--pio-home` can override the default `~/.platformio`. The script checks the supplied inputs against the current PlatformIO build and verifies the partition layout and every merged image region. Its scratch files stay in ignored `.helper/`.

5. Review and publish the release files to this repository. In the Cloudflare site's `manifest.json`, set the generated version and use an immutable raw GitHub URL for the image:

   ```text
   https://raw.githubusercontent.com/NinaGott/SmartHeart_webflash/<FULL_COMMIT_SHA>/smartheart-<version>-esp32.bin
   ```

6. Upload the updated `webflasher_SH` directory to Cloudflare Pages. Referencing a commit ensures a published installer always fetches its matching firmware, even when `main` changes later.

## References

- [ESP Web Tools manifest and ESP32 merge instructions](https://esphome.github.io/esp-web-tools/)
