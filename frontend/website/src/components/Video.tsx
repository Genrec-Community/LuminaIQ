'use client';
/* eslint-disable @next/next/no-img-element -- YouTube thumbnail */
import { useEffect, useRef, useState } from 'react';

/**
 * The walkthrough plays by itself (muted, looping) as soon as it scrolls near the viewport, which is
 * the only kind of autoplay browsers allow. "Sound on" unmutes through the YouTube iframe API.
 * Under reduced motion it waits for a click instead.
 */
export function Video({ id, title }: { id: string; title: string }) {
  const box = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const [play, setPlay] = useState(false);
  const [muted, setMuted] = useState(true);

  useEffect(() => {
    const el = box.current;
    if (!el || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setPlay(true);
          io.disconnect();
        }
      },
      { rootMargin: '300px 0px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const command = (func: string) =>
    frame.current?.contentWindow?.postMessage(JSON.stringify({ event: 'command', func, args: [] }), '*');

  const toggleSound = () => {
    if (muted) {
      command('unMute');
      command('playVideo');
    } else command('mute');
    setMuted((m) => !m);
  };

  const src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&loop=1&playlist=${id}&playsinline=1&rel=0&modestbranding=1&enablejsapi=1`;

  return (
    <div className="video" ref={box}>
      {play ? (
        <>
          <iframe
            ref={frame}
            src={src}
            title={title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
          <button type="button" className="video__sound" onClick={toggleSound} aria-pressed={!muted}>
            <span className="video__eq" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {muted ? 'Sound on' : 'Sound off'}
          </button>
        </>
      ) : (
        <button type="button" className="video__poster" onClick={() => setPlay(true)}>
          <img
            src={`https://i.ytimg.com/vi/${id}/maxresdefault.jpg`}
            alt=""
            width={1280}
            height={720}
            loading="lazy"
            decoding="async"
            onError={(e) => {
              const img = e.currentTarget as HTMLImageElement;
              if (!img.src.includes('hqdefault')) img.src = `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
              else img.style.display = 'none';
            }}
          />
          <span className="video__play">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M8 5.5v13l11-6.5z" fill="currentColor" />
            </svg>
            <span>Play the walkthrough</span>
          </span>
        </button>
      )}
    </div>
  );
}
