import os

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsField,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .dialogs import CoordinateFieldsDialog


PLUGIN_MENU = "&FeraTools"
CONTEXT_MENU = "FeraTools"
SETTINGS_KEY = "feratools/coordenadas"


class PegarCoordenadasPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar_action = None
        self.menu_action = None
        self.context_action = None
        self.settings = QSettings()
        self.icon_path = os.path.join(os.path.dirname(__file__), "icon_coord.svg")

    def initGui(self):
        self._create_toolbar_action()
        self._create_plugin_menu_actions()
        self._create_layer_context_actions()

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

    def _create_toolbar_action(self):
        self.toolbar_action = QAction(
            QIcon(self.icon_path),
            "Coordenadas",
            self.iface.mainWindow(),
        )
        self.toolbar_action.setToolTip("Criar/atualizar campos X e Y")
        self.toolbar_action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.toolbar_action)

    def _create_plugin_menu_actions(self):
        self.menu_action = QAction(QIcon(self.icon_path), "Coordenadas", self.iface.mainWindow())
        self.menu_action.triggered.connect(self.run)
        self.iface.addPluginToMenu(PLUGIN_MENU, self.menu_action)

    def _create_layer_context_actions(self):
        self.context_action = QAction(QIcon(self.icon_path), "Coordenadas", self.iface.mainWindow())
        self.context_action.triggered.connect(self.run)
        self.iface.addCustomActionForLayerType(
            self.context_action,
            CONTEXT_MENU,
            Qgis.LayerType.Vector,
            True,
        )

    def run(self):
        layer = self.iface.activeLayer()
        if not isinstance(layer, QgsVectorLayer):
            self._warn("Selecione uma camada vetorial primeiro.")
            return

        if layer.geometryType() == Qgis.GeometryType.Null:
            self._warn("A camada selecionada não possui geometria.")
            return

        dialog = CoordinateFieldsDialog(
            defaults={
                "X": {
                    "field_name": self._load_setting("x_field_name", "coord_x"),
                    "output_format": self._load_setting("output_format", "decimal"),
                    "precision": int(self._load_setting("precision", 3)),
                    "target_authid": self._load_setting("target_authid", "EPSG:31983"),
                },
                "Y": {
                    "field_name": self._load_setting("y_field_name", "coord_y"),
                    "output_format": self._load_setting("output_format", "decimal"),
                    "precision": int(self._load_setting("precision", 3)),
                    "target_authid": self._load_setting("target_authid", "EPSG:31983"),
                },
            },
            has_selection=(layer.selectedFeatureCount() > 0),
            parent=self.iface.mainWindow(),
        )
        if dialog.exec_() != dialog.Accepted:
            return

        x_cfg, y_cfg = dialog.configs()

        self._save_defaults(x_cfg, y_cfg)
        self._process_layer(layer, x_cfg, y_cfg)

    def _process_layer(self, layer, x_cfg, y_cfg):
        same_field = x_cfg.field_name.lower() == y_cfg.field_name.lower()
        if same_field:
            self._warn("Os campos X e Y precisam ter nomes diferentes.")
            return

        target_crs_x = QgsCoordinateReferenceSystem(x_cfg.target_authid)
        target_crs_y = QgsCoordinateReferenceSystem(y_cfg.target_authid)
        if not target_crs_x.isValid() or not target_crs_y.isValid():
            self._warn("Um dos CRS selecionados é inválido.")
            return

        selected_only = x_cfg.selected_only or y_cfg.selected_only
        if selected_only and layer.selectedFeatureCount() == 0:
            self._warn("Não há feições selecionadas para processar.")
            return

        feature_ids = [f.id() for f in layer.selectedFeatures()] if selected_only else None

        started_editing = False
        if not layer.isEditable():
            if not layer.startEditing():
                self._warn("Não foi possível colocar a camada em modo de edição.")
                return
            started_editing = True

        try:
            layer.beginEditCommand("Pegar coordenadas")
            self._ensure_field(layer, x_cfg)
            self._ensure_field(layer, y_cfg)
            layer.updateFields()

            x_idx = layer.fields().indexFromName(x_cfg.field_name)
            y_idx = layer.fields().indexFromName(y_cfg.field_name)

            ct_x = QgsCoordinateTransform(layer.crs(), target_crs_x, QgsProject.instance())
            ct_y = QgsCoordinateTransform(layer.crs(), target_crs_y, QgsProject.instance())

            request = QgsFeatureRequest()
            if feature_ids is not None:
                request.setFilterFids(feature_ids)

            updated = 0
            skipped = 0
            for feature in layer.getFeatures(request):
                geom = feature.geometry()
                if not geom or geom.isEmpty():
                    skipped += 1
                    continue

                pt_x = self._feature_point_in_crs(feature, ct_x)
                pt_y = self._feature_point_in_crs(feature, ct_y)
                if pt_x is None or pt_y is None:
                    skipped += 1
                    continue

                value_x = self._format_axis_value(pt_x.x(), x_cfg, is_x=True)
                value_y = self._format_axis_value(pt_y.y(), y_cfg, is_x=False)

                layer.changeAttributeValue(feature.id(), x_idx, value_x)
                layer.changeAttributeValue(feature.id(), y_idx, value_y)
                updated += 1

            layer.endEditCommand()

            if started_editing:
                if not layer.commitChanges():
                    errors = "\n".join(layer.commitErrors()) or "Falha ao gravar alterações."
                    self._warn(errors)
                    return

            layer.triggerRepaint()
            self.iface.setActiveLayer(layer)
            self.iface.showAttributeTable(layer)

            msg = f"Campos atualizados: {updated} feição(ões)."
            if skipped:
                msg += f" Ignoradas: {skipped}."
            self.iface.messageBar().pushSuccess("Pegar coordenadas", msg)

        except Exception as exc:
            try:
                layer.destroyEditCommand()
            except Exception:
                pass
            if started_editing:
                layer.rollBack()
            self._warn(f"Erro ao calcular coordenadas: {exc}")

    def _feature_point_in_crs(self, feature, transform):
        geom = feature.geometry()
        centroid = geom.centroid()
        if not centroid or centroid.isEmpty():
            return None
        point = centroid.asPoint()
        try:
            return transform.transform(point)
        except Exception:
            return None

    def _ensure_field(self, layer, cfg):
        field_idx = layer.fields().indexFromName(cfg.field_name)
        if field_idx >= 0:
            return

        if cfg.output_format == "decimal":
            field = QgsField(cfg.field_name, QMetaType.Type.Double, "double", 20, cfg.precision)
        else:
            field = QgsField(cfg.field_name, QMetaType.Type.QString, "string", 40, 0)

        layer.addAttribute(field)

    def _format_axis_value(self, value, cfg, is_x):
        if cfg.output_format == "decimal":
            return round(value, cfg.precision)
        return self._decimal_to_dms(value, cfg.precision, is_longitude=is_x)

    def _decimal_to_dms(self, decimal_value, precision, is_longitude):
        hemi = self._hemisphere(decimal_value, is_longitude)
        absolute = abs(decimal_value)
        degrees = int(absolute)
        minutes_full = (absolute - degrees) * 60.0
        minutes = int(minutes_full)
        seconds = round((minutes_full - minutes) * 60.0, precision)

        if seconds >= 60:
            seconds = 0.0
            minutes += 1
        if minutes >= 60:
            minutes = 0
            degrees += 1

        sec_text = f"{seconds:.{precision}f}"
        return f"{degrees} deg {minutes:02d}' {sec_text}\" {hemi}"

    def _hemisphere(self, value, is_longitude):
        if is_longitude:
            return "E" if value >= 0 else "W"
        return "N" if value >= 0 else "S"

    def _save_defaults(self, x_cfg, y_cfg):
        self._save_setting("x_field_name", x_cfg.field_name)
        self._save_setting("y_field_name", y_cfg.field_name)
        self._save_setting("output_format", y_cfg.output_format)
        self._save_setting("precision", y_cfg.precision)
        self._save_setting("target_authid", y_cfg.target_authid)

    def _load_setting(self, key, default):
        return self.settings.value(f"{SETTINGS_KEY}/{key}", default)

    def _save_setting(self, key, value):
        self.settings.setValue(f"{SETTINGS_KEY}/{key}", value)

    def _warn(self, message):
        QMessageBox.warning(self.iface.mainWindow(), "Pegar coordenadas", message)
        self.iface.messageBar().pushWarning("Pegar coordenadas", message)
