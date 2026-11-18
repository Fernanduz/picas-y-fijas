# Picas y Fijas: API REST

Juego individual contra la máquina, implementado en Python sin dependencias externas. El servidor genera una secuencia aleatoria de **cuatro cifras diferentes**; se permite que empiece por cero.

- **Fija:** cifra correcta en la posición correcta.
- **Pica:** cifra correcta en una posición distinta.
- La partida termina cuando se consiguen cuatro fijas.

## Ejecutar y probar localmente

Requiere Python 3.10 o superior:

```bash
python app.py
```

La API escucha en `http://localhost:8000`. Para ejecutar las pruebas:

```bash
python -m unittest -v
```

## Endpoints

Todas las respuestas son JSON. Salvo `/login`, las solicitudes requieren el encabezado `Authorization: Bearer TOKEN`.

| Método | Ruta | Función |
|---|---|---|
| POST | `/login` | Iniciar sesión con `{"usuario":"Ana"}`; devuelve un token. |
| POST | `/juego` | Crear una partida en estado `sin completar`. |
| PUT | `/juego/{ID}` | Unirse como jugador único; pasa a `en juego`. |
| POST | `/juego/{ID}/jugar` | Probar con `{"numero":"0123"}`. |
| GET | `/juego/{ID}` | Consultar estado e intentos. |
| GET | `/juego` | Listar partidas. |

El número debe enviarse como **cadena**, para conservar un posible cero inicial. Nunca se revela el número secreto en las respuestas. Cualquier usuario autenticado puede consultar y listar partidas; solo quien se une puede jugar. Quien crea la partida también puede unirse a ella. Un usuario diferente puede unirse primero, si la partida está libre.

Ejemplo en una terminal Bash, como la de Killercoda (requiere `curl` y `python3`):

```bash
BASE=http://localhost:8000
TOKEN=$(curl -s -X POST "$BASE/login" -H 'Content-Type: application/json' -d '{"usuario":"Ana"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
ID=$(curl -s -X POST "$BASE/juego" -H "Authorization: Bearer $TOKEN" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -X PUT "$BASE/juego/$ID" -H "Authorization: Bearer $TOKEN"
curl -X POST "$BASE/juego/$ID/jugar" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"numero":"0123"}'
curl "$BASE/juego/$ID" -H "Authorization: Bearer $TOKEN"
curl "$BASE/juego" -H "Authorization: Bearer $TOKEN"
```

## Despliegue en Kubernetes / Killercoda

El clúster necesita poder descargar la imagen del contenedor. Crea un repositorio público de imágenes, por ejemplo en Docker Hub, y sustituye `TU_USUARIO` por tu usuario:

```bash
docker build -t TU_USUARIO/picas-y-fijas:1.0 .
docker login
docker push TU_USUARIO/picas-y-fijas:1.0
```

En `k8s/deployment.yaml`, sustituye `REEMPLAZAR_USUARIO` por el mismo usuario. En la terminal de Killercoda, con este repositorio disponible:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/picas-y-fijas
kubectl get pods,svc
kubectl port-forward service/picas-y-fijas 8000:80
```

Deja el `port-forward` ejecutándose y, en otra terminal del mismo entorno, ejecuta los ejemplos de `curl`. Si el entorno no dispone de Docker, construye y publica la imagen desde otro equipo o sistema de construcción de imágenes; el clúster solamente necesita descargarla.

## Limitaciones

El inicio de sesión es demostrativo: acepta un nombre sin contraseña y entrega un token temporal; **no es autenticación segura para producción**. Usuarios, tokens y partidas viven en la memoria del proceso y desaparecen al reiniciarse. Por ello el despliegue usa **una sola réplica**: no aumentes las réplicas sin incorporar almacenamiento compartido y autenticación apropiada. No hay HTTPS configurado.
