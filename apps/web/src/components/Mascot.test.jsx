import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import Mascot from './Mascot.jsx';
import { LanguageProvider } from '../lib/language.jsx';
import { POSE_SETS } from '../lib/mascot.js';

const render = (node) => renderToStaticMarkup(<LanguageProvider>{node}</LanguageProvider>);

describe('Mascot poses', () => {
  it('starts every pose on its own base image inside the original-aspect frame', () => {
    for (const [mood, ratio] of [['wave', '400 / 517'], ['think', '400 / 499'], ['happy', '397 / 517'], ['front', '373 / 520']]) {
      const html = render(<Mascot mood={mood} interactive={false} />);
      expect(html, mood).toContain(`aspect-ratio:${ratio}`);
      expect(html, mood).toContain(`src="${POSE_SETS[mood].images.base}"`);
    }
  });
  it('an expression prop picks a frame inside the same pose and falls back to its base', () => {
    expect(render(<Mascot mood="wave" interactive={false} expression="grin" />)).toContain(POSE_SETS.wave.images.grin);
    expect(render(<Mascot mood="wave" interactive={false} expression="crying" />)).toContain(POSE_SETS.wave.images.base);
  });
  it('an unknown mood keeps the old still image', () => {
    const html = render(<Mascot mood="nope" interactive={false} />);
    expect(html).not.toContain('mascot-frame');
  });
});
