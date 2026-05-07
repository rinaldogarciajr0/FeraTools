from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsMapLayerType
import os

from .exportar_dialog import ExportarDialog


class ExportarShpContexto(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.acao_contexto = None
        self.icon_path = os.path.join(os.path.dirname(__file__), "icon_export.svg")

    def initGui(self):
        self.acao_contexto = QAction(
            QIcon(self.icon_path),
            "Exportar",
            self.iface.mainWindow(),
        )
        self.acao_contexto.triggered.connect(self.executar_exportacao)

        self.iface.addCustomActionForLayerType(
            self.acao_contexto,
            "FeraTools",
            QgsMapLayerType.VectorLayer,
            True,
        )

    def unload(self):
        if self.acao_contexto:
            self.iface.removeCustomActionForLayerType(self.acao_contexto)
            self.acao_contexto = None

    def executar_exportacao(self):
        camada = self.iface.layerTreeView().currentLayer()

        if not camada:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Exportar SHP",
                "Nenhuma camada selecionada.",
            )
            return

        dialog = ExportarDialog(camada, self.iface.mainWindow())
        dialog.exec_()
