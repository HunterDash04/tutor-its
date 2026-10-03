# Aplicación web — Tutor Inteligente de Programación

## 1. Probar en tu PC (sin internet ni base de datos externa)

```
py -m pip install streamlit sqlalchemy altair
py crear_docente.py          # crea tu cuenta docente en la base local (its_local.db)
py -m streamlit run app.py   # se abre en el navegador: http://localhost:8501
```

En tu PC la app usa SQLite automáticamente. Crea una cuenta de estudiante desde la pantalla de inicio y prueba el flujo completo.

## 2. Publicarla en internet

Necesitas tus 3 cuentas: GitHub, Neon y Streamlit Community Cloud.

### 2.1 Neon (base de datos donde se guardan cuentas y avances)
1. En Neon, crea un proyecto (por ejemplo `tutor-its`) en la región más cercana (por ejemplo, US East).
2. En el panel del proyecto pulsa **Connect** y copia la **connection string**. Empieza con `postgresql://` y termina con `?sslmode=require...`.
3. No la pegues en ningún archivo del proyecto: va solo en los secretos de Streamlit (paso 2.3).

### 2.2 GitHub (código)
1. Crea un repositorio nuevo (puede ser **privado**), por ejemplo `tutor-its`, sin README.
2. La forma más simple, sin instalar nada: en la página del repositorio elige **Add file → Upload files**. Arrastra estos archivos y carpetas desde `BD_MODELO`:
   - `app.py`, `crear_docente.py`, `requirements.txt`, `.gitignore`, `LEEME_APP.md`
   - `motor_recomendacion.py`, `motor_recomendacion.pkl`, `topicos_codeforces.py`, `reglas_diagnostico.py`, `diagnostico_dominio_reglas.py`
   - las carpetas `its_web/`, `.streamlit/` (solo `config.toml`), `resultados_modelo_a/`, `resultados_recomendador/`
   - opcional, para que el repositorio sea reproducible: los scripts del pipeline (`construir_dataset_estudiante.py`, `entrenar_modelo_a.py`, `descargar_codeforces.py`, `entrenar_recomendador.py`, `evaluar_metricas.py`, `simulador_consola.py`, `LEEME_PIPELINE.md`)
   - **NO subas** la carpeta `datasets/`, los `.csv` de la raíz, los `.docx` ni `its_local.db`.
3. Escribe el mensaje del commit (por ejemplo "Versión inicial") y pulsa **Commit changes**. El commit queda a tu nombre.

Si prefieres usar git desde la terminal, configura antes tu identidad:
`git config --global user.name "Tu Nombre"` y `git config --global user.email "tu-correo"`.

### 2.3 Streamlit Community Cloud (publicación)
1. Pulsa **Create app**, elige *Deploy a public app from GitHub* y completa: tu repositorio, rama `main` y archivo principal `app.py`.
2. Abre **Advanced settings**:
   - **Python version:** 3.13
   - **Secrets:** pega esto con tus datos reales:
     ```toml
     DATABASE_URL = "postgresql://...la cadena copiada de Neon..."

     [docente]
     usuario = "tu_usuario_docente"
     clave = "una-contraseña-segura"
     nombre = "Tu nombre"
     ```
     La cuenta docente se crea sola la primera vez que se abre la app.
3. Pulsa **Deploy**. La primera vez tarda unos minutos mientras instala las librerías.
4. Comparte la URL `https://<nombre>.streamlit.app`.

## Notas
- **Contraseñas:** se guardan cifradas (PBKDF2-SHA256); nadie, ni el docente, puede verlas.
- **Si la app se reinicia:** los datos no se pierden porque viven en Neon, no dentro de la app.
- **Base inactiva:** Neon suspende la base cuando nadie la usa. El primer acceso después de un rato puede tardar unos segundos más.
- **Si reentrenas el recomendador** (`entrenar_recomendador.py`): vuelve a subir `motor_recomendacion.pkl` al repositorio y la app se actualiza sola.
