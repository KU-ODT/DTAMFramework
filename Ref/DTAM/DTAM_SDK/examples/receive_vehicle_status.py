"""Receive vehicle status messages until Ctrl+C."""

from dtam_client import DtamClient


def main() -> None:
    dtam = DtamClient.from_config("dtam_config.json", auto_listen=False)

    @dtam.on("4001")
    def on_vehicle_status(result) -> None:
        print(result.to_dict())

    dtam.listen(block=True)


if __name__ == "__main__":
    main()
