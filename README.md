# Picas y Fijas: API REST multijugador (1 contra 1)

API REST + JSON en Python, sin dependencias externas, desplegable en Kubernetes.

Cada jugador elige un **número secreto de cuatro cifras diferentes** (puede empezar por cero). Por turnos, cada uno intenta adivinar el número del rival:

- **Fija:** cifra correcta en la posición correcta.
- **Pica:** cifra correcta en una posición distinta.
- Empieza quien creó la partida. Gana el primero que consigue cuatro fijas; al terminar se revelan ambos números.

## Ejecutar y probar localmente

Requiere Python 3.10 o superior:

```bash
python app.py
python -m unittest -v
```

La API escucha en `http://localhost:8000`. Para jugar con botones, abre **http://localhost:8000/** en dos pestañas o navegadores distintos (un jugador en cada una). La página usa los mismos endpoints REST.

## Endpoints

Todas las respuestas son JSON. Salvo `/login`, las solicitudes requieren el encabezado `Authorization: Bearer TOKEN`.

| Método | Ruta | Cuerpo | Función |
|---|---|---|---|
| POST | `/login` | `{"usuario":"Ana"}` | Iniciar sesión; devuelve un token. |
| POST | `/juego` | `{"secreto":"1234"}` | Crear una partida con tu número secreto. Estado `sin completar`. |
| PUT | `/juego/{ID}` | `{"secreto":"5678"}` | Unirse como rival con tu número secreto. Estado `en juego`. |
| POST | `/juego/{ID}/jugar` | `{"numero":"0123"}` | Adivinar el número del rival en tu turno. |
| GET | `/juego/{ID}` | — | Consultar jugadores, estado, turno, ganador e intentos. |
| GET | `/juego` | — | Listar partidas. |

Los números se envían como **cadena** para conservar un posible cero inicial. Los números secretos solo se muestran cuando la partida termina.

Códigos de respuesta: `200` correcto, `201` partida creada, `400` número inválido, `401` sin token, `403` no eres jugador de la partida, `404` no existe, `405` método no permitido, `409` conflicto (no es tu turno, falta rival, partida completa o terminada).

## Despliegue en Kubernetes / Killercoda

La imagen se construye automáticamente con **GitHub Actions** (`.github/workflows/publicar-imagen.yml`): cada `git push` a `main` la publica en `ghcr.io/fernanduz/picas-y-fijas:1.0`.

En la terminal de Killercoda (playground de Kubernetes):

```bash
git clone https://github.com/Fernanduz/picas-y-fijas.git
cd picas-y-fijas
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/picas-y-fijas
kubectl get pods,svc
```

Si se publica una versión nueva de la imagen:

```bash
kubectl rollout restart deployment/picas-y-fijas
kubectl rollout status deployment/picas-y-fijas
```

### Probar la API con curl (dos jugadores)

```bash
BASE=http://$(kubectl get svc picas-y-fijas -o jsonpath='{.spec.clusterIP}')
login() { curl -s -X POST "$BASE/login" -H 'Content-Type: application/json' -d "{\"usuario\":\"$1\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])'; }
ANA=$(login Ana)
BETO=$(login Beto)
ID=$(curl -s -X POST "$BASE/juego" -H "Authorization: Bearer $ANA" -H 'Content-Type: application/json' -d '{"secreto":"1234"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -s -X PUT "$BASE/juego/$ID" -H "Authorization: Bearer $BETO" -H 'Content-Type: application/json' -d '{"secreto":"5678"}' | python3 -m json.tool
curl -s -X POST "$BASE/juego/$ID/jugar" -H "Authorization: Bearer $ANA" -H 'Content-Type: application/json' -d '{"numero":"5687"}' | python3 -m json.tool
curl -s -X POST "$BASE/juego/$ID/jugar" -H "Authorization: Bearer $BETO" -H 'Content-Type: application/json' -d '{"numero":"1234"}' | python3 -m json.tool
curl -s "$BASE/juego/$ID" -H "Authorization: Bearer $ANA" | python3 -m json.tool
curl -s "$BASE/juego" -H "Authorization: Bearer $ANA" | python3 -m json.tool
```

### Abrir la página web

```bash
kubectl port-forward --address 0.0.0.0 service/picas-y-fijas 8000:80
```

En el menú de Killercoda elige **Traffic / Ports**, puerto `8000`. Abre ese enlace en dos pestañas para jugar uno contra uno.

## Limitaciones

El inicio de sesión es demostrativo: acepta un nombre sin contraseña y entrega un token temporal; **no es autenticación segura para producción**. Usuarios, tokens y partidas viven en la memoria del proceso y desaparecen al reiniciarse. Por ello el despliegue usa **una sola réplica**: no aumentes las réplicas sin incorporar almacenamiento compartido (por ejemplo, Redis o una base de datos). No hay HTTPS configurado.