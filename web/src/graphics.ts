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
