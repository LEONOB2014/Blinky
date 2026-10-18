/** True when the browser can create a WebGL2 or WebGL context. */
export function browserHasGraphics(): boolean {
  try {
    const canvas = document.createElement("canvas");
    if (canvas.getContext("webgl2")) return true;
    return Boolean(canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/**
 * True when the browser can create a WebGL2 context. The temporal graph's renderer (cosmos.gl 3,
 * on luma.gl 9) needs WebGL2: a browser with only WebGL1 must get the fallback image, not a blank
 * canvas. The story graph (sigma.js) still runs on WebGL1, so it keeps `browserHasGraphics`.
 */
export function browserHasWebGL2(): boolean {
  try {
    return Boolean(document.createElement("canvas").getContext("webgl2"));
  } catch {
    return false;
  }
}
