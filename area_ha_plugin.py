from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import (
    Qgis,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsField,
    QgsMapLayerType,
    QgsWkbTypes,
)
import os

from .field_calc_dialog import FieldCalcDialog


class AreaHaPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu_name = "FeraTools"
        self.action = None
        self.icon_path = os.path.join(os.path.dirname(__file__), "icon_area.svg")

    def initGui(self):
        self.action = QAction(QIcon(self.icon_path), "Área", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addCustomActionForLayerType(
            self.action,
            self.menu_name,
            Qgis.LayerType.Vector,
            True,
        )

    def unload(self):
        if self.action:
            self.iface.removeCustomActionForLayerType(self.action)

    def run(self):
        layer = self.iface.activeLayer()

        if not layer:
            QMessageBox.warning(None, "Área", "Nenhuma camada ativa.")
            return

        if layer.type() != QgsMapLayerType.VectorLayer:
            QMessageBox.warning(None, "Área", "A camada ativa não é vetorial.")
            return

        if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            QMessageBox.warning(None, "Área", "A camada ativa não é poligonal.")
            return

        dlg = FieldCalcDialog(
            has_selection=(layer.selectedFeatureCount() > 0),
            parent=self.iface.mainWindow(),
        )

        if dlg.exec_() != dlg.Accepted:
            return

        vals = dlg.values()

        field_name = vals["field_name"]
        expr = QgsExpression(vals["expression"])
        selected_only = vals["selected_only"]
        length = vals["length"]
        precision = vals["precision"]

        if not field_name:
            QMessageBox.warning(None, "Área", "Informe o nome do campo.")
            return

        if selected_only and layer.selectedFeatureCount() == 0:
            QMessageBox.warning(None, "Área", "Não há feições selecionadas.")
            return

        started_here = False

        try:
            self.iface.showAttributeTable(layer)

            if not layer.isEditable():
                if not layer.startEditing():
                    raise Exception("Não foi possível iniciar a edição da camada.")
                started_here = True

            idx = layer.fields().indexOf(field_name)

            if idx == -1:
                ok = layer.dataProvider().addAttributes([
                    QgsField(field_name, QVariant.Double, "double", length, precision)
                ])
                if not ok:
                    raise Exception(f"Não foi possível criar o campo '{field_name}'.")
                layer.updateFields()
                idx = layer.fields().indexOf(field_name)

            context = QgsExpressionContext()
            context.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(layer)
            )

            if selected_only:
                fids = layer.selectedFeatureIds()
                request = QgsFeatureRequest().setFilterFids(fids)
                features = layer.getFeatures(request)
            else:
                features = layer.getFeatures()

            for feat in features:
                context.setFeature(feat)
                value = expr.evaluate(context)

                if expr.hasEvalError():
                    raise Exception(expr.evalErrorString())

                if value is not None:
                    value = round(float(value), precision)

                if not layer.changeAttributeValue(feat.id(), idx, value):
                    raise Exception(f"Falha ao atualizar a feição ID {feat.id()}.")

            if started_here:
                if not layer.commitChanges():
                    raise Exception("Falha ao salvar as alterações.")
            else:
                layer.triggerRepaint()

            self.iface.messageBar().pushSuccess(
                "Área",
                f"Campo '{field_name}' criado/atualizado com sucesso.",
            )

        except Exception as e:
            if started_here and layer.isEditable():
                layer.rollBack()
            QMessageBox.critical(None, "Área", str(e))
