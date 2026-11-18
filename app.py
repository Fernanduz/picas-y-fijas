"""API REST de Picas y Fijas, usando únicamente la biblioteca estándar."""

import json
import re
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

usuarios = {}
juegos = {}
lock = threading.RLock()


def estado(juego):
    if not juego["jugador"]:
        return "sin completar"
    return "terminado" if juego["terminado"] else "en juego"


def publico(juego):
    return {
        "id": juego["id"],
        "jugador": juego["jugador"],
        "estado": estado(juego),
        "intentos": juego["intentos"],
    }


def evaluar(secreto, intento):
    fijas = sum(a == b for a, b in zip(secreto, intento))
    return len(set(secreto) & set(intento)) - fijas, fijas


class Handler(BaseHTTPRequestHandler):
    def responder(self, codigo, datos):
        contenido = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def cuerpo(self):
        try:
            longitud = int(self.headers.get("Content-Length", "0"))
            if longitud < 0 or longitud > 16384:
                raise ValueError
            datos = json.loads(self.rfile.read(longitud) or b"{}")
            if not isinstance(datos, dict):
                raise ValueError
            return datos
        except (ValueError, UnicodeDecodeError):
            return None

    def usuario(self):
        encabezado = self.headers.get("Authorization", "")
        if not encabezado.startswith("Bearer "):
            return None
        return usuarios.get(encabezado[7:])

    def procesar(self):
        ruta = urlsplit(self.path).path
        partes = [p for p in ruta.split("/") if p]
        metodo = self.command

        with lock:
            if metodo == "GET" and ruta == "/":
                contenido = Path(__file__).with_name("index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(contenido)))
                self.end_headers()
                self.wfile.write(contenido)
                return

            if metodo == "POST" and ruta == "/login":
                datos = self.cuerpo()
                nombre = datos.get("usuario") if datos is not None else None
                if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 50:
                    return self.responder(400, {"error": "Indica un usuario de 1 a 50 caracteres."})
                token = secrets.token_urlsafe(32)
                usuarios[token] = nombre.strip()
                return self.responder(200, {"usuario": nombre.strip(), "token": token})

            if not partes or partes[0] != "juego" or len(partes) > 3:
                return self.responder(404, {"error": "Ruta no encontrada."})

            usuario = self.usuario()
            if not usuario:
                return self.responder(401, {"error": "Envía un token válido en Authorization: Bearer <token>."})

            if len(partes) == 1:
                if metodo == "POST":
                    identificador = str(uuid.uuid4())
                    juegos[identificador] = {
                        "id": identificador, "creador": usuario, "jugador": None,
                        "secreto": "".join(secrets.SystemRandom().sample("0123456789", 4)),
                        "intentos": [], "terminado": False,
                    }
                    return self.responder(201, publico(juegos[identificador]))
                if metodo == "GET":
                    return self.responder(200, [publico(j) for j in juegos.values()])
                return self.responder(405, {"error": "Método no permitido."})

            juego = juegos.get(partes[1])
            if not juego:
                return self.responder(404, {"error": "Partida no encontrada."})
            if len(partes) == 2:
                if metodo == "GET":
                    return self.responder(200, publico(juego))
                if metodo == "PUT":
                    if juego["jugador"]:
                        return self.responder(409, {"error": "La partida ya tiene jugador."})
                    juego["jugador"] = usuario
                    return self.responder(200, publico(juego))
                return self.responder(405, {"error": "Método no permitido."})

            if partes[2] != "jugar":
                return self.responder(404, {"error": "Ruta no encontrada."})
            if metodo != "POST":
                return self.responder(405, {"error": "Método no permitido."})
            if juego["jugador"] != usuario:
                return self.responder(403, {"error": "Debes unirte a esta partida para jugar."})
            if juego["terminado"]:
                return self.responder(409, {"error": "La partida ya terminó."})
            datos = self.cuerpo()
            intento = datos.get("numero") if datos is not None else None
            if not isinstance(intento, str) or not re.fullmatch(r"[0-9]{4}", intento) or len(set(intento)) != 4:
                return self.responder(400, {"error": "El número debe ser una cadena de 4 cifras diferentes."})
            picas, fijas = evaluar(juego["secreto"], intento)
            resultado = {"numero": intento, "picas": picas, "fijas": fijas}
            juego["intentos"].append(resultado)
            juego["terminado"] = fijas == 4
            return self.responder(200, {"resultado": resultado, "juego": publico(juego)})

    do_GET = procesar
    do_POST = procesar
    do_PUT = procesar


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
