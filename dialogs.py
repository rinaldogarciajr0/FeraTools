from dataclasses import dataclass

from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)


ZONE_ITEMS = [
    ("SIRGAS 2000 / UTM zona 18S (EPSG:31978)", "EPSG:31978"),
    ("SIRGAS 2000 / UTM zona 19S (EPSG:31979)", "EPSG:31979"),
    ("SIRGAS 2000 / UTM zona 20S (EPSG:31980)", "EPSG:31980"),
    ("SIRGAS 2000 / UTM zona 21S (EPSG:31981)", "EPSG:31981"),
    ("SIRGAS 2000 / UTM zona 22S (EPSG:31982)", "EPSG:31982"),
    ("SIRGAS 2000 / UTM zona 23S (EPSG:31983)", "EPSG:31983"),
    ("SIRGAS 2000 / UTM zona 24S (EPSG:31984)", "EPSG:31984"),
    ("SIRGAS 2000 / UTM zona 25S (EPSG:31985)", "EPSG:31985"),
    ("SIRGAS 2000 geográfico (EPSG:4674)", "EPSG:4674"),
    ("WGS 84 geográfico (EPSG:4326)", "EPSG:4326"),
]


@dataclass
class FieldConfig:
    axis: str
    field_name: str
    output_format: str
    precision: int
    target_authid: str
    selected_only: bool


class CoordinateFieldDialog(QDialog):
    def __init__(self, axis, default_field_name, has_selection, initial=None, parent=None):
        super().__init__(parent)
        self.axis = axis.upper()
        self.setWindowTitle(f"Configurar campo {self.axis}")
        self.setModal(True)
        self.resize(560, 340)

        self._build_ui(default_field_name, has_selection)
        if initial:
            self._apply_initial(initial)
        self._update_expression_preview()

    def _build_ui(self, default_field_name, has_selection):
        root = QVBoxLayout(self)

        intro = QLabel(
            f"Defina como o campo {self.axis} será criado/calculado na tabela de atributos."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        group = QGroupBox(f"Campo {self.axis}")
        form = QFormLayout(group)

        self.field_name_edit = QLineEdit(default_field_name)
        self.field_name_edit.textChanged.connect(self._update_expression_preview)
        form.addRow("Nome do campo", self.field_name_edit)

        self.format_combo = QComboBox()
        self.format_combo.addItem("Decimal", "decimal")
        self.format_combo.addItem("Graus, minutos e segundos (texto)", "dms")
        self.format_combo.currentIndexChanged.connect(self._update_expression_preview)
        form.addRow("Formato", self.format_combo)

        self.precision_spin = QSpinBox()
        self.precision_spin.setRange(0, 10)
        self.precision_spin.setValue(3)
        self.precision_spin.valueChanged.connect(self._update_expression_preview)
        form.addRow("Precisão", self.precision_spin)

        self.crs_combo = QComboBox()
        for label, authid in ZONE_ITEMS:
            self.crs_combo.addItem(label, authid)
        self.crs_combo.setCurrentIndex(5)
        self.crs_combo.currentIndexChanged.connect(self._update_expression_preview)
        form.addRow("CRS de saída", self.crs_combo)

        self.selected_only_checkbox = QCheckBox("Apenas feições selecionadas")
        self.selected_only_checkbox.setEnabled(has_selection)
        self.selected_only_checkbox.stateChanged.connect(self._update_expression_preview)
        form.addRow("Escopo", self.selected_only_checkbox)

        root.addWidget(group)

        self.expression_preview = QPlainTextEdit()
        self.expression_preview.setReadOnly(True)
        self.expression_preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.expression_preview.setPlaceholderText("Prévia da expressão...")
        root.addWidget(QLabel("Expressão (prévia)"))
        root.addWidget(self.expression_preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _apply_initial(self, initial):
        self.field_name_edit.setText(initial.get("field_name", self.field_name_edit.text()))
        fmt = initial.get("output_format", "decimal")
        idx = self.format_combo.findData(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        precision = int(initial.get("precision", 3))
        self.precision_spin.setValue(precision)
        authid = initial.get("target_authid", "EPSG:31983")
        idx = self.crs_combo.findData(authid)
        if idx >= 0:
            self.crs_combo.setCurrentIndex(idx)
        self.selected_only_checkbox.setChecked(bool(initial.get("selected_only", False)))

    def _update_expression_preview(self):
        axis_function = "x" if self.axis == "X" else "y"
        authid = self.crs_combo.currentData()
        precision = self.precision_spin.value()
        field_name = self.field_name_edit.text().strip() or f"coord_{self.axis.lower()}"
        output_format = self.format_combo.currentData()

        if output_format == "decimal":
            preview = (
                f"Campo: {field_name}\n"
                f"round({axis_function}(transform(@geometry, layer_property(@layer, 'crs'), '{authid}')), {precision})"
            )
        else:
            preview = (
                f"Campo: {field_name}\n"
                f"dms({axis_function}(transform(@geometry, layer_property(@layer, 'crs'), '{authid}')), {precision})"
            )

        self.expression_preview.setPlainText(preview)

    def _on_accept(self):
        field_name = self.field_name_edit.text().strip()
        if not field_name:
            QMessageBox.warning(self, "Campo obrigatório", "Informe um nome de campo.")
            return

        authid = self.crs_combo.currentData()
        output_format = self.format_combo.currentData()
        if output_format == "dms":
            crs = QgsCoordinateReferenceSystem(authid)
            if not crs.isValid() or not crs.isGeographic():
                QMessageBox.warning(
                    self,
                    "CRS incompatível",
                    "Para formato em graus/minutos/segundos, escolha um CRS geográfico, como EPSG:4674 ou EPSG:4326.",
                )
                return

        self.accept()

    def config(self):
        return FieldConfig(
            axis=self.axis,
            field_name=self.field_name_edit.text().strip(),
            output_format=self.format_combo.currentData(),
            precision=self.precision_spin.value(),
            target_authid=self.crs_combo.currentData(),
            selected_only=self.selected_only_checkbox.isChecked(),
        )


class CoordinateFieldsDialog(QDialog):
    def __init__(self, defaults, has_selection, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar coordenadas")
        self.setModal(True)
        self.resize(640, 520)
        self.controls = {}

        root = QVBoxLayout(self)

        for axis in ("X", "Y"):
            group = QGroupBox(f"Campo {axis}")
            form = QFormLayout(group)

            field_name = QLineEdit(defaults[axis]["field_name"])
            form.addRow("Nome do campo", field_name)

            format_combo = QComboBox()
            format_combo.addItem("Decimal", "decimal")
            format_combo.addItem("Graus, minutos e segundos (texto)", "dms")
            form.addRow("Formato", format_combo)

            precision_spin = QSpinBox()
            precision_spin.setRange(0, 10)
            precision_spin.setValue(3)
            form.addRow("Precisão", precision_spin)

            crs_combo = QComboBox()
            for label, authid in ZONE_ITEMS:
                crs_combo.addItem(label, authid)
            crs_combo.setCurrentIndex(5)
            form.addRow("CRS de saída", crs_combo)

            self.controls[axis] = {
                "field_name": field_name,
                "format": format_combo,
                "precision": precision_spin,
                "crs": crs_combo,
            }
            self._apply_axis_initial(axis, defaults[axis])
            root.addWidget(group)

        self.selected_only_checkbox = QCheckBox("Apenas feições selecionadas")
        self.selected_only_checkbox.setEnabled(has_selection)
        root.addWidget(self.selected_only_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _apply_axis_initial(self, axis, initial):
        controls = self.controls[axis]

        fmt = initial.get("output_format", "decimal")
        idx = controls["format"].findData(fmt)
        if idx >= 0:
            controls["format"].setCurrentIndex(idx)

        controls["precision"].setValue(int(initial.get("precision", 3)))

        authid = initial.get("target_authid", "EPSG:31983")
        idx = controls["crs"].findData(authid)
        if idx >= 0:
            controls["crs"].setCurrentIndex(idx)

    def _on_accept(self):
        x_name = self.controls["X"]["field_name"].text().strip()
        y_name = self.controls["Y"]["field_name"].text().strip()

        if not x_name or not y_name:
            QMessageBox.warning(self, "Campo obrigatório", "Informe os nomes dos campos X e Y.")
            return

        if x_name.lower() == y_name.lower():
            QMessageBox.warning(self, "Campos duplicados", "Os campos X e Y precisam ter nomes diferentes.")
            return

        for axis in ("X", "Y"):
            controls = self.controls[axis]
            if controls["format"].currentData() != "dms":
                continue

            crs = QgsCoordinateReferenceSystem(controls["crs"].currentData())
            if not crs.isValid() or not crs.isGeographic():
                QMessageBox.warning(
                    self,
                    "CRS incompatível",
                    "Para formato em graus/minutos/segundos, escolha um CRS geográfico, como EPSG:4674 ou EPSG:4326.",
                )
                return

        self.accept()

    def _axis_config(self, axis):
        controls = self.controls[axis]
        return FieldConfig(
            axis=axis,
            field_name=controls["field_name"].text().strip(),
            output_format=controls["format"].currentData(),
            precision=controls["precision"].value(),
            target_authid=controls["crs"].currentData(),
            selected_only=self.selected_only_checkbox.isChecked(),
        )

    def configs(self):
        return self._axis_config("X"), self._axis_config("Y")
