# Mapa automático de tu Notion

Cada 6 horas, GitHub lee todas tus bases de datos de Notion, recoge el campo **Lugar**,
lo convierte en coordenadas y actualiza un mapa web con todos los lugares juntos.
Funciona con el campo de tipo Place, texto, título, select y multiselect.

## Puesta en marcha (≈10 min)

### 1. Crear la integración en Notion
1. Ve a https://www.notion.so/profile/integrations → **Nueva integración** (tipo interna).
2. Copia el **token secreto** (empieza por `ntn_` o `secret_`).
3. En Notion, abre la página raíz que contiene tus bases de datos → **⋯ → Conexiones** → añade la integración.
   Al compartir una página, sus subpáginas y bases de datos quedan accesibles. Las que estén fuera de esa página hay que compartirlas aparte.
   La integración solo ve lo que le compartes.

### 2. Subir el proyecto a GitHub
1. Crea un repositorio nuevo en GitHub y sube el contenido de esta carpeta (incluida `.github/`).
2. En **Settings → Secrets and variables → Actions → New repository secret**:
   nombre `NOTION_TOKEN`, valor el token del paso 1.
3. En **Settings → Actions → General → Workflow permissions**: marca *Read and write permissions*.

### 3. Activar el mapa
1. Pestaña **Actions** → *Actualizar mapa* → **Run workflow** (primera ejecución manual).
   Mira el log: te dice cuántas bases con «Lugar» encontró y qué lugares no pudo localizar.
2. **Settings → Pages** → Source: *Deploy from a branch* → rama `main`, carpeta `/docs`.
3. Tu mapa estará en `https://TU-USUARIO.github.io/NOMBRE-REPO/`.

### 4. (Opcional) Verlo dentro de Notion
En cualquier página de Notion escribe `/embed` y pega esa URL.

## Cómo se actualiza
- Automático cada 6 horas (cambia el `cron` en `.github/workflows/update-map.yml`).
- Al instante: Actions → *Actualizar mapa* → Run workflow.
- Los lugares nuevos se geocodifican una sola vez y se guardan en `geocache.json`.

## Privacidad: léelo antes de publicar
GitHub Pages es **público** (en repos gratuitos todo el mundo con el enlace verá tus pines, títulos y enlaces a Notion;
las páginas de Notion en sí siguen privadas). Opciones:
- Aceptarlo si los lugares no son sensibles.
- Repo privado + Pages: requiere plan de pago de GitHub, y aun así el sitio puede ser público según el plan.
- Alojar la carpeta `docs/` en Cloudflare Pages con Cloudflare Access (login por email), que tiene plan gratuito.
No publiques direcciones de tu casa o datos de terceros sin pensarlo.

## Problemas típicos
- **«no se encontró ninguna base con ese campo»**: no compartiste las páginas con la integración, o el campo no se llama exactamente «Lugar» (cámbialo con `PROPERTY_NAME` en el workflow).
- **Lugares «no localizados»**: texto demasiado vago («casa de Juan»). Añade ciudad o país: «Bar Pepe, Alcalá de Henares».
- **El workflow se desactiva solo**: GitHub pausa los workflows programados tras 60 días sin actividad en el repo. Si pasa, reactívalo en Actions.
- Geocodificación con OpenStreetMap (Nominatim): ~1 lugar por segundo; la primera ejecución con muchos lugares tardará.
