// Ritual de la manana - "Briefing"
// Ejecutado por la tarea programada JaruBriefing (08:00)
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pendientesPath = path.join(__dirname, 'datos', 'pendientes.txt');
const logDir = path.join(__dirname, 'logs');
fs.mkdirSync(logDir, { recursive: true });

const ahora = new Date();
const fechaLarga = ahora.toLocaleDateString('es-MX', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
});
const hora = ahora.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });

let pendientes = [];
try {
  pendientes = fs
    .readFileSync(pendientesPath, 'utf8')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'));
} catch {
  pendientes = [];
}

const lineas = [];
lineas.push('==================================================');
lineas.push(`  BUENOS DIAS  -  ${fechaLarga}`);
lineas.push(`  Hora: ${hora}`);
lineas.push('==================================================');
lineas.push('');
lineas.push(`  Pendientes (${pendientes.length}):`);
if (pendientes.length === 0) {
  lineas.push('    (no hay pendientes registrados)');
} else {
  pendientes.slice(0, 10).forEach((p, i) => lineas.push(`    ${i + 1}. ${p}`));
}
lineas.push('');
lineas.push('  Animo. Un paso a la vez.');
lineas.push('==================================================');

const salida = lineas.join('\n');
console.log(salida);

const logFile = path.join(logDir, `briefing-${ahora.toISOString().slice(0, 10)}.log`);
fs.appendFileSync(logFile, `[${ahora.toISOString()}] Briefing\n${salida}\n\n`, 'utf8');
