import { build } from 'esbuild';
await build({stdin:{contents:"export { createClient } from '@supabase/supabase-js';",resolveDir:process.cwd()},bundle:true,minify:true,format:'esm',platform:'browser',target:['es2022'],outfile:'members/vendor/supabase.js',legalComments:'eof'});
