"use client";

import { useEffect, useId, useRef } from "react";
import { ENGRAVER_GRID, ENGRAVER_TILE } from "./engraver_text";
import { mountEngraverRipple } from "./engraver_ripple";

export function InteractiveBackground() {
  const patternId = useId();
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvas.current) return mountEngraverRipple(canvas.current);
  }, []);

  return (
    <div className="engraver-background" aria-hidden="true">
      {/* Permanent server-rendered text; the transparent canvas adds effects only. */}
      <svg className="engraver-background-text" width="100%" height="100%">
        <defs>
          <pattern
            id={patternId}
            width={ENGRAVER_GRID.columns * ENGRAVER_GRID.cellWidth}
            height={ENGRAVER_GRID.rows * ENGRAVER_GRID.lineHeight}
            patternUnits="userSpaceOnUse"
          >
            {ENGRAVER_TILE.map((line, row) => (
              <text
                key={row}
                x={Array.from({ length: ENGRAVER_GRID.columns }, (_, column) =>
                  column * ENGRAVER_GRID.cellWidth + ENGRAVER_GRID.cellWidth / 2,
                ).join(" ")}
                y={row * ENGRAVER_GRID.lineHeight + ENGRAVER_GRID.baseline}
                fontSize={ENGRAVER_GRID.fontSize}
                textAnchor="middle"
                xmlSpace="preserve"
              >
                {line}
              </text>
            ))}
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#${patternId})`} />
      </svg>
      <canvas ref={canvas} className="engraver-background-canvas" />
    </div>
  );
}
