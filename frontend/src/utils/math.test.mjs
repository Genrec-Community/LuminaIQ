// Run with: node src/utils/math.test.mjs
import assert from 'node:assert/strict';
import { normalizeMath, hideUnfinishedMath } from './math.js';

assert.equal(normalizeMath('Speed \\(v = d/t\\) here'), 'Speed $v = d/t$ here');
assert.equal(normalizeMath('Energy:\\[E = mc^2\\]done'), 'Energy:\n$$\nE = mc^2\n$$\ndone');
assert.equal(normalizeMath('code `\\(x\\)` stays'), 'code `\\(x\\)` stays');
assert.equal(hideUnfinishedMath('The formula is $v = u + a'), 'The formula is ');
assert.equal(hideUnfinishedMath('Done: $v = u + at$ and'), 'Done: $v = u + at$ and');
assert.equal(hideUnfinishedMath('Block:\n$$\nE = \\frac{1}{2}'), 'Block:\n');
assert.equal(hideUnfinishedMath('Closed $$x$$ then $y'), 'Closed $$x$$ then ');
assert.equal(hideUnfinishedMath('Costs \\$5 so far'), 'Costs \\$5 so far');
assert.equal(hideUnfinishedMath('Para one $a$.\n\nPara two $b'), 'Para one $a$.\n\nPara two ');
assert.equal(normalizeMath('so\n\n$$E = mc^2$$\n'), 'so\n\n$$\nE = mc^2\n$$\n');
assert.equal(normalizeMath('inline $$x$$ stays'), 'inline $$x$$ stays');
console.log('math utils: all good');
