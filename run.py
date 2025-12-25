from utils import *
import time
import os
import json
import sys
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
)

class chem_draw_worker(worker):
    def __init__(self):
        super().__init__()
        self.p_img = None
        self.pre_img = None
        self.post_img = None
        self.cap = 5
    def draw_chem(self, smiles: str) -> None:
        """
        Draw the given chemical formula.
        """
        self.write_to_clipboard(smiles)
        self.p_img = self.capture_main_display_gray("beforepaste")
        # print(self.get_clipboard_text())
        self.press_keys(self.pasteKey)
        time.sleep(1)
        self.pre_img = self.capture_main_display_gray("afterpaste")
        self.press_keys(self.startKey)
        time.sleep(1)
        self.post_img = self.capture_main_display_gray("afterstart")
        points = self.find_max_diff_centers(self.pre_img, self.post_img)
        
        iupac_name = ""
        for point in points:
            self.move_and_click(point[0], point[1])
            # self.move_and_click(self.max_diff_center_x, self.max_diff_center_y)
            time.sleep(0.5)
            self.press_keys(self.copyKey)
            time.sleep(0.01)
            iupac_name = self.get_clipboard_text()
            if iupac_name != smiles:
                break
            self.move_and_click(point[0], point[1]-10)
            # self.move_and_click(self.max_diff_center_x, self.max_diff_center_y)
            time.sleep(0.5)
            self.press_keys(self.copyKey)
            time.sleep(0.01)
            iupac_name = self.get_clipboard_text()
            if iupac_name != smiles:
                break
            self.move_and_click(point[0], point[1]+10)
            # self.move_and_click(self.max_diff_center_x, self.max_diff_center_y)
            time.sleep(0.5)
            self.press_keys(self.copyKey)
            time.sleep(0.01)
            iupac_name = self.get_clipboard_text()
            if iupac_name != smiles:
                break
        
        self.press_keys(["command", "a"])
        self.press_keys(["backspace"])
        return iupac_name




def wait_until_space_up():
    """
    Block until the space bar is released (if currently pressed).
    Uses Quartz key state so it does not require sudo (only normal Accessibility).
    """
    while not is_space_pressed():
        time.sleep(0.01)

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto IU2 SM")
        self.resize(360, 180)

        self.smiles_file = ""

        layout = QVBoxLayout()
        self.prompt = QLabel("请输入 smiles 文件路径。按下提交后切换回 ChemDraw，创建空白文档并按空格开始。")
        self.input = QLineEdit()
        self.browse_btn = QPushButton("浏览...")
        self.submit_button = QPushButton("提交")
        layout.addWidget(self.prompt)
        layout.addWidget(self.input)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

        self.browse_btn.clicked.connect(self.browse_file)
        self.submit_button.clicked.connect(self.submit)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 smiles 文件", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            self.input.setText(file_path)

    def submit(self):
        self.smiles_file = self.input.text().strip()
        if not self.smiles_file:
            self.prompt.setText(f"请输入 smiles 文件路径。按下submit后切换回 ChemDraw，创建空白文档并按空格开始，结果将写入 {self.smiles_file}.json")
            return
        if not os.path.exists(self.smiles_file):
            self.prompt.setText(f"文件不存在: {self.smiles_file}")
            return

        # self.prompt.setText(
        #     f"请切换回 ChemDraw，空白文档按空格开始，结果将写入 {self.smiles_file}.json"
        # )

        try:
            self.run_pipeline(self.smiles_file)
            self.prompt.setText(f"结果已保存至 {self.smiles_file}.json")
        except Exception as exc:
            self.prompt.setText(f"出错: {exc}")

    def run_pipeline(self, smiles_file):
        wait_until_space_up()
        cdw = chem_draw_worker()
        with open(smiles_file, "r") as f:
            smiles_list = [line.strip() for line in f if line.strip()]

        data = []
        for smiles in smiles_list:
            data.append({
                "smiles": smiles,
                "iupac_name": cdw.draw_chem(smiles)
            })

        output_path = f"{smiles_file}.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=4)


if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(qt_app.exec())