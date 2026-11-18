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

    def login(self, nombre):
        return self.request("POST", "/login", {"usuario": nombre})[1]["token"]

    def test_partida_uno_contra_uno(self):
        self.assertEqual(self.request("GET", "/juego")[0], 401)
        ana, beto, carla = self.login("Ana"), self.login("Beto"), self.login("Carla")

        # Crear partida con número secreto
        self.assertEqual(self.request("POST", "/juego", {"secreto": "1123"}, ana)[0], 400)
        status, juego = self.request("POST", "/juego", {"secreto": "1234"}, ana)
        self.assertEqual((status, juego["estado"], juego["jugadores"]), (201, "sin completar", ["Ana"]))
        self.assertNotIn("secretos", juego)
        path = "/juego/" + juego["id"]

        # No se puede jugar sin rival ni unirse a la propia partida
        self.assertEqual(self.request("POST", path + "/jugar", {"numero": "5678"}, ana)[0], 409)
        self.assertEqual(self.request("PUT", path, {"secreto": "5678"}, ana)[0], 409)

        # Beto se une con su número secreto
        status, juego = self.request("PUT", path, {"secreto": "5678"}, beto)
        self.assertEqual((status, juego["estado"], juego["turno"]), (200, "en juego", "Ana"))
        self.assertEqual(self.request("PUT", path, {"secreto": "9012"}, carla)[0], 409)

        # Turnos: empieza quien creó la partida
        self.assertEqual(self.request("POST", path + "/jugar", {"numero": "0123"}, beto)[0], 409)
        self.assertEqual(self.request("POST", path + "/jugar", {"numero": "0123"}, carla)[0], 403)
        status, r = self.request("POST", path + "/jugar", {"numero": "5687"}, ana)
        self.assertEqual((status, r["resultado"]["picas"], r["resultado"]["fijas"], r["juego"]["turno"]), (200, 2, 2, "Beto"))

        # Beto adivina el número de Ana y gana
        status, r = self.request("POST", path + "/jugar", {"numero": "1234"}, beto)
        self.assertEqual((status, r["resultado"]["fijas"]), (200, 4))
        status, juego = self.request("GET", path, token=ana)
        self.assertEqual((juego["estado"], juego["ganador"], juego["turno"]), ("terminado", "Beto", None))
        self.assertEqual(juego["secretos"], {"Ana": "1234", "Beto": "5678"})
        self.assertEqual(self.request("POST", path + "/jugar", {"numero": "5678"}, ana)[0], 409)
        self.assertEqual(self.request("GET", "/juego", token=ana)[0], 200)

    def test_cancelar_y_limpiar(self):
        ana, beto = self.login("Ana2"), self.login("Beto2")
        _, juego = self.request("POST", "/juego", {"secreto": "1234"}, ana)
        path = "/juego/" + juego["id"]
        self.assertEqual(self.request("DELETE", path, token=beto)[0], 403)
        self.assertEqual(self.request("DELETE", path, token=ana)[0], 200)
        self.assertEqual(self.request("GET", path, token=ana)[0], 404)

        # Una partida sin actividad se borra sola
        _, juego = self.request("POST", "/juego", {"secreto": "1234"}, ana)
        app.juegos[juego["id"]]["actualizada"] -= app.INACTIVIDAD + 1
        self.assertEqual(self.request("GET", "/juego/" + juego["id"], token=ana)[0], 404)

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