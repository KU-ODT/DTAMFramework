from __future__ import annotations

import sys

from PyQt5 import QtCore, QtWebEngineWidgets, QtWidgets

from app.config import APP_TITLE, DATA_DIR, MBTILES_PATH, RESOURCES_DIR, SERVER_HOST, SERVER_PORT, WEB_DIR
from app.mbtiles import MBTiles
from app.tile_server import TileServer


def main() -> int:
    mbtiles = MBTiles(MBTILES_PATH)
    server = TileServer(
        mbtiles=mbtiles,
        web_dir=WEB_DIR,
        resources_dir=RESOURCES_DIR,
        data_dir=DATA_DIR,
        host=SERVER_HOST,
        port=SERVER_PORT,
    )
    server.start()

    app = QtWidgets.QApplication(sys.argv)
    view = QtWebEngineWidgets.QWebEngineView()
    view.setUrl(QtCore.QUrl(server.url))

    window = QtWidgets.QMainWindow()
    window.setWindowTitle(APP_TITLE)
    window.setCentralWidget(view)
    window.resize(1400, 900)

    def _cleanup() -> None:
        server.stop()
        mbtiles.close()

    app.aboutToQuit.connect(_cleanup)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
