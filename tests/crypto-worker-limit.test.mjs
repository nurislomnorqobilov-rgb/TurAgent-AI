import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const source=readFileSync(new URL('../src/index.js',import.meta.url),'utf8');
test('PBKDF2 work factor never exceeds the 100,000 WebCrypto cap observed in Workers',()=>{
 const match=source.match(/const PASSWORD_PBKDF2_ITERATIONS\s*=\s*([\d_]+)/);
 assert.ok(match,'PBKDF2 work factor must be a named constant');
 const factor=Number(match[1].replaceAll('_',''));
 assert.ok(factor>0 && factor<=100000,`Unexpected PBKDF2 factor ${factor}`);
 assert.match(source,/iterations:PASSWORD_PBKDF2_ITERATIONS/);
 assert.doesNotMatch(source,/iterations\s*:\s*210000/);
});
