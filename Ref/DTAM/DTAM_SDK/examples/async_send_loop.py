"""Non-blocking send example for a simulation loop."""

import time

from dtam_client import DtamClient


def main() -> None:
    dtam = DtamClient.from_config("dtam_config.json", auto_listen=True)

    def on_send_error(result) -> None:
        print(result)

    dtam.on_send_error = on_send_error

    try:
        while True:
            dtam.push_vehicle_status_async(dtam.sample("4001"))
            time.sleep(1.0)
    finally:
        dtam.close()


if __name__ == "__main__":
    main()
