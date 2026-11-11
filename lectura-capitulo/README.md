# Lectura del capítulo (BNI Connect)

`srv.py` escucha solo en `127.0.0.1:8765` (configurable con `BNI_SRV_HOST` / `BNI_SRV_PORT`) y recibe perfiles que un script del navegador le manda por query `?d=`. Guarda `m_<id>.json` en `BNI_DATA_DIR`.

`parse.py` junta `roster.json` y esos perfiles en `members.json`. Los cargos se leen de `roles.json` (hay un ejemplo en `examples/`). El nombre del capítulo sale de `BNI_CHAPTER`.

Los `m_*.json`, el roster y `members.json` reales no se versionan: son datos personales de los miembros.
