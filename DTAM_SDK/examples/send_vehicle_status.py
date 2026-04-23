"""Send one sample vehicle status message."""

from dtam_client import DtamClient


def main() -> None:
    dtam = DtamClient.from_config("dtam_config.json", auto_listen=True)
    result = dtam.push_vehicle_status(dtam.sample("4001"))
    print(result)
    dtam.close()


if __name__ == "__main__":
    main()
