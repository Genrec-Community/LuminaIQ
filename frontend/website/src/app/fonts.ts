import { Atkinson_Hyperlegible_Next, Newsreader } from 'next/font/google';

// Display: Newsreader (variable weight + optical size, with italics).
// Text and UI: Atkinson Hyperlegible Next, drawn by the Braille Institute so I, l and 1 never blur
// (in a plain grotesk the brand name reads as "LuminalQ").
export const display = Newsreader({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  variable: '--font-display',
  display: 'swap',
});

export const text = Atkinson_Hyperlegible_Next({
  subsets: ['latin'],
  variable: '--font-text',
  display: 'swap',
});
