import os

from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMapLayerType,
    QgsPointXY,
    QgsProject,
    QgsRendererCategory,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsMarkerSymbol,
)

from .linhas_plantio_dialog import LinhasPlantioDialog


PLUGIN_MENU = "&FeraTools"
CONTEXT_MENU = "FeraTools"
VALID_GROUPS = {"Diversidade", "Cobertura"}


class LinhasPlantioPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar_action = None
        self.menu_action = None
        self.context_action = None
        self.icon_path = os.path.join(os.path.dirname(__file__), "icon_linhas_plantio.svg")

    def initGui(self):
        self.toolbar_action = QAction(
            QIcon(self.icon_path),
            "Linhas de Plantio",
            self.iface.mainWindow(),
        )
        self.toolbar_action.setToolTip("Criar pontos de plantio recortados pela camada ativa")
        self.toolbar_action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.toolbar_action)

        self.menu_action = QAction(
            QIcon(self.icon_path),
            "Linhas de Plantio",
            self.iface.mainWindow(),
        )
        self.menu_action.triggered.connect(self.run)
        self.iface.addPluginToMenu(PLUGIN_MENU, self.menu_action)

        self.context_action = QAction(
            QIcon(self.icon_path),
            "Linhas de Plantio",
            self.iface.mainWindow(),
        )
        self.context_action.triggered.connect(self.run)
        self.iface.addCustomActionForLayerType(
            self.context_action,
            CONTEXT_MENU,
            Qgis.LayerType.Vector,
            True,
        )

    def unload(self):
        if self.toolbar_action:
            self.iface.removeToolBarIcon(self.toolbar_action)
            self.toolbar_action = None

        if self.menu_action:
            self.iface.removePluginMenu(PLUGIN_MENU, self.menu_action)
            self.menu_action = None

        if self.context_action:
            try:
                self.iface.removeCustomActionForLayerType(self.context_action)
            except Exception:
                pass
            self.context_action = None

    def run(self):
        layer = self.iface.activeLayer()

        if not layer:
            self._warn("Selecione uma camada poligonal primeiro.")
            return

        if layer.type() != QgsMapLayerType.VectorLayer:
            self._warn("A camada ativa nao e vetorial.")
            return

        if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            self._warn("A camada ativa precisa ser poligonal para recortar a grade.")
            return

        if not layer.crs().isValid():
            self._warn("A camada ativa nao possui SRC/CRS valido.")
            return

        if layer.crs().isGeographic():
            self._warn(
                "A camada esta em coordenadas geograficas. Use uma camada em UTM ou outro SRC em metros."
            )
            return

        dialog = LinhasPlantioDialog(layer.name(), self.iface.mainWindow())
        if dialog.exec_() != dialog.Accepted:
            return

        try:
            output = self._create_grid_layer(layer, dialog.values())
        except Exception as exc:
            QMessageBox.critical(self.iface.mainWindow(), "Linhas de Plantio", str(exc))
            return

        QgsProject.instance().addMapLayer(output)
        self.iface.setActiveLayer(output)
        self.iface.messageBar().pushSuccess(
            "Linhas de Plantio",
            f"Camada criada com {output.featureCount()} ponto(s).",
        )

    def _create_grid_layer(self, source_layer, config):
        clip_geometry = self._layer_union_geometry(source_layer)
        if clip_geometry is None or clip_geometry.isEmpty():
            raise Exception("Nao foi possivel montar a geometria de recorte da camada.")

        output = QgsVectorLayer("Point", "Linhas de Plantio", "memory")
        output.setCrs(source_layer.crs())
        provider = output.dataProvider()
        provider.addAttributes(
            [
                QgsField(
                    config.field_name,
                    config.field_type,
                    config.field_type_name,
                    config.field_length,
                    config.field_precision,
                )
            ]
        )
        output.updateFields()

        expression = QgsExpression(config.expression)
        if expression.hasParserError():
            raise Exception(f"Expressao invalida: {expression.parserErrorString()}")

        point_features = self._build_point_features(source_layer, clip_geometry, output.fields(), config)
        if not point_features:
            raise Exception("Nenhum ponto foi criado dentro da camada selecionada.")

        provider.addFeatures(point_features)
        output.updateExtents()

        removed = self._calculate_group_field(output, config, expression)
        self._apply_categorized_style(output, config.field_name)

        if removed:
            output.setName(f"Linhas de Plantio ({output.featureCount()} pontos)")

        return output

    def _layer_union_geometry(self, layer):
        geometries = []
        for feature in layer.getFeatures():
            geometry = feature.geometry()
            if geometry and not geometry.isEmpty():
                geometries.append(QgsGeometry(geometry))

        if not geometries:
            return None

        if len(geometries) == 1:
            return geometries[0]

        return QgsGeometry.unaryUnion(geometries)

    def _build_point_features(self, source_layer, clip_geometry, fields, config):
        extent = source_layer.extent()
        features = []
        y = extent.yMinimum()

        while y <= extent.yMaximum() + 0.000001:
            x = extent.xMinimum()
            while x <= extent.xMaximum() + 0.000001:
                point = QgsPointXY(x, y)
                point_geometry = QgsGeometry.fromPointXY(point)
                if clip_geometry.intersects(point_geometry):
                    feature = QgsFeature(fields)
                    feature.setGeometry(point_geometry)
                    feature.setAttributes([None] * fields.count())
                    features.append(feature)
                x += config.horizontal_spacing
            y += config.vertical_spacing

        return features

    def _calculate_group_field(self, layer, config, expression):
        field_idx = layer.fields().indexFromName(config.field_name)
        if field_idx < 0:
            raise Exception(f"Campo '{config.field_name}' nao foi encontrado na camada criada.")

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))

        layer.startEditing()
        ids_to_delete = []
        for feature in layer.getFeatures():
            context.setFeature(feature)
            value = expression.evaluate(context)
            if expression.hasEvalError():
                layer.rollBack()
                raise Exception(f"Erro ao avaliar expressao: {expression.evalErrorString()}")

            if str(value) not in VALID_GROUPS:
                ids_to_delete.append(feature.id())
                continue

            layer.changeAttributeValue(feature.id(), field_idx, value)

        if ids_to_delete:
            layer.deleteFeatures(ids_to_delete)

        if not layer.commitChanges():
            errors = "\n".join(layer.commitErrors()) or "Falha ao salvar atributos da camada criada."
            raise Exception(errors)

        return len(ids_to_delete)

    def _apply_categorized_style(self, layer, field_name):
        categories = [
            self._category("Diversidade", "#FF002D"),
            self._category("Cobertura", "#00FF07"),
        ]
        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def _category(self, value, color):
        symbol = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": QColor(color).name(),
                "outline_color": "#232323",
                "outline_width": "0.15",
                "size": "2.0",
            }
        )
        return QgsRendererCategory(value, symbol, value)

    def _warn(self, message):
        QMessageBox.warning(self.iface.mainWindow(), "Linhas de Plantio", message)
        self.iface.messageBar().pushWarning("Linhas de Plantio", message)
