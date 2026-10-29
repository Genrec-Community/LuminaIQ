/* eslint-disable @next/next/no-img-element -- Unsplash's CDN resizes; no optimizer round trip needed. */
import type { Photo as PhotoData } from '@/data/site';

const src = (id: string, w: number) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=68`;

type Props = {
  photo: PhotoData;
  sizes: string;
  ratio?: string; // CSS aspect-ratio of the frame
  eager?: boolean;
  className?: string;
};

/** A duotoned stock photo (forest on paper). If the image fails, the frame shows grid paper. */
export function Photo({ photo, sizes, ratio = '4 / 5', eager, className }: Props) {
  const widths = [480, 768, 1080, 1440, 1920];
  return (
    <figure className={`photo ${className ?? ''}`} style={{ aspectRatio: ratio }}>
      <img
        src={src(photo.id, 1080)}
        srcSet={widths.map((w) => `${src(photo.id, w)} ${w}w`).join(', ')}
        sizes={sizes}
        alt={photo.alt}
        width={1080}
        height={1350}
        loading={eager ? 'eager' : 'lazy'}
        fetchPriority={eager ? 'high' : 'auto'}
        decoding="async"
      />
    </figure>
  );
}
