# Plan del video narrado (sin editor)

Receta: una toma de audio por bloque del guion (`demo_script.md`); ffmpeg ajusta cada toma a su imagen
o clip con la duración exacta de la toma, normaliza el volumen (`loudnorm`) y concatena los bloques.
**La voz la graba el mantenedor**; aquí solo están las tomas de pantalla, los nombres de archivo y los
comandos. Todo vive en `lake/video/` (fuera de git).

## Estructura de carpetas

```
lake/video/
  audio/   01_gancho.wav  02_top10.wav  03_porque.wav  04_confianza.wav  05_cierre.wav
  shots/   01_gancho.png  02_top10.png  03a_lentes.mov  03b_chat.png  04_confianza.png
           05a_temporal.mov  05b_historia.png
  build/   (segmentos intermedios)
  radar_demo.mp4
```

## Lista de tomas (coincide con el guion)

Todas las tomas salen del sitio público en una sola pantalla: el top 10 a la izquierda, el grafo con
sus 8 lentes en el centro y la píldora del chat abajo a la derecha. Chrome con ventana visible, nunca
headless (headless no captura las capas WebGL), a 1440x900 como las capturas de ensayo de
`status/WS9.md`; ffmpeg las lleva a 1920x1080 con bandas.

| Bloque | Audio (≈ duración) | Toma | Cómo se captura |
|---|---|---|---|
| 1. Gancho | `01_gancho.wav` (30 s) | `01_gancho.png`: la vista inicial (título, frescura, top 10, grafo en la lente Radar, chat cerrado) | captura de ventana (⇧⌘4, espacio) |
| 2. Top 10 | `02_top10.wav` (75 s) | `02_top10.png`: la tarjeta #1 abierta con sus fichas medido / estimado, **Brief y Evidencia cerrados**, y el grafo en la lente Historia con el tema y sus vecinos nombrados | igual, después de un clic en la tarjeta #1 |
| 3. Por qué, cómo adaptarlo y las lentes | `03_porque.wav` (75 s) | `03a_lentes.mov` (Radar → Momento → Puente → Comunidades → Novedad, unos 2 s cada una) y `03b_chat.png` (la respuesta a "¿Cuál es el ángulo para ejecutivos de LatAm esta semana?" con la línea "Decisión del radar: …", la línea de cobertura y la traza) | `screencapture -v -V 12 lake/video/shots/03a_lentes.mov` mientras se pulsan las lentes; el chat gasta crédito y tiene un límite de 10 preguntas cada 10 min por visitante |
| 4. Confianza | `04_confianza.wav` (60 s) | `04_confianza.png`: la respuesta calibrada a "¿Cuánto puedo confiar en el radar? ¿Hay backtest?" (la línea del código con 29,2%, el intervalo y "Úsalo como señal temprana, no como garantía"), o el panel **Confianza** abierto | captura después de la pregunta; el panel no gasta crédito |
| 5. Cierre | `05_cierre.wav` (60 s) | `05a_temporal.mov` (pantalla completa, ▶ Reproducir 13 semanas, ~35 s) y `05b_historia.png` (la tarjeta #1 en la lente Historia) | `screencapture -v -V 35 lake/video/shots/05a_temporal.mov` mientras corre el play |

Si algo no se puede grabar en vivo, `docs/media/` tiene GIF y capturas del sitio ya revisados (sin
titulares, URLs ni nombres de personas): `radar-lenses.gif` para el bloque 3, `radar-trust.png` para
el 4 y `radar-play.gif` para el 5. Para el video, mejor grabar `.mov`: los GIF tienen 64 a 128 colores.

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

Bloque 3: el clip de las lentes, repetido hasta llenar la primera mitad de la toma, y luego la
imagen del chat.

```bash
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 audio/03_porque.wav)
half=$(python3 -c "print($dur/2)")
ffmpeg -y -stream_loop -1 -t "$half" -i shots/03a_lentes.mov \
          -loop 1 -framerate 30 -t "$half" -i shots/03b_chat.png -i audio/03_porque.wav \
  -filter_complex "[0:v]fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[a];\
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
- Ninguna toma muestra titulares, URLs de noticias ni nombres de personas. El sitio sí los muestra en
  **Evidencia** y en las respuestas del chat sobre artículos: dejar Evidencia cerrada, no preguntar
  por artículos, y revisar cuadro a cuadro las tomas del chat antes de montar. Si alguna cita uno,
  recortarla o regrabarla.
- Los números que se dicen en el audio son los de `stories.md`, `status/WS9.md`,
  `status/WS0-agents.md` y los reportes de `reports/` del momento de la grabación.
