# Cruce WhatsApp × capítulo

- `add.py`: incorpora lotes de contactos a `wa_personal_contacts.json`.
- `build.py`: primera versión del Excel de cruces. Lee las listas de `cruces_manual.json`.
- `build2.py`: versión actual. Conserva cruces previos, agrega los de `cruces_manual_nuevos.json`, pestaña de prospectos (`prospectos_vilar.json`) y pasteles. Omite identificadores y menciones de FIEL en los perfiles.

Copia los JSON de `examples/*.ejemplo.json` a `BNI_DATA_DIR` (sin el sufijo `.ejemplo`) para correr una demo. Los archivos de datos reales están en `.gitignore`.
