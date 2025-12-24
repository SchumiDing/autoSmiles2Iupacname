from utils import *
import time

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
        time.sleep(0.01)
        self.pre_img = self.capture_main_display_gray("afterpaste")
        self.press_keys(self.startKey)
        time.sleep(1)
        self.post_img = self.capture_main_display_gray("afterstart")
        self.find_max_diff_center(self.pre_img, self.post_img)
        self.move_and_click(self.max_diff_center_x, self.max_diff_center_y)
        # self.move_and_click(self.max_diff_center_x, self.max_diff_center_y)
        self.press_keys(self.copyKey)
        time.sleep(0.5)
        iupac_name = self.get_clipboard_text()
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
        

if __name__=="__main__":
    wait_until_space_up()
    # smiles = "CC1=C2C(C(=O)C3(C(CC4C(C3C(C(C2(C)C)(CC1OC(=O)C5=CC=CC=C5)O)OC(=O)C6=CC=CC=C6)(CO4)OC(=O)C)O)C)OC(=O)C7=CC=CC=C7"
    cdw = chem_draw_worker()
    smiles_List = [
        "CC1=C2C(C(=O)C3(C(CC4C(C3C(C(C2(C)C)(CC1OC(=O)C5=CC=CC=C5)O)OC(=O)C6=CC=CC=C6)(CO4)OC(=O)C)O)C)OC(=O)C7=CC=CC=C7",
        "CC1=C2C(C(=O)C3(C(CC4C(C3C(C(C2(C)C)(CC1OC(=O)C5=CC=CC=C5)O)OC(=O)C6=CC=CC=C6)(CO4)OC(=O)C)O)C)OC(=O)C7=CC=CC=C7",
    ]
    data = []
    for smiles in smiles_List:
        data.append({
            "smiles": smiles,
            "iupac_name": cdw.draw_chem(smiles)
        })
    import json
    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)
    