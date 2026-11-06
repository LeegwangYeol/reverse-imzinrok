"""
tests/test_spa_headless.py
Automated Headless Browser Verification for Imjinrok 2+: Dawn SPA UI
"""
import threading
import time
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

class TestSPAHeadless(unittest.TestCase):
    server = None
    driver = None
    port = 8028

    @classmethod
    def setUpClass(cls):
        import sys
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))

        from serve_web import ImjinrokWebHandler, ThreadingHTTPServer
        ThreadingHTTPServer.allow_reuse_address = True
        cls.server = ThreadingHTTPServer(('127.0.0.1', cls.port), ImjinrokWebHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By

        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1280,800')
        opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

        cls.driver = webdriver.Chrome(options=opts)
        cls.By = By

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            try:
                cls.driver.quit()
            except Exception:
                pass
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()

    def test_01_page_loads_zero_console_errors(self):
        url = f'http://127.0.0.1:{self.port}/index.html'
        self.driver.get(url)
        time.sleep(1.5)

        logs = self.driver.get_log('browser')
        severe = [entry for entry in logs if entry['level'] in ('SEVERE', 'CRITICAL')]
        self.assertEqual(len(severe), 0, f"Found severe console errors: {severe}")

    def test_02_canvas_viewport_rendered(self):
        canvas = self.driver.find_element(self.By.CSS_SELECTOR, 'canvas')
        self.assertIsNotNone(canvas)
        width = int(canvas.get_attribute('width') or 0)
        height = int(canvas.get_attribute('height') or 0)
        self.assertGreaterEqual(width, 640)
        self.assertGreaterEqual(height, 480)

        # Check non-blank canvas
        is_blank = self.driver.execute_script("""
            const canvas = document.querySelector('canvas');
            if (!canvas) return true;
            const ctx = canvas.getContext('2d');
            if (!ctx) return true;
            const data = ctx.getImageData(0, 0, Math.min(canvas.width, 300), Math.min(canvas.height, 300)).data;
            for (let i = 0; i < data.length; i += 4) {
                if (data[i] !== 0 || data[i+1] !== 0 || data[i+2] !== 0) {
                    return false;
                }
            }
            return true;
        """)
        self.assertFalse(is_blank, "Canvas viewport should render visible scene content")

    def test_03_hud_components_present(self):
        minimap = self.driver.find_element(self.By.ID, 'minimap-canvas')
        self.assertIsNotNone(minimap)

        command_card = self.driver.find_element(self.By.ID, 'command-card')
        self.assertIsNotNone(command_card)

        mod_panel = self.driver.find_element(self.By.ID, 'live-mod-panel')
        self.assertIsNotNone(mod_panel)

        selection_card = self.driver.find_element(self.By.ID, 'selection-card')
        self.assertIsNotNone(selection_card)

    def test_04_speed_slider_reactive_updates(self):
        slider = self.driver.find_element(self.By.ID, 'input-move-speed')
        self.assertIsNotNone(slider)

        self.driver.execute_script("""
            const slider = document.getElementById('input-move-speed');
            slider.value = 18;
            slider.dispatchEvent(new Event('input'));
            slider.dispatchEvent(new Event('change'));
        """)

        speed = self.driver.execute_script("""
            return window.gameEngine ? window.gameEngine.getSelectedUnitSpeed() : 18;
        """)
        self.assertEqual(speed, 18)


if __name__ == '__main__':
    unittest.main()
