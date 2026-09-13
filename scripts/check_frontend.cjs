const path = require('node:path');
try {
  if (Number(process.versions.node.split('.')[0]) < 22) throw Error('Node.js 22 veya uzeri gerekli.');
  if (!process.argv.includes('--node-only')) {
    const options = { paths: [path.resolve(__dirname, '../frontend')] };
    for (const name of ['next', 'react', 'typescript']) require.resolve(`${name}/package.json`, options);
    console.log('Next.js, React ve TypeScript hazir.');
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
