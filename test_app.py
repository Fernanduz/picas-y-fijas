import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

import app


class APITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, data=None, token=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        conn.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def test_juego_completo(self):
        self.assertEqual(self.request("GET", "/juego")[0], 401)
        _, login = self.request("POST", "/login", {"usuario": "Ana"})
        token = login["token"]
        status, juego = self.request("POST", "/juego", token=token)
        self.assertEqual((status, juego["estado"]), (201, "sin completar"))
        path = "/juego/" + juego["id"]
        self.assertNotIn("secreto", juego)
        self.assertEqual(self.request("PUT", path, token=token)[1]["estado"], "en juego")
        self.assertEqual(self.request("PUT", path, token=token)[0], 409)
        self.assertEqual(self.request("POST", path + "/jugar", {"numero": "1123"}, token)[0], 400)
        secreto = app.juegos[juego["id"]]["secreto"]
        status, resultado = self.request("POST", path + "/jugar", {"numero": secreto}, token)
        self.assertEqual((status, resultado["resultado"]["fijas"]), (200, 4))
        self.assertEqual(self.request("GET", path, token=token)[1]["estado"], "terminado")
        self.assertEqual(self.request("POST", path + "/jugar", {"numero": secreto}, token)[0], 409)
        self.assertEqual(self.request("GET", "/juego", token=token)[0], 200)

    def test_picas_y_fijas(self):
        self.assertEqual(app.evaluar("0123", "0324"), (1, 2))
        self.assertEqual(app.evaluar("0123", "0123"), (0, 4))

    def test_pagina_web(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request("GET", "/")
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        self.assertIn("text/html", response.getheader("Content-Type"))
        self.assertIn("Picas y Fijas", response.read().decode("utf-8"))
        conn.close()


if __name__ == "__main__":
    unittest.main()
