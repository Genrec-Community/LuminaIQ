'use client';
import { Engine } from '@/engine/next';
import { setupMotion } from '@/motion/setup';
import { site } from '@/data/site';

export function Motion() {
  return <Engine setup={setupMotion} pages={site.pages} />;
}
