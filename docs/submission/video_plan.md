# Plan del video narrado (sin editor)

Receta: una toma de audio por bloque del guion (`demo_script.md`); ffmpeg ajusta cada toma a su imagen
o clip con la duración exacta de la toma, normaliza el volumen (`loudnorm`) y concatena los bloques.
**La voz la graba el mantenedor**; aquí solo están las tomas de pantalla, los nombres de archivo y los
comandos. Todo vive en `lake/video/` (fuera de git).

## Estructura de carpetas

```
lake/video/
  audio/   01_gancho.wav  02_top10.wav  03_porque.wav  04_confianza.wav  05_cierre.wav
  shots/   01_gancho.png  02_top10.png  03a_serie_anillo.png  03b_chat.png  04_confianza.png
           05a_temporal.mov  05b_historia.png
  build/   (segmentos intermedios)
  radar_demo.mp4
```

## Lista de tomas (coincide con el guion)

| Bloque | Audio (≈ duración) | Toma | Cómo se captura |
|---|---|---|---|
| 1. Gancho | `01_gancho.wav` (30 s) | `01_gancho.png`: parte superior del sitio público (título, frescura, perfil `full`) | Chrome con ventana visible a 1920x1080, captura de ventana (⇧⌘4, espacio) |
| 2. Top 10 | `02_top10.wav` (75 s) | `02_top10.png`: las tarjetas #1-#3 con sus fichas | igual, con la página desplazada a las tarjetas |
| 3. Por qué y cómo adaptarlo | `03_porque.wav` (75 s) | `03a_serie_anillo.png` (serie diaria y anillo de la historia 1 de `stories.md`) y `03b_chat.png` (respuesta del chat y traza) | captura después de una pregunta real; el chat gasta crédito y tiene límite de 10 cada 10 min por IP |
| 4. Confianza | `04_confianza.wav` (60 s) | `04_confianza.png`: tabla de evidencia (backtest, P/R, costo, fuentes) con los números ya llenos | captura de la diapositiva o de `submission_text.md` renderizado |
| 5. Cierre | `05_cierre.wav` (60 s) | `05a_temporal.mov` (barrido de las 13 semanas, ~35 s) y `05b_historia.png` (vista de historia del #1) | **Chrome con ventana visible, nunca headless** (headless no captura las capas WebGL): servir `lake/views` en local, abrir `temporal.html`, grabar la ventana con `screencapture -v -V 35 lake/video/shots/05a_temporal.mov` (macOS) mientras corre el play |

Las duraciones son objetivos; ffmpeg usa la duración real de cada toma.

## Comandos

Bloques de una sola imagen (1, 2 y 4): la imagen dura lo que dure su toma.

```bash
cd lake/video
mkdir -p build
seg_still() {  # seg_still <png> <wav> <salida.mp4>
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$2")
  ffmpeg -y -loop 1 -framerate 30 -t "$dur" -i "$1" -i "$2" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p" \
    -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 \
    -c:v libx264 -tune stillimage -preset medium -crf 20 -c:a aac -b:a 192k -shortest "$3"
}
seg_still shots/01_gancho.png    audio/01_gancho.wav    build/01.mp4
seg_still shots/02_top10.png     audio/02_top10.wav     build/02.mp4
seg_still shots/04_confianza.png audio/04_confianza.wav build/04.mp4
```

Bloque 3: dos imágenes que se reparten la toma en partes iguales.

```bash
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 audio/03_porque.wav)
half=$(python3 -c "print($dur/2)")
ffmpeg -y -loop 1 -framerate 30 -t "$half" -i shots/03a_serie_anillo.png \
          -loop 1 -framerate 30 -t "$half" -i shots/03b_chat.png -i audio/03_porque.wav \
  -filter_complex "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[a];\
[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[b];\
[a][b]concat=n=2:v=1:a=0,format=yuv420p[v];[2:a]loudnorm=I=-16:TP=-1.5:LRA=11[aud]" \
  -map "[v]" -map "[aud]" -ar 48000 -c:v libx264 -preset medium -crf 20 -c:a aac -b:a 192k \
  -shortest build/03.mp4
```

Bloque 5: el clip del barrido, cortado o repetido hasta llenar la toma menos 15 s, y luego la imagen
de la historia durante los 15 s finales.

```bash
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 audio/05_cierre.wav)
clip=$(python3 -c "print(max($dur-15, 1))")
ffmpeg -y -stream_loop -1 -t "$clip" -i shots/05a_temporal.mov \
          -loop 1 -framerate 30 -t 15 -i shots/05b_historia.png -i audio/05_cierre.wav \
  -filter_complex "[0:v]fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[a];\
[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[b];\
[a][b]concat=n=2:v=1:a=0,format=yuv420p[v];[2:a]loudnorm=I=-16:TP=-1.5:LRA=11[aud]" \
  -map "[v]" -map "[aud]" -ar 48000 -c:v libx264 -preset medium -crf 20 -c:a aac -b:a 192k \
  -shortest build/05.mp4
```

Unir los cinco bloques (mismos códecs y resolución, así que se copian sin recodificar):

```bash
printf "file '%s.mp4'\n" 01 02 03 04 05 > build/list.txt   # rutas relativas al archivo de lista
ffmpeg -y -f concat -safe 0 -i build/list.txt -c copy radar_demo.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 radar_demo.mp4   # objetivo: <= 300 s
```

## Comprobaciones antes de subir

- Duración total de 300 s o menos (`ffprobe`); si se pasa, regrabar la toma más larga, no acelerar.
- Escuchar el volumen: `loudnorm` deja cada bloque cerca de -16 LUFS, así que no hay saltos entre
  bloques.
- Ninguna captura muestra titulares, URLs de noticias ni nombres de personas: el sitio muestra ids de
  temas, no titulares. Si una captura del chat cita uno, recortarla.
- Los números que se dicen en el audio son los de `stories.md`, `status/WS9.md` y los reportes del
  momento de la grabación; los `[PENDIENTE]` se graban solo cuando llegan los números.
