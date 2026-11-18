"""API REST de Picas y Fijas multijugador (1 contra 1), usando únicamente la biblioteca estándar."""

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


def numero_valido(numero):
    return isinstance(numero, str) and re.fullmatch(r"[0-9]{4}", numero) is not None and len(set(numero)) == 4


def estado(juego):
    if len(juego["jugadores"]) < 2:
        return "sin completar"
    return "terminado" if juego["ganador"] else "en juego"


def publico(juego):
    datos = {
        "id": juego["id"],
        "jugadores": juego["jugadores"],
        "estado": estado(juego),
        "turno": juego["turno"],
        "ganador": juego["ganador"],
        "intentos": juego["intentos"],
    }
    if juego["ganador"]:
        datos["secretos"] = juego["secretos"]
    return datos


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
            return {}

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
                nombre = self.cuerpo().get("usuario")
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

            # /juego
            if len(partes) == 1:
                if metodo == "POST":
                    secreto = self.cuerpo().get("secreto")
                    if not numero_valido(secreto):
                        return self.responder(400, {"error": "Tu número secreto debe tener 4 cifras diferentes."})
                    identificador = str(uuid.uuid4())
                    juegos[identificador] = {
                        "id": identificador, "jugadores": [usuario], "secretos": {usuario: secreto},
                        "turno": None, "ganador": None, "intentos": [],
                    }
                    return self.responder(201, publico(juegos[identificador]))
                if metodo == "GET":
                    return self.responder(200, [publico(j) for j in juegos.values()])
                return self.responder(405, {"error": "Método no permitido."})

            juego = juegos.get(partes[1])
            if not juego:
                return self.responder(404, {"error": "Partida no encontrada."})

            # /juego/{ID}
            if len(partes) == 2:
                if metodo == "GET":
                    return self.responder(200, publico(juego))
                if metodo == "PUT":
                    if usuario in juego["jugadores"]:
                        return self.responder(409, {"error": "Ya estás en esta partida."})
                    if len(juego["jugadores"]) == 2:
                        return self.responder(409, {"error": "La partida ya tiene dos jugadores."})
                    secreto = self.cuerpo().get("secreto")
                    if not numero_valido(secreto):
                        return self.responder(400, {"error": "Tu número secreto debe tener 4 cifras diferentes."})
                    juego["jugadores"].append(usuario)
                    juego["secretos"][usuario] = secreto
                    juego["turno"] = juego["jugadores"][0]
                    return self.responder(200, publico(juego))
                return self.responder(405, {"error": "Método no permitido."})

            # /juego/{ID}/jugar
            if partes[2] != "jugar":
                return self.responder(404, {"error": "Ruta no encontrada."})
            if metodo != "POST":
                return self.responder(405, {"error": "Método no permitido."})
            if usuario not in juego["jugadores"]:
                return self.responder(403, {"error": "No eres jugador de esta partida."})
            if estado(juego) == "sin completar":
                return self.responder(409, {"error": "Falta que un rival se una a la partida."})
            if estado(juego) == "terminado":
                return self.responder(409, {"error": "La partida ya terminó."})
            if juego["turno"] != usuario:
                return self.responder(409, {"error": f"No es tu turno; le toca a {juego['turno']}."})
            intento = self.cuerpo().get("numero")
            if not numero_valido(intento):
                return self.responder(400, {"error": "El número debe ser una cadena de 4 cifras diferentes."})
            rival = juego["jugadores"][1] if juego["jugadores"][0] == usuario else juego["jugadores"][0]
            picas, fijas = evaluar(juego["secretos"][rival], intento)
            resultado = {"jugador": usuario, "numero": intento, "picas": picas, "fijas": fijas}
            juego["intentos"].append(resultado)
            if fijas == 4:
                juego["ganador"] = usuario
                juego["turno"] = None
            else:
                juego["turno"] = rival
            return self.responder(200, {"resultado": resultado, "juego": publico(juego)})

    do_GET = procesar
    do_POST = procesar
    do_PUT = procesar
    do_DELETE = procesar
    do_PATCH = procesar


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()