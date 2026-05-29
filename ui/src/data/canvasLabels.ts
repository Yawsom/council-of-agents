import type { ForceNode } from "./graphToForce";

export function wrapCanvasText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number
): string[] {
  const words = text.replace(/\s+/g, " ").trim().split(" ");
  if (!words.length) return [];
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const test = current ? `${current} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && current) {
      lines.push(current);
      current = word;
    } else {
      current = test;
    }
  }
  if (current) lines.push(current);
  return lines;
}

export function drawNodeLabel(
  ctx: CanvasRenderingContext2D,
  node: ForceNode,
  x: number,
  y: number,
  nodeRadius: number,
  globalScale: number,
  options: { dimmed: boolean; highlighted: boolean; showLabels: boolean }
): void {
  if (!options.showLabels) return;

  const labelText = options.highlighted ? node.fullText : node.name;
  const maxWidth = options.highlighted ? 200 / globalScale : 160 / globalScale;
  const fontSize = Math.max(8, (options.highlighted ? 11 : 10) / globalScale);
  const lineHeight = fontSize * 1.25;
  const maxLines = options.highlighted ? 5 : 3;

  ctx.font = `500 ${fontSize}px "DM Sans", system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";

  const lines = wrapCanvasText(ctx, labelText, maxWidth).slice(0, maxLines);
  if (lines.length === 0) return;

  const startY = y + nodeRadius + 5 / globalScale;
  const blockHeight = lines.length * lineHeight + 4 / globalScale;
  const blockWidth =
    Math.max(...lines.map((l) => ctx.measureText(l).width), 20) + 8 / globalScale;

  ctx.fillStyle = options.dimmed
    ? "rgba(26, 20, 16, 0.55)"
    : "rgba(26, 20, 16, 0.82)";
  ctx.beginPath();
  const bx = x - blockWidth / 2;
  const by = startY - 2 / globalScale;
  const r = 3 / globalScale;
  ctx.roundRect(bx, by, blockWidth, blockHeight, r);
  ctx.fill();

  ctx.fillStyle = options.dimmed
    ? "rgba(201, 185, 154, 0.45)"
    : options.highlighted
      ? "#f4e8d4"
      : "#c9b89a";

  lines.forEach((line, i) => {
    ctx.fillText(line, x, startY + i * lineHeight);
  });

  if (node.kind === "claim" && node.status && !options.dimmed) {
    const tag = node.status;
    const tagW = ctx.measureText(tag).width + 6 / globalScale;
    ctx.font = `600 ${Math.max(7, 8 / globalScale)}px "DM Sans", sans-serif`;
    ctx.fillStyle = node.color;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    ctx.roundRect(x - tagW / 2, by - 10 / globalScale, tagW, 9 / globalScale, 2);
    ctx.fill();
    ctx.fillStyle = "#1a1410";
    ctx.fillText(tag, x, by - 9 / globalScale);
    ctx.globalAlpha = 1;
  }
}
