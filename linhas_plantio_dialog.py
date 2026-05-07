from dataclasses import dataclass

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)


FIELD_TYPES = [
    ("Texto", QVariant.String, "string", 0),
    ("Numero inteiro", QVariant.Int, "integer", 0),
    ("Numero inteiro longo", QVariant.LongLong, "integer64", 0),
    ("Numero decimal (real)", QVariant.Double, "double", 3),
    ("Booleano", QVariant.Bool, "boolean", 0),
    ("Data", QVariant.Date, "date", 0),
    ("Data e hora", QVariant.DateTime, "datetime", 0),
]


@dataclass
class PlantingLinesConfig:
    horizontal_spacing: float
    vertical_spacing: float
    field_name: str
    field_type: object
    field_type_name: str
    field_length: int
    field_precision: int
    expression: str


class LinhasPlantioDialog(QDialog):
    def __init__(self, layer_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Linhas de Plantio")
        self.setModal(True)
        self.resize(620, 430)

        layout = QVBoxLayout(self)
        info = QLabel(
            f"Camada usada para extensao e recorte: {layer_name}\n"
            "Tipo de grade: Ponto"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self.horizontal_spin = QDoubleSpinBox()
        self.horizontal_spin.setRange(0.01, 1000000.0)
        self.horizontal_spin.setDecimals(2)
        self.horizontal_spin.setSuffix(" m")
        self.horizontal_spin.setValue(3.0)
        self.horizontal_spin.valueChanged.connect(self._update_expression)
        form.addRow("Espacamento horizontal", self.horizontal_spin)

        self.vertical_spin = QDoubleSpinBox()
        self.vertical_spin.setRange(0.01, 1000000.0)
        self.vertical_spin.setDecimals(2)
        self.vertical_spin.setSuffix(" m")
        self.vertical_spin.setValue(2.0)
        self.vertical_spin.valueChanged.connect(self._update_expression)
        form.addRow("Espacamento vertical", self.vertical_spin)

        self.field_name_edit = QLineEdit("Grupo")
        form.addRow("Nome do campo", self.field_name_edit)

        self.field_type_combo = QComboBox()
        for label, variant_type, type_name, default_precision in FIELD_TYPES:
            self.field_type_combo.addItem(
                label,
                {
                    "variant_type": variant_type,
                    "type_name": type_name,
                    "precision": default_precision,
                },
            )
        self.field_type_combo.currentIndexChanged.connect(self._update_precision_for_type)
        form.addRow("Tipo do novo campo", self.field_type_combo)

        self.length_spin = QSpinBox()
        self.length_spin.setRange(1, 255)
        self.length_spin.setValue(20)
        form.addRow("Comprimento do campo de saida", self.length_spin)

        self.precision_spin = QSpinBox()
        self.precision_spin.setRange(0, 15)
        self.precision_spin.setValue(0)
        form.addRow("Precisao", self.precision_spin)

        layout.addLayout(form)

        layout.addWidget(QLabel("Expressao"))
        self.expression_edit = QPlainTextEdit()
        self.expression_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        layout.addWidget(self.expression_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_expression()

    def _update_precision_for_type(self):
        self.precision_spin.setValue(self.field_type_combo.currentData()["precision"])

    def _update_expression(self):
        vertical = self.vertical_spin.value()
        vertical_text = f"{vertical:.6f}".rstrip("0").rstrip(".")
        expression = (
            "CASE \n"
            f"WHEN (floor(($y - aggregate(@layer, 'min', $y)) / {vertical_text}) % 2) = 0 THEN 'Cobertura'\n"
            "ELSE 'Diversidade'\n"
            "END"
        )
        self.expression_edit.setPlainText(expression)

    def _on_accept(self):
        if not self.field_name_edit.text().strip():
            QMessageBox.warning(self, "Linhas de Plantio", "Informe o nome do campo.")
            return

        if self.field_type_combo.currentData()["variant_type"] != QVariant.String:
            answer = QMessageBox.question(
                self,
                "Tipo do campo",
                "A expressao padrao retorna os textos Cobertura e Diversidade.\n\n"
                "Deseja continuar com um campo que nao e texto?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.No:
                return

        self.accept()

    def values(self):
        type_data = self.field_type_combo.currentData()
        return PlantingLinesConfig(
            horizontal_spacing=self.horizontal_spin.value(),
            vertical_spacing=self.vertical_spin.value(),
            field_name=self.field_name_edit.text().strip(),
            field_type=type_data["variant_type"],
            field_type_name=type_data["type_name"],
            field_length=self.length_spin.value(),
            field_precision=self.precision_spin.value(),
            expression=self.expression_edit.toPlainText().strip(),
        )
