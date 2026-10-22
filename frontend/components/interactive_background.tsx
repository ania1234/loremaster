"use client";

import { useEffect, useRef } from "react";
import { mountEngraverRipple } from "./engraver_ripple";

export function InteractiveBackground() {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvas.current) return mountEngraverRipple(canvas.current);
  }, []);

  return <canvas ref={canvas} className="engraver-background" aria-hidden="true" />;
}
